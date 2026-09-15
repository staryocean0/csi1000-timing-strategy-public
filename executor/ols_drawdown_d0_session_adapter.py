from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_ols_drawdown_d0", HERE / "ols_drawdown_d0.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("ols_d0_adapter_source_unavailable")
d0 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(d0)


def _load_5m_by_verified_order(inputs: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    frames: list[pd.DataFrame] = []
    receipt: dict[str, object] = {}
    required = {"trading_day", "timestamp", "open", "high", "low", "close"}
    for year in d0.YEARS:
        size, blob = d0.DATA[year]
        path = inputs / f"{year}.parquet"
        if not path.is_file() or path.stat().st_size != size or d0._blobsha(path) != blob:
            raise RuntimeError(f"ols_d0_data_identity_mismatch_{year}")
        raw = pd.read_parquet(path)
        missing = sorted(required.difference(raw.columns))
        if missing:
            raise RuntimeError(f"ols_d0_market_data_missing_ohlc_{year}:{missing}")
        z = pd.DataFrame(
            {
                "trading_day": pd.to_datetime(raw["trading_day"], errors="coerce").dt.strftime("%Y-%m-%d"),
                "timestamp": d0._aware_timestamp(raw["timestamp"]),
                "open": pd.to_numeric(raw["open"], errors="coerce"),
                "high": pd.to_numeric(raw["high"], errors="coerce"),
                "low": pd.to_numeric(raw["low"], errors="coerce"),
                "close": pd.to_numeric(raw["close"], errors="coerce"),
            }
        ).dropna()
        z = z[pd.to_datetime(z["trading_day"]).dt.year.eq(year)].copy()
        z = z.sort_values(["trading_day", "timestamp"], kind="stable").reset_index(drop=True)
        values = z[["open", "high", "low", "close"]].to_numpy(float)
        if z.empty or not np.isfinite(values).all() or bool((values <= 0.0).any()):
            raise RuntimeError(f"ols_d0_invalid_ohlc_{year}")
        if bool((z["high"] < z[["open", "close"]].max(axis=1)).any()) or bool(
            (z["low"] > z[["open", "close"]].min(axis=1)).any()
        ):
            raise RuntimeError(f"ols_d0_invalid_bar_{year}")
        counts = z.groupby("trading_day", sort=False).size()
        bad = counts[counts != 48]
        if len(bad):
            raise RuntimeError(f"ols_d0_non_48_bar_day_{year}:{bad.head().to_dict()}")

        # The frozen carrier contract already establishes exactly 48 ordered 5m bars
        # per trading day. Session membership is therefore a physical-schema concern:
        # first 24 bars are the morning session, final 24 bars are the afternoon session.
        # This avoids inferring session identity from timezone rendering of timestamps.
        day_index = z.groupby("trading_day", sort=False).cumcount()
        z["session"] = np.where(day_index < 24, "AM", "PM")
        session_counts = z.groupby(["trading_day", "session"], sort=False).size()
        if len(session_counts[session_counts != 24]):
            raise RuntimeError(f"ols_d0_non_24_bar_session_{year}")
        frames.append(z)
        receipt[str(year)] = {
            "bytes": size,
            "git_blob_sha1": blob,
            "sha256": d0._sha256(path),
        }
    return pd.concat(frames, ignore_index=True), receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--atlas-script", required=True, type=Path)
    args = parser.parse_args()
    d0._load_5m = _load_5m_by_verified_order
    d0.run(args.inputs, args.out, args.atlas_script)


if __name__ == "__main__":
    main()
