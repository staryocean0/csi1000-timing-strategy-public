from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

import risk_phase1b_fresh_oos_eval as ev

PROFILE = "risk-v2-phase1b-fresh-oos-attrition-v1"
TASK_ID = "CSI1000-RISK-V2-2026-FRESH-OOS-ATTRITION-V1-20260915"
SCHEMA_ID = "risk_tool_v2_phase1b_fresh_oos_attrition_result@1.0"
PREREG_SHA256 = "98b5e0f22958986ad77529b260895a849f24054f23fefbc7e71bdd061affd53a"
PARENT_RUN = "34956326542-1"
PARENT_STATUS = "INSUFFICIENT_2026_SUPPORT"
CARRIER_BYTES = 3615731
CARRIER_SHA256 = "211448c914b547232bc536da7df94dc5ae279b8265a5cafe58409238485217d7"
SYMBOLS = ("000688.SH", "000852.SH")
CHECKPOINT_ORDER = (
    "physical_projected",
    "temporal_window_usable",
    "normalized",
    "state_rows",
    "fresh_state_rows",
    "episode_starts",
    "fresh_cohort",
    "horizon_15_usable",
    "horizon_30_usable",
)
PARENT_SUPPORT = {
    "15": {
        "horizon_minutes": 15,
        "rows": 754,
        "positive": 184,
        "negative": 570,
        "trading_day_clusters": 70,
        "by_symbol_rows": {"000688.SH": 0, "000852.SH": 754},
    },
    "30": {
        "horizon_minutes": 30,
        "rows": 690,
        "positive": 319,
        "negative": 371,
        "trading_day_clusters": 67,
        "by_symbol_rows": {"000688.SH": 0, "000852.SH": 690},
    },
}


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_identity(inputs: Path) -> tuple[dict, Path]:
    path = inputs / "DIAGNOSTIC_IDENTITY.json"
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError("diagnostic_identity_not_object")
    if value.get("profile") != PROFILE or value.get("task_id") != TASK_ID:
        raise RuntimeError("diagnostic_identity_task_mismatch")
    if value.get("prereg_sha256") != PREREG_SHA256:
        raise RuntimeError("diagnostic_identity_prereg_mismatch")
    parent = value.get("parent_fresh_oos") or {}
    if parent.get("run_id") != PARENT_RUN or parent.get("overall_status") != PARENT_STATUS:
        raise RuntimeError("diagnostic_identity_parent_mismatch")
    if value.get("diagnostic_only") is not True or value.get("parent_verdict_changed") is not False:
        raise RuntimeError("diagnostic_identity_boundary_mismatch")
    carrier = value.get("carrier") or {}
    if carrier.get("bytes") != CARRIER_BYTES or carrier.get("sha256") != CARRIER_SHA256:
        raise RuntimeError("diagnostic_identity_carrier_mismatch")
    carrier_path = inputs / "market" / "5m_offset_0.parquet"
    if not carrier_path.is_file() or carrier_path.is_symlink():
        raise RuntimeError("carrier_file_missing")
    if carrier_path.stat().st_size != CARRIER_BYTES or sha256_file(carrier_path) != CARRIER_SHA256:
        raise RuntimeError("carrier_file_identity_mismatch")
    return value, carrier_path


def read_physical(carrier_path: Path) -> pd.DataFrame:
    parquet = pq.ParquetFile(carrier_path)
    required = ("timestamp", "symbol", "close")
    names = tuple(parquet.schema_arrow.names)
    missing = [name for name in required if name not in names]
    if missing:
        raise RuntimeError("carrier_physical_columns_missing:" + ",".join(missing))
    table = parquet.read(columns=list(required), use_pandas_metadata=False)
    return table.to_pandas(ignore_metadata=True).rename(columns={"timestamp": "datetime"})


def count_frame(frame: pd.DataFrame) -> dict:
    if "symbol" not in frame:
        raise RuntimeError("count_frame_symbol_missing")
    symbols = frame["symbol"].astype(str)
    by_rows = {symbol: int(symbols.eq(symbol).sum()) for symbol in SYMBOLS}
    result = {
        "rows": int(sum(by_rows.values())),
        "by_symbol_rows": by_rows,
    }
    if "trading_day" in frame:
        days = frame["trading_day"].astype(str)
        result["trading_days"] = int(frame.loc[symbols.isin(SYMBOLS), "trading_day"].nunique())
        result["by_symbol_trading_days"] = {
            symbol: int(days[symbols.eq(symbol)].nunique()) for symbol in SYMBOLS
        }
    return result


def temporal_window(source: pd.DataFrame) -> pd.DataFrame:
    z = pd.DataFrame(
        {
            "symbol": source["symbol"].astype(str),
            "bar_end": ev.wallclock(source["datetime"]),
            "close": pd.to_numeric(source["close"], errors="coerce"),
        }
    ).dropna()
    z = z[z.symbol.isin(SYMBOLS)].copy()
    z["trading_day"] = z.bar_end.dt.strftime("%Y-%m-%d")
    years = z.bar_end.dt.year
    return z[(years == ev.WARMUP_YEAR) | ((years == ev.FRESH_YEAR) & z.trading_day.le(ev.CUTOFF_DAY))].copy()


