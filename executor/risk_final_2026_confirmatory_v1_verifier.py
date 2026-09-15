from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_fresh_verify", HERE / "risk_phase1b_fresh_oos_verifier.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("fresh_oos_verifier_base_unavailable")
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


def validate_inputs(inputs: Path) -> tuple[dict, dict, dict]:
    receipt = load_json(inputs / "CARRIER_IDENTITY.json")
    if receipt.get("schema_id") != CARRIER_SCHEMA_ID or receipt.get("task_id") != TASK_ID:
        raise RuntimeError("carrier_receipt_identity_mismatch")
    if receipt.get("year_2026_semantic_read_before_guard") is not False:
        raise RuntimeError("carrier_pre_guard_flag_invalid")
    rows = receipt.get("files")
    if not isinstance(rows, dict) or set(rows) != set(FILES):
        raise RuntimeError("carrier_receipt_file_set_mismatch")
    for rel, expected in FILES.items():
        path = inputs / rel
        if not path.is_file() or path.is_symlink() or path.stat().st_size != expected["bytes"]:
            raise RuntimeError(f"carrier_file_invalid:{rel}")
        if git_blob_sha1(path) != expected["blob"]:
            raise RuntimeError(f"carrier_blob_mismatch:{rel}")
        digest = sha256_file(path)
        if expected.get("sha256") and digest != expected["sha256"]:
            raise RuntimeError(f"carrier_sha256_mismatch:{rel}")
        if rows[rel].get("bytes") != expected["bytes"] or rows[rel].get("git_blob_sha1") != expected["blob"] or rows[rel].get("sha256") != digest:
            raise RuntimeError(f"carrier_receipt_row_mismatch:{rel}")

    model_path = inputs / "MODEL_FREEZE.json"
    calibration_path = inputs / "CALIBRATION_FREEZE.json"
    if sha256_file(model_path) != MODEL_FREEZE_SHA256:
        raise RuntimeError("model_freeze_digest_mismatch")
    if sha256_file(calibration_path) != CALIBRATION_FREEZE_SHA256:
        raise RuntimeError("calibration_freeze_digest_mismatch")
    model = load_json(model_path)
    calibration = load_json(calibration_path)
    if model.get("schema_id") != "risk_tool_v2_model_freeze@1.0" or model.get("development_years") != [2021, 2022, 2023] or float(model.get("ridge_lambda")) != 0.01 or model.get("audit_retuning") is not False:
        raise RuntimeError("model_freeze_contract_mismatch")
    if calibration.get("method") != "Platt" or float(calibration.get("slope_ridge_lambda")) != 1e-6 or calibration.get("year_2026_read") is not False:
        raise RuntimeError("calibration_freeze_contract_mismatch")
    return receipt, model, calibration


def normalize_1m(frame: pd.DataFrame, year: int) -> pd.DataFrame:
    required = {"trading_day", "timestamp", "close"}
    if not required.issubset(frame.columns):
        raise RuntimeError("guard_one_minute_columns_missing")
    z = pd.DataFrame({
        "trading_day": pd.to_datetime(frame["trading_day"], errors="coerce").dt.strftime("%Y-%m-%d"),
        "timestamp": pd.to_datetime(frame["timestamp"].astype(str).str.slice(0, 19), errors="coerce"),
        "close": pd.to_numeric(frame["close"], errors="coerce"),
    }).dropna()
    return z[pd.to_datetime(z.trading_day).dt.year.eq(year)].sort_values(["trading_day", "timestamp"], kind="stable").reset_index(drop=True)


def independently_synthesize_5m(frame: pd.DataFrame, year: int) -> pd.DataFrame:
    z = normalize_1m(frame, year)
    rows = []
    for day_name, day0 in z.groupby("trading_day", sort=True):
        day = day0.sort_values("timestamp", kind="stable").reset_index(drop=True)
        am = day[day.timestamp.dt.hour < 12].reset_index(drop=True)
        pm = day[day.timestamp.dt.hour >= 12].reset_index(drop=True)
        if len(day) != 240 or len(am) != 120 or len(pm) != 120:
            raise RuntimeError("guard_one_minute_session_shape_invalid")
        for session in (am, pm):
            selected = session.iloc[np.arange(4, 120, 5)]
            for row in selected.itertuples(index=False):
                rows.append((day_name, pd.Timestamp(row.timestamp), float(row.close)))
    return pd.DataFrame(rows, columns=["trading_day", "timestamp", "close"])


