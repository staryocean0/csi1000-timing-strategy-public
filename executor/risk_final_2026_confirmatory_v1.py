from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_fresh_base", HERE / "risk_phase1b_fresh_oos_eval.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("fresh_oos_base_unavailable")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

TASK_ID = "CSI1000-RISK-V2-FINAL-2026-CONFIRMATORY-V1-20260915"
SCHEMA_ID = "risk_tool_v2_final_2026_confirmatory_result@1.0"
CARRIER_SCHEMA_ID = "risk_tool_v2_final_2026_carrier_identity@1.0"
MODEL_FREEZE_SHA256 = "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551"
CALIBRATION_FREEZE_SHA256 = "74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909"
TAIL_ANCHOR_RATE = 0.2312353159391616
TAIL_LIMIT = 4.0
TAIL_SELECTION_RUN = "34920654435-1"

base.CALIBRATION_FREEZE_SHA256 = CALIBRATION_FREEZE_SHA256

# All public market bytes are pinned by Git blob identity before deserialization.
FILES = {
    "fresh_1m/000688.SH/2026.parquet": {"bytes": 584376, "blob": "4626fb307bbcae1c417ddcd69ac694cf322c8bbc", "sha256": "b7e7e9a9e85b738d661583dcd3d7dab158562fddac4355362cc37597db21eca4"},
    "fresh_1m/000852.SH/2026.parquet": {"bytes": 707905, "blob": "8de5cd3caab99dbacae229a2c87f15c4ff2f8558", "sha256": "60b2054d2055bef8010a9948a0589bc1c4b0bb18dd6f373a9366f97e689fdf87"},
    "guard_1m/000688.SH/2023.parquet": {"bytes": 1156684, "blob": "6dc7de6de7fe04233566b2a1743de66b054df18b"},
    "guard_1m/000852.SH/2023.parquet": {"bytes": 1507783, "blob": "a915cc9a0e9259e2660558c07ffbe1d6c37c0e8f"},
    "guard_5m/000688.SH/2023.parquet": {"bytes": 309025, "blob": "02c3a9474dff4e5203cec12ca7a24a3b2be8994b"},
    "guard_5m/000852.SH/2023.parquet": {"bytes": 342750, "blob": "0b17d76b150bfd15d45158f100748898e72089b1"},
    "market/000688.SH/2025.parquet": {"bytes": 320754, "blob": "32d6d1754f965dd6298c885e30b244b877d694ed", "sha256": "bb0b3a5747f11bf5e8908ac169185b582213fcc83a74567e683a56410ceb8511"},
    "market/000852.SH/2025.parquet": {"bytes": 353882, "blob": "85159b9fa1b2b6854b1a0f04faa9f963e9d04c13", "sha256": "5fbecf49d76cd2560e7db5af280b60c012a440a6e69ba6b8306acbbbd4e49333"},
}


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def git_blob_sha1(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"json_object_required:{path.name}")
    return value


def validate_carrier(inputs: Path) -> dict:
    receipt_path = inputs / "CARRIER_IDENTITY.json"
    receipt = load_json(receipt_path)
    if receipt.get("schema_id") != CARRIER_SCHEMA_ID or receipt.get("task_id") != TASK_ID:
        raise RuntimeError("carrier_receipt_identity_mismatch")
    if receipt.get("year_2026_semantic_read_before_guard") is not False:
        raise RuntimeError("carrier_pre_guard_semantic_read_flag_invalid")
    got_files = receipt.get("files")
    if not isinstance(got_files, dict) or set(got_files) != set(FILES):
        raise RuntimeError("carrier_receipt_file_set_mismatch")
    for rel, expected in FILES.items():
        path = inputs / rel
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"carrier_file_missing:{rel}")
        if path.stat().st_size != expected["bytes"]:
            raise RuntimeError(f"carrier_size_mismatch:{rel}")
        if git_blob_sha1(path) != expected["blob"]:
            raise RuntimeError(f"carrier_blob_mismatch:{rel}")
        if "sha256" in expected and sha256_file(path) != expected["sha256"]:
            raise RuntimeError(f"carrier_sha256_mismatch:{rel}")
        row = got_files[rel]
        if row.get("bytes") != expected["bytes"] or row.get("git_blob_sha1") != expected["blob"]:
            raise RuntimeError(f"carrier_receipt_row_mismatch:{rel}")
        if row.get("sha256") != sha256_file(path):
            raise RuntimeError(f"carrier_receipt_sha256_mismatch:{rel}")
    return receipt