def count_episode_starts(states: pd.DataFrame) -> dict:
    by_symbol = {symbol: 0 for symbol in SYMBOLS}
    for (symbol, day_name), z0 in states.groupby(["symbol", "trading_day"], sort=False):
        if int(str(day_name)[:4]) != ev.FRESH_YEAR:
            continue
        day = z0.sort_values("bar_end", kind="stable").reset_index(drop=True)
        prev_unsafe = day.risk_state.shift(1).eq("UNSAFE").fillna(False)
        candidates = list(day.index[day.shock.astype(bool) & ~prev_unsafe])
        occupied = -1
        for j0 in candidates:
            j = int(j0)
            if j <= occupied:
                continue
            normals = day.index[(day.index > j) & day.risk_state.eq("NORMAL")]
            end = int(normals[0]) if len(normals) else None
            occupied = (end - 1) if end is not None else int(day.index.max())
            by_symbol[str(symbol)] += 1
    return {"rows": int(sum(by_symbol.values())), "by_symbol_rows": by_symbol}


def parent_support_snapshot(cohort: pd.DataFrame, horizon: int) -> dict:
    raw = ev.support_gate(cohort, horizon)
    return {
        "horizon_minutes": int(raw["horizon_minutes"]),
        "rows": int(raw["rows"]),
        "positive": int(raw["positive"]),
        "negative": int(raw["negative"]),
        "trading_day_clusters": int(raw["trading_day_clusters"]),
        "by_symbol_rows": {symbol: int(raw["by_symbol_rows"][symbol]) for symbol in SYMBOLS},
    }


def build_result(inputs: Path) -> dict:
    identity, carrier_path = load_identity(inputs)
    source = read_physical(carrier_path)

    projected = source[source.symbol.astype(str).isin(SYMBOLS)].copy()
    window = temporal_window(source)
    normalized = ev.normalize_carrier(source)
    states = ev.build_state_rows(normalized)
    fresh_states = states[states.year.eq(ev.FRESH_YEAR)].copy()
    starts = count_episode_starts(states)
    cohort = ev.build_fresh_cohort(states)
    h15 = cohort[cohort["normal_within_15m"].notna()].copy()
    h30 = cohort[cohort["normal_within_30m"].notna()].copy()

    checkpoints = {
        "physical_projected": count_frame(projected),
        "temporal_window_usable": count_frame(window),
        "normalized": count_frame(normalized),
        "state_rows": count_frame(states),
        "fresh_state_rows": count_frame(fresh_states),
        "episode_starts": starts,
        "fresh_cohort": count_frame(cohort),
        "horizon_15_usable": count_frame(h15),
        "horizon_30_usable": count_frame(h30),
    }

    support = {
        "15": parent_support_snapshot(cohort, 15),
        "30": parent_support_snapshot(cohort, 30),
    }
    for horizon, expected in PARENT_SUPPORT.items():
        if support[horizon] != expected:
            raise RuntimeError("parent_support_not_reproduced:" + horizon)

    first_zero = {}
    for symbol in SYMBOLS:
        first_zero[symbol] = next(
            (name for name in CHECKPOINT_ORDER if checkpoints[name]["by_symbol_rows"][symbol] == 0),
            None,
        )

    return {
        "schema_id": SCHEMA_ID,
        "task_id": TASK_ID,
        "profile": PROFILE,
        "prereg_sha256": PREREG_SHA256,
        "parent_fresh_oos": {
            "run_id": PARENT_RUN,
            "overall_status": PARENT_STATUS,
            "verdict_immutable": True,
        },
        "carrier_identity_sha256": CARRIER_SHA256,
        "cutoff_trading_day_inclusive": ev.CUTOFF_DAY,
        "checkpoint_order": list(CHECKPOINT_ORDER),
        "checkpoints": checkpoints,
        "first_zero_checkpoint": first_zero,
        "parent_support_reproduced": support,
        "status": "DIAGNOSTIC_COMPLETE",
        "diagnostic_only": True,
        "parent_verdict_changed": False,
        "model_execution": False,
        "calibration_execution": False,
        "new_training": False,
        "row_level_market_data_exported": False,
        "market_values_exported": False,
        "timestamps_exported": False,
        "model_outputs_exported": False,
        "production_authority": False,
        "source_identity": {
            "same_accepted_carrier_as_parent": True,
            "user_authorized_same_source_and_valid": bool(identity.get("user_authorized_same_source_and_valid")),
        },
    }


def run(inputs: Path, out: Path) -> dict:
    if out.exists():
        raise RuntimeError("output_directory_already_exists")
    result = build_result(inputs)
    out.mkdir(parents=True)
    (out / "ATTRITION.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.inputs.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
