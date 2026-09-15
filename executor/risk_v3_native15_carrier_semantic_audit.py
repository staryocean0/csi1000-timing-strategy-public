from __future__ import annotations
import argparse, hashlib, json
from collections import Counter
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq

TASK_ID = "CSI1000-RISK-V3-NATIVE15-PHASE-A-CARRIER-SEMANTIC-AUDIT-V1-20260915"
PROFILE = "risk-v3-native15-carrier-semantic-audit-v1"
SCHEMA_ID = "risk_tool_v3_native15_carrier_semantic_audit_result@1.0"
PREREG_SHA256 = "d8bd50b694256379a07289c1f4587b3428cc36ba9d0e285bde2aa97fc0c8cd09"
PRIMARY = "000852.SH"
REQUIRED_YEARS = (2021, 2022, 2023, 2024, 2025)

def sha256_file(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def load_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError("json_object_required")
    return value

def mode_int(values: pd.Series) -> int | None:
    if values.empty:
        return None
    modes = values.mode()
    return int(modes.iloc[0]) if len(modes) else None

def clock_list(s: pd.Series) -> list[str]:
    return sorted(pd.Series(s.dt.strftime("%H:%M:%S")).dropna().unique().tolist())

def summarize_symbol(z: pd.DataFrame) -> dict:
    by_day = z.groupby("trading_day", sort=True).size()
    mode_day = mode_int(by_day)
    complete = int((by_day == mode_day).sum()) if mode_day is not None else 0
    by_year = {}
    for year, g in z.groupby("year", sort=True):
        d = g.groupby("trading_day").size()
        m = mode_int(d)
        by_year[str(int(year))] = {
            "rows": int(len(g)),
            "trading_days": int(g.trading_day.nunique()),
            "bars_per_day_mode": m,
            "bars_per_day_min": int(d.min()) if len(d) else None,
            "bars_per_day_max": int(d.max()) if len(d) else None,
            "complete_day_share_at_symbol_mode": float((d == m).mean()) if m is not None and len(d) else 0.0,
        }
    return {
        "rows": int(len(z)),
        "first_trading_day": str(z.trading_day.min()),
        "last_trading_day": str(z.trading_day.max()),
        "trading_days": int(z.trading_day.nunique()),
        "bars_per_day_mode": mode_day,
        "bars_per_day_min": int(by_day.min()) if len(by_day) else None,
        "bars_per_day_max": int(by_day.max()) if len(by_day) else None,
        "complete_day_share_at_symbol_mode": float(complete / len(by_day)) if len(by_day) else 0.0,
        "years": by_year,
    }

def build_result(inputs: Path) -> dict:
    ident = load_json(inputs / "DATA_IDENTITY.json")
    prereg = inputs / "PREREG.json"
    if sha256_file(prereg) != PREREG_SHA256:
        raise RuntimeError("prereg_digest_mismatch")
    if ident.get("task_id") != TASK_ID:
        raise RuntimeError("identity_task_mismatch")
    carrier_meta = ident.get("carrier")
    if not isinstance(carrier_meta, dict):
        raise RuntimeError("carrier_identity_missing")
    carrier = inputs / "15m_offset_5.parquet"
    if not carrier.is_file() or carrier.is_symlink():
        raise RuntimeError("carrier_missing")
    if carrier.stat().st_size != carrier_meta.get("bytes") or sha256_file(carrier) != carrier_meta.get("sha256"):
        raise RuntimeError("carrier_identity_mismatch")

    parquet = pq.ParquetFile(carrier)
    names = list(parquet.schema_arrow.names)
    if "symbol" not in names:
        raise RuntimeError("symbol_field_missing")
    time_candidates = [x for x in ("timestamp", "datetime") if x in names]
    if len(time_candidates) != 1:
        raise RuntimeError("time_field_not_unique")
    time_field = time_candidates[0]
    table = parquet.read(columns=[time_field, "symbol"], use_pandas_metadata=False)
    frame = table.to_pandas(ignore_metadata=True)
    raw_time = frame[time_field]
    parsed = pd.to_datetime(raw_time.astype(str).str.slice(0, 19), errors="coerce")
    parse_rate = float(parsed.notna().mean()) if len(parsed) else 0.0
    z = pd.DataFrame({"bar_end": parsed, "symbol": frame["symbol"].astype(str)})
    z = z[z.bar_end.notna()].copy()
    z["trading_day"] = z.bar_end.dt.strftime("%Y-%m-%d")
    z["year"] = z.bar_end.dt.year.astype(int)
    z["session"] = z.bar_end.dt.hour.lt(12).map({True:"AM", False:"PM"})
    z["minute_of_day"] = z.bar_end.dt.hour * 60 + z.bar_end.dt.minute
    z["mod15"] = z.minute_of_day % 15
    duplicates = int(z.duplicated(["symbol","bar_end"]).sum())

    delta_counter = Counter()
    for _, g in z.sort_values(["symbol","trading_day","session","bar_end"]).groupby(["symbol","trading_day","session"], sort=False):
        d = g.bar_end.diff().dropna().dt.total_seconds().div(60).round(6)
        delta_counter.update(float(x) for x in d.tolist())
    delta_total = sum(delta_counter.values())
    share15 = float(delta_counter.get(15.0, 0) / delta_total) if delta_total else 0.0

    session_counts = z.groupby(["symbol","trading_day","session"]).size()
    session_modes = {}
    for symbol in sorted(z.symbol.unique()):
        q = session_counts.loc[symbol] if symbol in session_counts.index.get_level_values(0) else pd.Series(dtype=int)
        session_modes[symbol] = {}
        for sess in ("AM","PM"):
            vals = q.xs(sess, level="session") if len(q) and sess in q.index.get_level_values("session") else pd.Series(dtype=int)
            session_modes[symbol][sess] = {
                "mode": mode_int(vals),
                "min": int(vals.min()) if len(vals) else None,
                "max": int(vals.max()) if len(vals) else None,
            }

    symbols = {s: summarize_symbol(g.copy()) for s,g in z.groupby("symbol", sort=True)}
    primary = symbols.get(PRIMARY)
    required_years_ready = bool(primary) and all(
        str(y) in primary["years"] and primary["years"][str(y)]["trading_days"] >= 200
        for y in REQUIRED_YEARS
    )
    primary_complete = float(primary["complete_day_share_at_symbol_mode"]) if primary else 0.0
    unique_residues = sorted(int(x) for x in z.mod15.dropna().unique().tolist())

    source_manifest = load_json(inputs / "SOURCE_MANIFEST.json")
    manifest_text = json.dumps(source_manifest, sort_keys=True)
    marker_count = manifest_text.count("15m_offset_5")
    structural = {
        "timestamp_parse_rate_ge_09999": parse_rate >= 0.9999,
        "duplicate_rows_eq_0": duplicates == 0,
        "mod15_residue_eq_5": unique_residues == [5],
        "within_session_15m_delta_share_ge_099": share15 >= 0.99,
        "primary_symbol_present": primary is not None,
        "primary_required_years_ge_200_days": required_years_ready,
        "primary_complete_day_share_ge_095": primary_complete >= 0.95,
        "source_manifest_mentions_candidate": marker_count >= 1,
    }
    valid = all(structural.values())

    return {
        "schema_id": SCHEMA_ID,
        "task_id": TASK_ID,
        "profile": PROFILE,
        "prereg_sha256": PREREG_SHA256,
        "status": "NATIVE15_CARRIER_SEMANTICS_VALID" if valid else "NATIVE15_CARRIER_SEMANTICS_NOT_READY",
        "carrier": carrier_meta,
        "schema": {
            "physical_fields": [{"name": f.name, "type": str(f.type)} for f in parquet.schema_arrow],
            "time_field": time_field,
            "symbol_field": "symbol",
            "wallclock_parse": "first_19_chars_no_timezone_conversion",
        },
        "aggregate": {
            "rows_physical": int(parquet.metadata.num_rows),
            "rows_parsed": int(len(z)),
            "timestamp_parse_rate": parse_rate,
            "symbols": symbols,
            "duplicate_symbol_timestamp_rows": duplicates,
            "clock_grid": clock_list(z.bar_end),
            "mod15_residues": unique_residues,
            "within_session_delta_minutes_counts": {str(k): int(v) for k,v in sorted(delta_counter.items())},
            "within_session_15m_delta_share": share15,
            "session_bar_count_summary": session_modes,
        },
        "source_manifest": {
            "identity": ident.get("source_contract"),
            "candidate_marker_count": marker_count,
            "canonical_1m_parent_dataset_version": source_manifest.get("canonical_1m_parent_dataset_version"),
        },
        "technical_acceptance": structural,
        "controls": {
            "market_values_read": False,
            "returns_read": False,
            "labels_read": False,
            "model_execution": False,
            "threshold_search": False,
            "calibration_execution": False,
            "year_2026_threshold_or_model_training": False,
            "pnl": False,
            "strategy_routing": False,
            "position_sizing": False,
            "production_authority": False,
        },
        "next_phase_authorized": bool(valid),
        "next_phase": "native15_descriptive_risk_map_only" if valid else "repair_or_reselect_native15_carrier_before_science",
    }

def run(inputs: Path, out: Path) -> dict:
    if out.exists():
        raise RuntimeError("output_directory_already_exists")
    result = build_result(inputs)
    out.mkdir(parents=True)
    (out / "NATIVE15_CARRIER_SEMANTIC_AUDIT.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    return result

def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a=p.parse_args()
    run(a.inputs.resolve(), a.out.resolve())

if __name__ == "__main__":
    main()