def one_minute_source(frame: pd.DataFrame, symbol: str, year: int) -> pd.DataFrame:
    required = {"trading_day", "timestamp", "close"}
    if not required.issubset(frame.columns):
        raise RuntimeError(f"one_minute_columns_missing:{symbol}:{year}")
    z = pd.DataFrame({
        "trading_day": pd.to_datetime(frame["trading_day"], errors="coerce").dt.strftime("%Y-%m-%d"),
        "timestamp": base.wallclock(frame["timestamp"]),
        "close": pd.to_numeric(frame["close"], errors="coerce"),
    }).dropna()
    z = z[pd.to_datetime(z.trading_day).dt.year.eq(year)].copy()
    z = z.sort_values(["trading_day", "timestamp"], kind="stable").reset_index(drop=True)
    if z.empty:
        raise RuntimeError(f"one_minute_source_empty:{symbol}:{year}")
    return z


def synthesize_5m(frame: pd.DataFrame, symbol: str, year: int) -> pd.DataFrame:
    z = one_minute_source(frame, symbol, year)
    out: list[dict] = []
    for day_name, day0 in z.groupby("trading_day", sort=True):
        day = day0.sort_values("timestamp", kind="stable").reset_index(drop=True)
        if len(day) != 240:
            raise RuntimeError(f"one_minute_non_240_day:{symbol}:{day_name}")
        morning = day[day.timestamp.dt.hour < 12].reset_index(drop=True)
        afternoon = day[day.timestamp.dt.hour >= 12].reset_index(drop=True)
        if len(morning) != 120 or len(afternoon) != 120:
            raise RuntimeError(f"one_minute_session_shape_invalid:{symbol}:{day_name}")
        for session in (morning, afternoon):
            for start in range(0, 120, 5):
                fifth = session.iloc[start + 4]
                out.append({
                    "trading_day": day_name,
                    "timestamp": pd.Timestamp(fifth.timestamp),
                    "close": float(fifth.close),
                })
    result = pd.DataFrame(out)
    counts = result.groupby("trading_day").size()
    if result.empty or len(counts[counts != 48]):
        raise RuntimeError(f"synthesized_5m_shape_invalid:{symbol}:{year}")
    return result


def equivalence_guard(inputs: Path) -> dict:
    result = {"guard_year": 2023, "max_abs_close_diff_limit": 1e-9, "symbols": {}, "passed": True}
    for symbol in base.SYMBOLS:
        one = pd.read_parquet(inputs / "guard_1m" / symbol / "2023.parquet")
        native = pd.read_parquet(inputs / "guard_5m" / symbol / "2023.parquet")
        synth = synthesize_5m(one, symbol, 2023)
        a = base.normalize_source(synth, symbol, 2023)
        b = base.normalize_source(native, symbol, 2023)
        days_a = list(a.trading_day.unique())
        days_b = list(b.trading_day.unique())
        if days_a != days_b:
            raise RuntimeError(f"equivalence_day_support_mismatch:{symbol}")
        ca = a.groupby("trading_day").size()
        cb = b.groupby("trading_day").size()
        if not ca.equals(cb) or len(ca[ca != 48]):
            raise RuntimeError(f"equivalence_row_count_mismatch:{symbol}")
        if len(a) != len(b) or not a.bar_end.reset_index(drop=True).equals(b.bar_end.reset_index(drop=True)):
            raise RuntimeError(f"equivalence_timestamp_mismatch:{symbol}")
        diff = float(np.max(np.abs(a.close.to_numpy(float) - b.close.to_numpy(float)))) if len(a) else float("inf")
        if not np.isfinite(diff) or diff > 1e-9:
            raise RuntimeError(f"equivalence_close_mismatch:{symbol}:{diff}")
        result["symbols"][symbol] = {"rows": int(len(a)), "days": int(len(days_a)), "max_abs_close_diff": diff, "passed": True}
    return result


def tail_compress(probability: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(probability, float), base.PLATT_CLIP, 1.0 - base.PLATT_CLIP)
    a = float(np.log(TAIL_ANCHOR_RATE / (1.0 - TAIL_ANCHOR_RATE)))
    z = np.log(p / (1.0 - p))
    z2 = a + TAIL_LIMIT * np.tanh((z - a) / TAIL_LIMIT)
    z2 = np.clip(z2, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-z2))


def score_final_candidate(cohort: pd.DataFrame, model_freeze: dict, calibration_freeze: dict) -> pd.DataFrame:
    scored = base.score_cohort(cohort, model_freeze, calibration_freeze)
    scored["p_C_cal_15m"] = tail_compress(scored["p_C_cal_15m"].to_numpy(float))
    return scored


