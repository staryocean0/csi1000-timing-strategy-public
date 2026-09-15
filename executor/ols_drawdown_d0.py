from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from dataclasses import dataclass
from datetime import timezone, timedelta
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

SYMBOL = "000852.SH"
YEARS = tuple(range(2020, 2026))
WINDOWS = (12, 24)
EXIT_MODES = (
    "qualification_reset",
    "first_opposite_close",
    "two_opposite_closes",
    "prior_extreme_break",
    "frozen_midline_break",
)
DATA = {
    2020: (353781, "c45ef84c123ae9f4ca1843b2816a4f413742547e"),
    2021: (347162, "aba298f940c7992ec8814dd8ece197477d106fa9"),
    2022: (351753, "fe6eed805f7237091813c32d25011848fc29b705"),
    2023: (342750, "0b17d76b150bfd15d45158f100748898e72089b1"),
    2024: (349739, "ba45837375d8a3ca64cb3faa7750bf51e9760796"),
    2025: (353882, "85159b9fa1b2b6854b1a0f04faa9f963e9d04c13"),
}
PRIVATE_REF = "67effb80f51228f6129dca5c4f7971a0bb6c7f15"
DATA_REF = "1d760ea9525eb3688b70a4aa0f2b5b207af16a17"
FAST_MIN_SLOPE = 0.001
FAST_MIN_PATH_EFFICIENCY = 0.30
FAST_MIN_R2 = 0.10
MAX_SINGLE_BAR_SHARE = 0.50
TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class OlsFit:
    slope: np.ndarray
    prediction: np.ndarray
    r2: np.ndarray
    residual_sigma: np.ndarray


