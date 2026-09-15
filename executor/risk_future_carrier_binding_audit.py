from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

TASK_ID = "CSI1000-RISK-V2-FUTURE-CARRIER-BINDING-AUDIT-V1-20260915"
PROFILE = "risk-v2-future-carrier-binding-audit-v1"
SCHEMA_ID = "risk_tool_v2_future_carrier_binding_audit_result@1.0"
PREREG_SHA256 = "6158bfb13dafe8a6ffee255455320c6598d17c932115985070994cade0030540"
EXPECTED_SYMBOLS = ("000688.SH", "000852.SH")
FUTURE_START = "2026-09-14"
FUTURE_END = "2027-03-31"


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError("json_object_required")
    return value


def _wallclock(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(str).str.slice(0, 19), errors="coerce")


def inspect_member(path: Path, expected_symbol: str, identity: dict) -> dict:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"pair_member_missing:{expected_symbol}")
    expected_bytes = int(identity["bytes"])
    expected_sha = str(identity["sha256"])
    if path.stat().st_size != expected_bytes or sha256_file(path) != expected_sha:
        raise RuntimeError(f"pair_member_identity_mismatch:{expected_symbol}")

    parquet = pq.ParquetFile(path)
    schema = parquet.schema_arrow
    names = list(schema.names)
    if "symbol" not in names:
        raise RuntimeError(f"symbol_field_missing:{expected_symbol}")
    time_field = "trading_day" if "trading_day" in names else ("timestamp" if "timestamp" in names else None)
    if time_field is None:
        raise RuntimeError(f"time_identity_field_missing:{expected_symbol}")

    # Deliberately read identity fields only. Market-value fields may exist in
    # the physical schema but are never deserialized here.
    frame = pq.read_table(path, columns=["symbol", time_field]).to_pandas()
    symbols = sorted(set(frame["symbol"].dropna().astype(str)))
    if time_field == "trading_day":
        day = pd.to_datetime(frame[time_field].astype(str).str.slice(0, 10), errors="coerce")
    else:
        day = _wallclock(frame[time_field])
    day = day.dropna()

    symbol_match = symbols == [expected_symbol]
    min_day = day.min().strftime("%Y-%m-%d") if len(day) else None
    max_day = day.max().strftime("%Y-%m-%d") if len(day) else None

    return {
        "expected_symbol": expected_symbol,
        "archive_path": identity["archive_path"],
        "bytes": expected_bytes,
        "sha256": expected_sha,
        "rows": int(parquet.metadata.num_rows),
        "physical_fields": [{"name": field.name, "type": str(field.type)} for field in schema],
        "identity_columns_read": ["symbol", time_field],
        "distinct_symbols": symbols,
        "symbol_binding_valid": bool(symbol_match),
        "time_identity_field": time_field,
        "time_identity_non_null_rows": int(len(day)),
        "min_trading_day": min_day,
        "max_trading_day": max_day,
        "market_value_columns_read": False,
        "row_level_data_exported": False,
    }


def run(inputs: Path, out: Path) -> dict:
    if out.exists():
        raise RuntimeError("output_directory_already_exists")
    identity = load_json(inputs / "PAIR_INPUT_IDENTITY.json")
    if identity.get("schema_id") != "risk_tool_v2_future_carrier_binding_input@1.0":
        raise RuntimeError("input_identity_schema_mismatch")
    if identity.get("task_id") != TASK_ID or identity.get("prereg_sha256") != PREREG_SHA256:
        raise RuntimeError("input_identity_task_or_prereg_mismatch")
    members = identity.get("members")
    if not isinstance(members, dict) or set(members) != set(EXPECTED_SYMBOLS):
        raise RuntimeError("pair_member_set_mismatch")

    inspected = {}
    for symbol in EXPECTED_SYMBOLS:
        local = inputs / "pair" / (symbol + ".parquet")
        inspected[symbol] = inspect_member(local, symbol, members[symbol])

    valid = all(inspected[s]["symbol_binding_valid"] for s in EXPECTED_SYMBOLS)
    starts = [inspected[s]["min_trading_day"] for s in EXPECTED_SYMBOLS if inspected[s]["min_trading_day"]]
    ends = [inspected[s]["max_trading_day"] for s in EXPECTED_SYMBOLS if inspected[s]["max_trading_day"]]
    overlap_start = max(starts) if len(starts) == 2 else None
    overlap_end = min(ends) if len(ends) == 2 else None
    covers_future = bool(
        valid
        and overlap_start is not None
        and overlap_end is not None
        and overlap_start <= FUTURE_START
        and overlap_end >= FUTURE_END
    )

    result = {
        "schema_id": SCHEMA_ID,
        "task_id": TASK_ID,
        "profile": PROFILE,
        "prereg_sha256": PREREG_SHA256,
        "status": "PAIR_BINDING_VALID_FOR_SOURCE_FAMILY" if valid else "PAIR_BINDING_INVALID",
        "source": identity["source"],
        "members": inspected,
        "pair_overlap": {
            "min_trading_day": overlap_start,
            "max_trading_day": overlap_end,
        },
        "future_oos_window": {
            "start_inclusive": FUTURE_START,
            "end_inclusive": FUTURE_END,
            "current_snapshot_covers_full_window": covers_future,
            "current_snapshot_is_future_oos_evidence": False,
        },
        "controls": {
            "market_values_read": False,
            "returns_or_labels_read": False,
            "model_execution": False,
            "calibration_execution": False,
            "new_training": False,
            "parent_verdict_changed": False,
            "strategy_authority": False,
            "production_authority": False,
        },
    }
    out.mkdir(parents=True)
    (out / "BINDING_AUDIT.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.inputs.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