def map_horizon(result: dict) -> dict:
    result = dict(result)
    status = result.get("status")
    mapping = {
        "OUT_OF_SUPPORTED_FRESH_OOS": "OUT_OF_SUPPORTED_CONFIRMATORY_2026",
        "FRESH_OOS_VALIDATED": "CONFIRMATORY_2026_VALIDATED",
        "FRESH_OOS_NOT_VALIDATED": "CONFIRMATORY_2026_NOT_VALIDATED",
    }
    result["status"] = mapping.get(status, status)
    result["scientific_support"] = result["status"] == "CONFIRMATORY_2026_VALIDATED"
    return result


def run(inputs: Path, out: Path) -> dict:
    if out.exists():
        raise RuntimeError("output_directory_already_exists")
    carrier = validate_carrier(inputs)
    model_freeze, calibration_freeze = base.validate_authority_inputs(inputs)
    warmup_paths = base.validate_warmup(inputs)

    # The 2023 equivalence guard must complete before any 2026 parquet deserialization.
    guard = equivalence_guard(inputs)
    if guard.get("passed") is not True:
        raise RuntimeError("equivalence_guard_failed")

    frames: dict[tuple[str, int], pd.DataFrame] = {}
    for symbol in base.SYMBOLS:
        frames[(symbol, base.WARMUP_YEAR)] = pd.read_parquet(warmup_paths[symbol])
        one_2026 = pd.read_parquet(inputs / "fresh_1m" / symbol / "2026.parquet")
        frames[(symbol, base.FRESH_YEAR)] = synthesize_5m(one_2026, symbol, base.FRESH_YEAR)

    states = base.build_state_rows(frames)
    cohort = base.build_fresh_cohort(states)
    scored = score_final_candidate(cohort, model_freeze, calibration_freeze)
    horizons = {str(h): map_horizon(base.evaluate_horizon(scored, h)) for h in base.HORIZONS}
    supported = sum(horizons[str(h)]["status"] != "OUT_OF_SUPPORTED_CONFIRMATORY_2026" for h in base.HORIZONS)
    validated = sum(horizons[str(h)]["status"] == "CONFIRMATORY_2026_VALIDATED" for h in base.HORIZONS)
    passing = [h for h in base.HORIZONS if horizons[str(h)]["status"] == "CONFIRMATORY_2026_VALIDATED"]
    if supported == 0:
        overall = "RISK_TOOL_V2_CLOSED_INSUFFICIENT_CONFIRMATORY_SUPPORT"
    elif validated == 2:
        overall = "LAYER2_CONFIRMATORY_FULL_VALIDATION"
    elif validated == 1:
        overall = "LAYER2_CONFIRMATORY_PARTIAL_VALIDATION"
    else:
        overall = "RISK_TOOL_V2_CLOSED_NOT_VALIDATED"

    result = {
        "schema_id": SCHEMA_ID,
        "task_id": TASK_ID,
        "confirmatory_year": 2026,
        "confirmatory_as_of_end": "2026-08-21",
        "fresh_oos_claim": False,
        "full_calendar_year_claim": False,
        "horizons_minutes": list(base.HORIZONS),
        "model_freeze_sha256": MODEL_FREEZE_SHA256,
        "calibration_freeze_sha256": CALIBRATION_FREEZE_SHA256,
        "carrier_identity_sha256": sha256_file(inputs / "CARRIER_IDENTITY.json"),
        "candidate_15m": {"raw_scores": "frozen", "B_calibration": "phase1b_audit_platt", "C_calibration": "phase1b_audit_platt_then_tail_L_4", "tail_anchor_event_rate": TAIL_ANCHOR_RATE, "tail_limit": TAIL_LIMIT, "selection_authority_run": TAIL_SELECTION_RUN},
        "candidate_30m": {"raw_scores": "frozen", "B_calibration": "phase1b_audit_platt", "C_calibration": "phase1b_audit_platt"},
        "synthesis_equivalence_guard": guard,
        "year_2026_semantic_read": True,
        "parent_model_refit": False,
        "calibrator_refit": False,
        "sensor_retuning": False,
        "cohort_retuning": False,
        "support_gate_retuning": False,
        "alternate_carrier_used": False,
        "historical_hierarchical_v1_result_rewritten": False,
        "historical_hierarchical_v1_status": "TS-I",
        "carrier": carrier,
        "horizons": horizons,
        "eligible_layer3_research_horizons": passing,
        "overall_status": overall,
        "task_closed_after_this_run": True,
        "automatic_successor_allowed": False,
        "production_authority": False,
    }
    out.mkdir(parents=True)
    scored.to_parquet(out / "CONFIRMATORY_SCORED.parquet", index=False)
    (out / "EQUIVALENCE_GUARD.json").write_text(json.dumps(base.clean(guard), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "INPUT_DATA_RECEIPT.json").write_text(json.dumps(base.clean(carrier), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "SUMMARY.json").write_text(json.dumps(base.clean(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.inputs.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