def _blobsha(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _aware_timestamp(series: pd.Series) -> pd.Series:
    values = pd.to_datetime(series.astype(str).str.slice(0, 25), errors="coerce")
    if values.isna().any():
        raise RuntimeError("ols_d0_invalid_timestamp")
    try:
        current_tz = values.dt.tz
    except AttributeError as exc:
        raise RuntimeError("ols_d0_invalid_timestamp") from exc
    return values.dt.tz_localize(TZ) if current_tz is None else values.dt.tz_convert(TZ)


def _load_5m(inputs: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    frames: list[pd.DataFrame] = []
    receipt: dict[str, object] = {}
    required = {"trading_day", "timestamp", "open", "high", "low", "close"}
    for year in YEARS:
        size, blob = DATA[year]
        path = inputs / f"{year}.parquet"
        if not path.is_file() or path.stat().st_size != size or _blobsha(path) != blob:
            raise RuntimeError(f"ols_d0_data_identity_mismatch_{year}")
        raw = pd.read_parquet(path)
        missing = sorted(required.difference(raw.columns))
        if missing:
            raise RuntimeError(f"ols_d0_market_data_missing_ohlc_{year}:{missing}")
        z = pd.DataFrame(
            {
                "trading_day": pd.to_datetime(raw["trading_day"], errors="coerce").dt.strftime("%Y-%m-%d"),
                "timestamp": _aware_timestamp(raw["timestamp"]),
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
        z["session"] = np.where(z["timestamp"].dt.hour < 12, "AM", "PM")
        session_counts = z.groupby(["trading_day", "session"], sort=False).size()
        if len(session_counts[session_counts != 24]):
            raise RuntimeError(f"ols_d0_non_24_bar_session_{year}")
        frames.append(z)
        receipt[str(year)] = {
            "bytes": size,
            "git_blob_sha1": blob,
            "sha256": _sha256(path),
        }
    return pd.concat(frames, ignore_index=True), receipt


def _to_15m(frame: pd.DataFrame) -> pd.DataFrame:
    z = frame.copy()
    z["session_index"] = z.groupby(["trading_day", "session"], sort=False).cumcount()
    z["bucket"] = z["session_index"] // 3
    grouped = z.groupby(["trading_day", "session", "bucket"], sort=False)
    if not grouped.size().eq(3).all():
        raise RuntimeError("ols_d0_15m_bucket_not_three_5m_bars")
    out = grouped.agg(
        timestamp=("timestamp", "max"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
    ).reset_index(drop=False)
    counts = out.groupby("trading_day", sort=False).size()
    if len(counts[counts != 16]):
        raise RuntimeError("ols_d0_non_16_bar_15m_day")
    out = out.sort_values("timestamp", kind="stable").reset_index(drop=True)
    if out["timestamp"].duplicated().any() or not out["timestamp"].is_monotonic_increasing:
        raise RuntimeError("ols_d0_15m_timestamp_order_invalid")
    return out[["timestamp", "open", "high", "low", "close", "trading_day", "session"]]


def _prior_ols(values: np.ndarray, window: int) -> OlsFit:
    raw = np.asarray(values, dtype=float)
    n = len(raw)
    empty = np.full(n, np.nan, dtype=float)
    if n < window + 1:
        return OlsFit(empty.copy(), empty.copy(), empty.copy(), empty.copy())
    if not np.isfinite(raw).all():
        raise RuntimeError("ols_d0_nonfinite_log_close")
    level_offset = float(raw[0])
    working = raw - level_offset
    x = np.arange(window, dtype=float)
    x_mean = float(x.mean())
    sxx = float(np.square(x - x_mean).sum())
    positions = np.arange(window, n)
    cumulative = np.concatenate(([0.0], np.cumsum(working)))
    cumulative_square = np.concatenate(([0.0], np.cumsum(np.square(working))))
    sum_y = cumulative[positions] - cumulative[positions - window]
    sum_y_square = cumulative_square[positions] - cumulative_square[positions - window]
    dot_xy = np.correlate(working, x, mode="valid")[: n - window]
    centered_xy = dot_xy - x_mean * sum_y
    slope_values = centered_xy / sxx
    intercept_values = sum_y / float(window) - slope_values * x_mean
    predictions = intercept_values + slope_values * float(window) + level_offset
    total_square = np.maximum(sum_y_square - np.square(sum_y) / float(window), 0.0)
    residual_square = np.maximum(total_square - slope_values * centered_xy, 0.0)
    unexplained = np.divide(
        residual_square,
        total_square,
        out=np.ones_like(residual_square),
        where=total_square > np.finfo(float).eps,
    )
    r2_values = np.clip(1.0 - unexplained, 0.0, 1.0)
    sigma_values = np.sqrt(residual_square / float(max(window - 2, 1)))
    slope = empty.copy(); prediction = empty.copy(); r2 = empty.copy(); sigma = empty.copy()
    slope[positions] = slope_values
    prediction[positions] = predictions
    r2[positions] = r2_values
    sigma[positions] = sigma_values
    return OlsFit(slope, prediction, r2, sigma)


def _path_attributes(log_close: np.ndarray, window: int) -> tuple[np.ndarray, np.ndarray]:
    size = len(log_close)
    efficiency = np.full(size, np.nan, dtype=float)
    tail_share = np.full(size, np.nan, dtype=float)
    for location in range(window, size):
        full = log_close[location - window : location]
        returns = np.diff(full)
        gross = float(np.abs(returns).sum())
        net_down = float(full[0] - full[-1])
        if gross > 0.0:
            efficiency[location] = abs(net_down) / gross
        if net_down > np.finfo(float).eps:
            tail_share[location] = float(np.maximum(-returns, 0.0).max(initial=0.0) / net_down)
    return efficiency, tail_share


def _down_features(close: np.ndarray) -> dict[int, dict[str, np.ndarray]]:
    log_close = np.log(close)
    result: dict[int, dict[str, np.ndarray]] = {}
    for window in WINDOWS:
        fit = _prior_ols(log_close, window)
        sigma = np.maximum(fit.residual_sigma, np.finfo(float).eps)
        upper = np.exp(fit.prediction + sigma)
        lower = np.exp(fit.prediction - sigma)
        efficiency, tail_share = _path_attributes(log_close, window)
        centre = np.sqrt(upper * lower)
        common = (
            np.isfinite(fit.slope)
            & np.isfinite(fit.r2)
            & np.isfinite(upper)
            & np.isfinite(lower)
            & np.isfinite(efficiency)
            & np.isfinite(tail_share)
            & (fit.slope < 0.0)
            & (tail_share <= MAX_SINGLE_BAR_SHARE)
            & (close <= centre)
        )
        qualified = (
            common
            & (fit.slope <= -FAST_MIN_SLOPE)
            & (fit.r2 >= FAST_MIN_R2)
            & (efficiency >= FAST_MIN_PATH_EFFICIENCY)
        )
        prior = np.zeros(len(close), dtype=bool)
        if len(close) > 1:
            prior[1:] = qualified[:-1]
        result[window] = {
            "slope": fit.slope,
            "fit_r2": fit.r2,
            "upper": upper,
            "lower": lower,
            "path_efficiency": efficiency,
            "qualified": qualified,
            "candidate": qualified & ~prior,
        }
    return result


def _features(ohlc: pd.DataFrame, side: Literal["up", "down"]) -> dict[int, dict[str, np.ndarray]]:
    if side == "down":
        return _down_features(ohlc["close"].to_numpy(float))
    mirrored_close = 1.0 / ohlc["close"].to_numpy(float)
    raw = _down_features(mirrored_close)
    result: dict[int, dict[str, np.ndarray]] = {}
    for window, fields in raw.items():
        result[window] = {
            "slope": -fields["slope"],
            "fit_r2": fields["fit_r2"],
            "upper": 1.0 / fields["lower"],
            "lower": 1.0 / fields["upper"],
            "path_efficiency": fields["path_efficiency"],
            "qualified": fields["qualified"],
            "candidate": fields["candidate"],
        }
    return result


def _opposite(mode: str, side: str, i: int, close: np.ndarray, high: np.ndarray, low: np.ndarray) -> bool:
    if mode == "qualification_reset":
        return True
    if mode == "first_opposite_close":
        return bool(i > 0 and (close[i] < close[i - 1] if side == "up" else close[i] > close[i - 1]))
    if mode == "two_opposite_closes":
        return bool(
            i > 1
            and (
                close[i] < close[i - 1] < close[i - 2]
                if side == "up"
                else close[i] > close[i - 1] > close[i - 2]
            )
        )
    if mode == "prior_extreme_break":
        return bool(i > 0 and (close[i] < low[i - 1] if side == "up" else close[i] > high[i - 1]))
    return False


def _side_lifecycle(
    ohlc: pd.DataFrame,
    features: dict[int, dict[str, np.ndarray]],
    mode: str,
    side: Literal["up", "down"],
) -> dict[str, np.ndarray]:
    size = len(ohlc)
    close = ohlc["close"].to_numpy(float)
    high = ohlc["high"].to_numpy(float)
    low = ohlc["low"].to_numpy(float)
    decision = np.zeros(size, dtype=bool)
    entry = np.zeros(size, dtype=bool)
    entry_window = np.zeros(size, dtype=np.int16)
    exit_trigger = np.zeros(size, dtype=bool)
    authority = np.zeros(size, dtype=np.int16)
    live_midline = np.full(size, np.nan, dtype=float)
    active = False; window = 0; anchor = -1
    slope = np.nan; upper = np.nan; lower = np.nan
    for i in range(size):
        exited_now = False
        live = [w for w in WINDOWS if bool(features[w]["qualified"][i])]
        if active:
            elapsed = i - anchor
            projected_upper = upper * np.exp(slope * elapsed)
            projected_lower = lower * np.exp(slope * elapsed)
            boundary = float(np.sqrt(projected_upper * projected_lower))
            live_midline[i] = boundary
            boundary_break = close[i] < boundary if side == "up" else close[i] > boundary
            family_reset = not live
            shape_confirmed = _opposite(mode, side, i, close, high, low)
            reset_exit = bool(mode != "frozen_midline_break" and family_reset and shape_confirmed)
            if boundary_break or reset_exit:
                active = False; window = 0; anchor = -1
                slope = np.nan; upper = np.nan; lower = np.nan
                exit_trigger[i] = True
                exited_now = True
        if not active and not exited_now:
            fresh = [w for w in WINDOWS if bool(features[w]["candidate"][i])]
            if fresh:
                scores = {
                    w: float(
                        abs(features[w]["slope"][i])
                        * float(w - 1)
                        * max(float(features[w]["path_efficiency"][i]), 0.0)
                        * max(float(features[w]["fit_r2"][i]), 0.0)
                    )
                    for w in fresh
                }
                selected = max(fresh, key=scores.__getitem__)
                active = True; window = selected; anchor = i
                slope = float(features[selected]["slope"][i])
                upper = float(features[selected]["upper"][i])
                lower = float(features[selected]["lower"][i])
                entry[i] = True; entry_window[i] = selected
        decision[i] = active
        authority[i] = window
    return {
        "decision": decision,
        "entry": entry,
        "entry_window": entry_window,
        "exit": exit_trigger,
        "authority": authority,
        "midline": live_midline,
    }


def _strategy(ohlc: pd.DataFrame, upf, downf, mode: str) -> pd.DataFrame:
    up = _side_lifecycle(ohlc, upf, mode, "up")
    down = _side_lifecycle(ohlc, downf, mode, "down")
    raw_up = up["decision"].astype(bool); raw_down = down["decision"].astype(bool)
    conflict = raw_up & raw_down
    decision = raw_up.astype(np.int8) - raw_down.astype(np.int8)
    decision[conflict] = 0
    authority = np.where(decision == 1, up["authority"], np.where(decision == -1, down["authority"], 0)).astype(np.int16)
    executable = np.zeros(len(ohlc), dtype=np.int8)
    executable_authority = np.zeros(len(ohlc), dtype=np.int16)
    if len(ohlc) > 1:
        executable[1:] = decision[:-1]
        executable_authority[1:] = authority[:-1]
    output = pd.DataFrame(
        {
            "timestamp": ohlc["timestamp"],
            "decision_position_for_next_bar": decision,
            "executable_position": executable,
            "executable_authority_window_bars": executable_authority,
            "direction_conflict": conflict,
            "exit_trigger": up["exit"] | down["exit"],
            "up_live_ols_midline": up["midline"],
            "down_live_ols_midline": down["midline"],
        }
    )
    return output


def _trace(ohlc: pd.DataFrame, strategy: pd.DataFrame, upf, downf) -> pd.DataFrame:
    next_open_return = ohlc["open"].shift(-1).div(ohlc["open"]).sub(1.0)
    rows: list[dict[str, object]] = []
    for i in range(len(ohlc) - 1):
        pos = int(strategy.at[i, "executable_position"])
        window = int(strategy.at[i, "executable_authority_window_bars"])
        row: dict[str, object] = {
            "timestamp": pd.Timestamp(ohlc.at[i, "timestamp"]).isoformat(),
            "strategy_return": float(pos * next_open_return.iat[i]),
            "executable_position": pos,
            "fit_r2": "",
            "path_efficiency": "",
            "slope_per_bar": "",
            "authority_window_bars": "" if pos == 0 else window,
            "qualified": "",
            "direction_conflict": bool(strategy.at[i, "direction_conflict"]),
            "exit_trigger": bool(strategy.at[i, "exit_trigger"]),
            "ols_midline": "",
            "close": float(ohlc.at[i, "close"]),
        }
        if pos != 0:
            if window not in WINDOWS:
                raise RuntimeError("ols_d0_nonflat_authority_window_invalid")
            side = upf if pos == 1 else downf
            r2 = float(side[window]["fit_r2"][i])
            eff = float(side[window]["path_efficiency"][i])
            slope = float(side[window]["slope"][i])
            if not (math.isfinite(r2) and math.isfinite(eff) and math.isfinite(slope)):
                raise RuntimeError("ols_d0_active_feature_nonfinite")
            row.update(
                {
                    "fit_r2": r2,
                    "path_efficiency": eff,
                    "slope_per_bar": slope,
                    "qualified": bool(side[window]["qualified"][i]),
                    "ols_midline": float(
                        strategy.at[i, "up_live_ols_midline"] if pos == 1 else strategy.at[i, "down_live_ols_midline"]
                    ) if math.isfinite(float(strategy.at[i, "up_live_ols_midline"] if pos == 1 else strategy.at[i, "down_live_ols_midline"])) else "",
                }
            )
        rows.append(row)
    return pd.DataFrame(rows)


def _atlas_module(path: Path):
    spec = importlib.util.spec_from_file_location("ols_drawdown_atlas", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _episode_stats(summary: dict[str, object]) -> dict[str, object]:
    episodes = list(summary.get("worst_episodes", []))
    valid = [row for row in episodes if isinstance(row, dict) and row.get("fit_r2_at_start") is not None and row.get("fit_r2_at_trough") is not None]
    deteriorated = [row for row in valid if float(row["fit_r2_at_trough"]) < float(row["fit_r2_at_start"])]
    leads = [int(row["r2_two_down_lead_bars_to_trough"]) for row in valid if row.get("r2_two_down_lead_bars_to_trough") is not None]
    collapses = [float(row["fit_r2_peak_to_trough"]) for row in valid if row.get("fit_r2_peak_to_trough") is not None]
    return {
        "top_episode_count": len(episodes),
        "r2_observable_episode_count": len(valid),
        "r2_lower_at_trough_fraction": None if not valid else len(deteriorated) / len(valid),
        "median_r2_peak_to_trough_collapse": None if not collapses else float(np.median(collapses)),
        "two_consecutive_r2_declines_before_trough_fraction": None if not valid else len(leads) / len(valid),
        "median_two_decline_lead_bars": None if not leads else float(np.median(leads)),
    }


def run(inputs: Path, out: Path, atlas_script: Path) -> None:
    raw5, data_receipt = _load_5m(inputs)
    bars = _to_15m(raw5)
    upf = _features(bars, "up")
    downf = _features(bars, "down")
    atlas = _atlas_module(atlas_script)
    out.mkdir(parents=True, exist_ok=True)
    comparison: list[dict[str, object]] = []
    mode_summaries: dict[str, object] = {}
    for mode in EXIT_MODES:
        mode_dir = out / mode
        mode_dir.mkdir()
        strategy = _strategy(bars, upf, downf, mode)
        trace = _trace(bars, strategy, upf, downf)
        trace_path = mode_dir / "trace.csv"
        trace.to_csv(trace_path, index=False)
        summary = atlas.run(trace_path, mode_dir, top_n=20)
        extras = _episode_stats(summary)
        row = {
            "exit_mode": mode,
            "total_return_gross": float(summary["total_return"]),
            "maximum_drawdown_gross": float(summary["maximum_drawdown"]),
            "final_equity_gross": float(summary["final_equity"]),
            "episode_count": int(summary["episode_count"]),
            "nonflat_bar_count": int(trace["executable_position"].ne(0).sum()),
            "long_bar_count": int(trace["executable_position"].gt(0).sum()),
            "short_bar_count": int(trace["executable_position"].lt(0).sum()),
            **extras,
        }
        comparison.append(row)
        mode_summaries[mode] = {**summary, "d0_episode_diagnostics": extras}
    comparison_frame = pd.DataFrame(comparison)
    comparison_frame.to_csv(out / "mode_comparison.csv", index=False)
    source_receipt = json.loads((inputs / "SOURCE_PROVENANCE.json").read_text())
    result = {
        "schema_id": "ols_drawdown_d0_replay@1.0",
        "status": "completed_diagnostic_only",
        "symbol": SYMBOL,
        "years": list(YEARS),
        "bar_frequency": "15m_from_session_local_three_x_5m",
        "data_ref": DATA_REF,
        "private_source_ref": PRIVATE_REF,
        "data_receipt": data_receipt,
        "source_provenance": source_receipt,
        "exit_modes_replayed": list(EXIT_MODES),
        "historical_best_exit_mode_predeclared": None,
        "historical_best_exit_mode_unresolved": True,
        "execution_semantics": "close_t_decision_open_t_plus_1; executable_position owns open_t_to_open_t_plus_1 gross return",
        "transaction_cost_assumption": "zero_cost_gross_d0_diagnosis_only",
        "optimization_performed": False,
        "new_training": False,
        "production_authority": False,
        "mode_summaries": mode_summaries,
    }
    (out / "RESULTS.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    lines = [
        "# OLS D0 drawdown replay",
        "",
        "Diagnostic only; no parameter, routing, sizing, leverage, or production change.",
        "",
        "| exit mode | gross return | max drawdown | non-flat bars | R2 lower at trough | median R2 peak→trough collapse |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in comparison:
        lower = row["r2_lower_at_trough_fraction"]
        collapse = row["median_r2_peak_to_trough_collapse"]
        lines.append(
            f"| {row['exit_mode']} | {row['total_return_gross']:.6f} | {row['maximum_drawdown_gross']:.6f} | {row['nonflat_bar_count']} | "
            f"{'' if lower is None else f'{float(lower):.3f}'} | {'' if collapse is None else f'{float(collapse):.4f}'} |"
        )
    lines += [
        "",
        "The table compares all five already-frozen exit modes because the online CSI1000 pair does not preserve a unique historical winner label. This is baseline identity recovery, not tuning.",
        "",
        "R2 deterioration is interpreted only descriptively in D0. No veto threshold is authorized by this replay.",
    ]
    (out / "RESULTS.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--atlas-script", required=True, type=Path)
    args = parser.parse_args()
    run(args.inputs, args.out, args.atlas_script)


if __name__ == "__main__":
    main()
