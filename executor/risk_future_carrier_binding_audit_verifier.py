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


def load(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError("json_object_required")
    return value


def independently_inspect(path: Path, symbol: str, meta: dict) -> dict:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("audit_member_missing")
    if path.stat().st_size != int(meta["bytes"]) or sha256_file(path) != str(meta["sha256"]):
        raise RuntimeError("audit_member_digest_mismatch")
    pf = pq.ParquetFile(path)
    schema = pf.schema_arrow
    names = list(schema.names)
    if "symbol" not in names:
        raise RuntimeError("audit_symbol_field_missing")
    time_field = "trading_day" if "trading_day" in names else ("timestamp" if "timestamp" in names else None)
    if time_field is None:
        raise RuntimeError("audit_time_field_missing")
    table = pq.read_table(path, columns=["symbol", time_field]).to_pandas()
    symbols = sorted(set(table["symbol"].dropna().astype(str)))
    if time_field == "trading_day":
        day = pd.to_datetime(table[time_field].astype(str).str.slice(0, 10), errors="coerce").dropna()
    else:
        day = pd.to_datetime(table[time_field].astype(str).str.slice(0, 19), errors="coerce").dropna()
    return {
        "expected_symbol": symbol,
        "archive_path": meta["archive_path"],
        "bytes": int(meta["bytes"]),
        "sha256": str(meta["sha256"]),
        "rows": int(pf.metadata.num_rows),
        "physical_fields": [{"name": f.name, "type": str(f.type)} for f in schema],
        "identity_columns_read": ["symbol", time_field],
        "distinct_symbols": symbols,
        "symbol_binding_valid": symbols == [symbol],
        "time_identity_field": time_field,
        "time_identity_non_null_rows": int(len(day)),
        "min_trading_day": day.min().strftime("%Y-%m-%d") if len(day) else None,
        "max_trading_day": day.max().strftime("%Y-%m-%d") if len(day) else None,
        "market_value_columns_read": False,
        "row_level_data_exported": False,
    }


def verify(inputs: Path, results: Path) -> dict:
    identity = load(inputs / "PAIR_INPUT_IDENTITY.json")
    result = load(results / "BINDING_AUDIT.json")
    if identity.get("schema_id") != "risk_tool_v2_future_carrier_binding_input@1.0":
        raise RuntimeError("audit_input_schema_mismatch")
    if identity.get("task_id") != TASK_ID or identity.get("prereg_sha256") != PREREG_SHA256:
        raise RuntimeError("audit_input_identity_mismatch")
    if result.get("schema_id") != SCHEMA_ID or result.get("task_id") != TASK_ID:
        raise RuntimeError("audit_result_schema_mismatch")
    if result.get("profile") != PROFILE or result.get("prereg_sha256") != PREREG_SHA256:
        raise RuntimeError("audit_result_identity_mismatch")
    if result.get("source") != identity.get("source"):
        raise RuntimeError("audit_source_drift")

    members = identity.get("members")
    if not isinstance(members, dict) or set(members) != set(EXPECTED_SYMBOLS):
        raise RuntimeError("audit_member_set_invalid")
    expected_members = {
        symbol: independently_inspect(inputs / "pair" / (symbol + ".parquet"), symbol, members[symbol])
        for symbol in EXPECTED_SYMBOLS
    }
    if result.get("members") != expected_members:
        raise RuntimeError("audit_member_recompute_mismatch")
    valid = all(expected_members[s]["symbol_binding_valid"] for s in EXPECTED_SYMBOLS)
    starts = [expected_members[s]["min_trading_day"] for s in EXPECTED_SYMBOLS if expected_members[s]["min_trading_day"]]
    ends = [expected_members[s]["max_trading_day"] for s in EXPECTED_SYMBOLS if expected_members[s]["max_trading_day"]]
    overlap_start = max(starts) if len(starts) == 2 else None
    overlap_end = min(ends) if len(ends) == 2 else None
    covers = bool(valid and overlap_start and overlap_end and overlap_start <= FUTURE_START and overlap_end >= FUTURE_END)
    if result.get("pair_overlap") != {"min_trading_day": overlap_start, "max_trading_day": overlap_end}:
        raise RuntimeError("audit_overlap_mismatch")
    if result.get("status") != ("PAIR_BINDING_VALID_FOR_SOURCE_FAMILY" if valid else "PAIR_BINDING_INVALID"):
        raise RuntimeError("audit_status_mismatch")
    if result.get("future_oos_window") != {
        "start_inclusive": FUTURE_START,
        "end_inclusive": FUTURE_END,
        "current_snapshot_covers_full_window": covers,
        "current_snapshot_is_future_oos_evidence": False,
    }:
        raise RuntimeError("audit_future_window_mismatch")
    controls = result.get("controls")
    required_controls = {
        "market_values_read": False,
        "returns_or_labels_read": False,
        "model_execution": False,
        "calibration_execution": False,
        "new_training": False,
        "parent_verdict_changed": False,
        "strategy_authority": False,
        "production_authority": False,
    }
    if controls != required_controls:
        raise RuntimeError("audit_control_violation")
    for row in expected_members.values():
        if row["market_value_columns_read"] is not False or row["row_level_data_exported"] is not False:
            raise RuntimeError("audit_export_violation")
    return {
        "status": "passed",
        "binding_status": result["status"],
        "current_snapshot_covers_full_window": covers,
        "production_authority": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.inputs.resolve(), args.results.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()