def independently_verify_guard(inputs: Path) -> dict:
    output = {"guard_year": 2023, "max_abs_close_diff_limit": 1e-9, "symbols": {}, "passed": True}
    for symbol in base.SYMBOLS:
        one = pd.read_parquet(inputs / "guard_1m" / symbol / "2023.parquet")
        native = pd.read_parquet(inputs / "guard_5m" / symbol / "2023.parquet")
        synth = independently_synthesize_5m(one, 2023)
        a = pd.DataFrame({
            "trading_day": synth.trading_day.astype(str),
            "bar_end": pd.to_datetime(synth.timestamp),
            "close": pd.to_numeric(synth.close),
        }).sort_values(["trading_day", "bar_end"], kind="stable").reset_index(drop=True)
        b = pd.DataFrame({
            "trading_day": pd.to_datetime(native["trading_day"], errors="coerce").dt.strftime("%Y-%m-%d"),
            "bar_end": pd.to_datetime(native["timestamp"].astype(str).str.slice(0, 19), errors="coerce"),
            "close": pd.to_numeric(native["close"], errors="coerce"),
        }).dropna().sort_values(["trading_day", "bar_end"], kind="stable").reset_index(drop=True)
        if list(a.trading_day.unique()) != list(b.trading_day.unique()):
            raise RuntimeError(f"guard_day_support_mismatch:{symbol}")
        ca = a.groupby("trading_day").size(); cb = b.groupby("trading_day").size()
        if not ca.equals(cb) or len(ca[ca != 48]) or len(a) != len(b):
            raise RuntimeError(f"guard_row_count_mismatch:{symbol}")
        if not a.bar_end.equals(b.bar_end):
            raise RuntimeError(f"guard_timestamp_mismatch:{symbol}")
        diff = float(np.max(np.abs(a.close.to_numpy(float) - b.close.to_numpy(float))))
        if not np.isfinite(diff) or diff > 1e-9:
            raise RuntimeError(f"guard_close_mismatch:{symbol}")
        output["symbols"][symbol] = {"rows": int(len(a)), "days": int(len(ca)), "max_abs_close_diff": diff, "passed": True}
    return output


def tail_compress(probability: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(probability, float), base.PLATT_CLIP, 1.0 - base.PLATT_CLIP)
    a = float(np.log(TAIL_ANCHOR_RATE / (1.0 - TAIL_ANCHOR_RATE)))
    z = np.log(p / (1.0 - p))
    z2 = a + TAIL_LIMIT * np.tanh((z - a) / TAIL_LIMIT)
    z2 = np.clip(z2, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-z2))


def verify_frozen_scores(scored: pd.DataFrame, model: dict, calibration: dict) -> None:
    for horizon in base.HORIZONS:
        models = model.get("models", {}).get(str(horizon))
        fits = calibration.get("fits", {}).get(str(horizon), {}).get("audit")
        if not isinstance(models, dict) or set(models) != {"B", "C"} or not isinstance(fits, dict) or set(fits) != {"B", "C"}:
            raise RuntimeError(f"frozen_horizon_input_missing:{horizon}")
        b_raw = base.predict_frozen(models["B"], scored)
        c_raw = base.predict_frozen(models["C"], scored)
        b_cal = base.apply_platt(fits["B"], b_raw)
        c_cal = base.apply_platt(fits["C"], c_raw)
        if horizon == 15:
            c_cal = tail_compress(c_cal)
        expected = {
            f"p_B_raw_{horizon}m": b_raw,
            f"p_C_raw_{horizon}m": c_raw,
            f"p_B_cal_{horizon}m": b_cal,
            f"p_C_cal_{horizon}m": c_cal,
        }
        for column, values in expected.items():
            if column not in scored or not base.close(scored[column].to_numpy(float), values):
                raise RuntimeError(f"frozen_score_mismatch:{column}")


def map_horizon(result: dict) -> dict:
    result = dict(result)
    result["status"] = {
        "OUT_OF_SUPPORTED_FRESH_OOS": "OUT_OF_SUPPORTED_CONFIRMATORY_2026",
        "FRESH_OOS_VALIDATED": "CONFIRMATORY_2026_VALIDATED",
        "FRESH_OOS_NOT_VALIDATED": "CONFIRMATORY_2026_NOT_VALIDATED",
    }.get(result.get("status"), result.get("status"))
    result["scientific_support"] = result["status"] == "CONFIRMATORY_2026_VALIDATED"
    return result


def verify(inputs: Path, results: Path) -> dict:
    expected_files = {"CONFIRMATORY_SCORED.parquet", "SUMMARY.json", "EQUIVALENCE_GUARD.json", "INPUT_DATA_RECEIPT.json"}
    present = {p.name for p in results.iterdir() if p.is_file()}
    if present != expected_files:
        raise RuntimeError("result_file_set_mismatch")
    carrier, model, calibration = validate_inputs(inputs)
    output_receipt = load_json(results / "INPUT_DATA_RECEIPT.json")
    base.compare_tree(output_receipt, carrier, "input_data_receipt")
    guard = independently_verify_guard(inputs)
    base.compare_tree(load_json(results / "EQUIVALENCE_GUARD.json"), guard, "equivalence_guard")

    scored = pd.read_parquet(results / "CONFIRMATORY_SCORED.parquet")
    if scored.empty or set(scored.symbol.dropna().unique()) != set(base.SYMBOLS) or set(scored.year.dropna().astype(int).unique()) != {2026}:
        raise RuntimeError("scored_scope_mismatch")
    verify_frozen_scores(scored, model, calibration)

    horizons = {str(h): map_horizon(base.recompute_horizon(scored, h, base.BOOTSTRAP_REPS)) for h in base.HORIZONS}
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

    expected = {
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
    base.compare_tree(load_json(results / "SUMMARY.json"), expected, "summary")
    return expected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    verified = verify(args.inputs.resolve(), args.results.resolve())
    print(json.dumps({"status": "passed", "overall_status": verified["overall_status"], "production_authority": False}, sort_keys=True))


if __name__ == "__main__":
    main()
