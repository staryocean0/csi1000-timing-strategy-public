#!/usr/bin/env python3
"""Execute one frozen reusable 2021-2025 BLACKBOX query and persist only its decision token receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logsumexp
from scipy.stats import rankdata

PROTOCOL_SCHEMA = "csi1000.overnight_continuous_driver_tail_likelihood_reusable_blackbox_prereg@1.0"
RECEIPT_SCHEMA = "csi1000.overnight_continuous_driver_tail_likelihood_blackbox_receipt@1.0"
IDENTITY = "overnight_continuous_driver_tail_likelihood_reusable_blackbox_v1"
PARENT_IDENTITY = "overnight_continuous_driver_tail_likelihood_v1"
SOURCE_REPO = "staryocean0/factorlab-overnight-open-lab"
SOURCE_REF = "9905c2f8942ad0a2faf106d42c1b62fd6127e646"
BB_START = pd.Timestamp("2021-01-01")
BB_END = pd.Timestamp("2025-12-31")
FEATURES = ["global_risk_z", "china_offshore_z", "driver_coherence", "log_rvol20"]
CLASS_NAMES = ["DOWN", "MID", "UP"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def git_blob_sha1(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def read_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("json_object_required")
    return value


def validate_protocol(p: dict) -> None:
    if p.get("schema_id") != PROTOCOL_SCHEMA or p.get("research_identity") != IDENTITY:
        raise RuntimeError("protocol_identity")
    if p.get("stage") != "result_free_reusable_blackbox_preregistration":
        raise RuntimeError("protocol_stage")
    source = p.get("blackbox_source", {})
    if source.get("repository") != SOURCE_REPO or source.get("ref") != SOURCE_REF:
        raise RuntimeError("protocol_source")
    if source.get("row_values_inspected_during_preregistration") is not False:
        raise RuntimeError("protocol_source_scope")
    window = p.get("blackbox_window", {})
    if window.get("start") != "2021-01-01" or window.get("end") != "2025-12-31":
        raise RuntimeError("protocol_window")
    if window.get("reused_period_is_independent_oos") is not False or window.get("single_query_for_this_frozen_identity") is not True:
        raise RuntimeError("protocol_reuse_scope")
    model = p.get("frozen_model_application", {})
    if model.get("feature_vector") != FEATURES or model.get("holdout_or_blackbox_information_may_modify_model") is not False:
        raise RuntimeError("protocol_model_scope")
    output = p.get("blackbox_output_contract", {})
    if output.get("public_detail_release") is not False or output.get("internal_metrics_persisted") is not False:
        raise RuntimeError("protocol_output_scope")
    if output.get("row_level_outputs") is not False or output.get("stdout") != "decision token only":
        raise RuntimeError("protocol_output_scope")
    if p.get("production_authority") is not False:
        raise RuntimeError("protocol_production_scope")


def validate_model(model: dict, p: dict) -> None:
    if model.get("schema_id") != "csi1000.overnight_continuous_driver_tail_likelihood_model@1.0":
        raise RuntimeError("model_schema")
    if model.get("research_identity") != PARENT_IDENTITY or model.get("available") is not True:
        raise RuntimeError("model_identity")
    if model.get("features") != FEATURES or model.get("class_order") != CLASS_NAMES:
        raise RuntimeError("model_surface")
    if model.get("model_frozen_before_holdout_evaluation") is not True:
        raise RuntimeError("model_freeze")
    if model.get("blackbox_authorized") is not False or model.get("production_authority") is not False:
        raise RuntimeError("model_scope")
    if model.get("protocol_sha256") != p["parent_development_artifact"]["development_protocol_sha256"]:
        raise RuntimeError("model_protocol_identity")
    for name in FEATURES:
        if name not in model.get("feature_means", {}) or name not in model.get("feature_population_sds", {}):
            raise RuntimeError("model_standardization")
        if name not in model.get("down", {}).get("weights", {}) or name not in model.get("up", {}).get("weights", {}):
            raise RuntimeError("model_weights")
    if set(model.get("fit_class_priors", {})) != set(CLASS_NAMES):
        raise RuntimeError("model_priors")


def verify_source_files(root: Path, p: dict) -> dict[str, str]:
    files = p["blackbox_source"]["files"]
    identities = {}
    for rel, meta in files.items():
        path = root / rel
        if path.is_symlink() or not path.is_file() or path.stat().st_size != meta["bytes"]:
            raise RuntimeError("source_file_identity")
        digest = git_blob_sha1(path)
        if digest != meta["git_blob_sha1"]:
            raise RuntimeError("source_file_digest")
        identities[rel] = digest
    assertions = read_object(root / "data/v6a_external_sources_2015_2025/source_assertions.json")
    required = p["blackbox_source"]["required_source_assertions"]
    if assertions.get("assertions") != required or not all(required.values()):
        raise RuntimeError("source_assertions")
    return identities


def trailing_rms_prev(values: pd.Series) -> pd.Series:
    x = pd.to_numeric(values, errors="coerce")
    return np.sqrt(x.pow(2).shift(1).rolling(window=60, min_periods=20).mean())


def load_panel(path: Path) -> pd.DataFrame:
    cols = ["trading_day", "gap", "rvol20", "holiday_reopen", "us_nasdaq", "us_vix_chg"]
    x = pd.read_parquet(path, columns=cols).copy()
    x["trading_day"] = pd.to_datetime(x["trading_day"], errors="raise").dt.normalize()
    x = x.loc[x["trading_day"].le(BB_END)].sort_values("trading_day", kind="mergesort").reset_index(drop=True)
    if x.empty or x["trading_day"].duplicated().any():
        raise RuntimeError("panel_identity")
    x["previous_china_day"] = x["trading_day"].shift(1)
    return x


def attach_a50(panel: pd.DataFrame, ordinary_path: Path, holiday_path: Path) -> tuple[pd.DataFrame, bool]:
    ordinary = pd.read_parquet(ordinary_path, columns=["trading_day", "a50_ordinary_preauction_closure_return", "target_end_time"]).copy()
    holiday = pd.read_parquet(holiday_path, columns=["trading_day", "a50_holiday_closure_return", "target_end_time"]).copy()
    for frame in (ordinary, holiday):
        frame["trading_day"] = pd.to_datetime(frame["trading_day"], errors="raise").dt.normalize()
        frame.drop(frame.index[frame["trading_day"].gt(BB_END)], inplace=True)
        if frame["trading_day"].duplicated().any():
            raise RuntimeError("a50_duplicate_day")
    ordinary = ordinary.rename(columns={"target_end_time": "ordinary_end_time"})
    holiday = holiday.rename(columns={"target_end_time": "holiday_end_time"})
    out = panel.merge(ordinary, on="trading_day", how="left", validate="one_to_one")
    out = out.merge(holiday, on="trading_day", how="left", validate="one_to_one")
    is_holiday = pd.to_numeric(out["holiday_reopen"], errors="coerce").fillna(0).ne(0)
    ordinary_available = (~is_holiday) & out["a50_ordinary_preauction_closure_return"].notna()
    holiday_available = is_holiday & out["a50_holiday_closure_return"].notna()
    clock_ok = True
    if ordinary_available.any():
        ordinary_times = pd.to_numeric(out.loc[ordinary_available, "ordinary_end_time"], errors="raise").round().astype("int64")
        clock_ok &= bool((ordinary_times < 91500).all())
    if holiday_available.any():
        holiday_times = pd.to_numeric(out.loc[holiday_available, "holiday_end_time"], errors="raise").round().astype("int64")
        clock_ok &= bool((holiday_times < 92500).all())
    out["a50_channel_return"] = np.where(is_holiday, out["a50_holiday_closure_return"], out["a50_ordinary_preauction_closure_return"])
    return out, clock_ok


def attach_hkma(panel: pd.DataFrame, path: Path) -> tuple[pd.DataFrame, bool]:
    x = pd.read_parquet(path, columns=["date", "usdcny_hk"]).copy()
    x["date"] = pd.to_datetime(x["date"], errors="raise").dt.normalize()
    x = x.loc[x["date"].le(BB_END)].copy()
    x["usdcny_hk"] = pd.to_numeric(x["usdcny_hk"], errors="coerce")
    x = x.dropna(subset=["date", "usdcny_hk"]).drop_duplicates("date", keep="last").sort_values("date")
    out = panel.copy()
    dates = x["date"].to_numpy(dtype="datetime64[ns]")
    levels = x["usdcny_hk"].to_numpy(float)
    target = out["trading_day"].to_numpy(dtype="datetime64[ns]")
    prev = out["previous_china_day"].to_numpy(dtype="datetime64[ns]")
    start_idx = np.full(len(out), -1, dtype=int)
    valid_prev = out["previous_china_day"].notna().to_numpy()
    start_idx[valid_prev] = np.searchsorted(dates, prev[valid_prev], side="right") - 1
    end_idx = np.searchsorted(dates, target, side="left") - 1
    valid = valid_prev & (start_idx >= 0) & (end_idx >= start_idx)
    ret = np.full(len(out), np.nan)
    ret[valid] = levels[end_idx[valid]] / levels[start_idx[valid]] - 1.0
    causal = True
    if valid.any():
        causal &= bool(np.all(dates[end_idx[valid]] < target[valid]))
    out["hkma_usdcny_closure_return"] = ret
    return out, causal


def build_coordinates(frame: pd.DataFrame) -> pd.DataFrame:
    x = frame.copy()
    for raw in ["us_nasdaq", "us_vix_chg", "a50_channel_return", "hkma_usdcny_closure_return"]:
        x[raw] = pd.to_numeric(x[raw], errors="coerce")
        x[f"{raw}_rms60_prev"] = trailing_rms_prev(x[raw])
    x["rvol20"] = pd.to_numeric(x["rvol20"], errors="coerce")
    x["global_risk_z"] = 0.5 * (x["us_nasdaq"] / x["us_nasdaq_rms60_prev"] - x["us_vix_chg"] / x["us_vix_chg_rms60_prev"])
    x["china_offshore_z"] = x["a50_channel_return"] / x["a50_channel_return_rms60_prev"]
    x["fx_cny_z"] = -x["hkma_usdcny_closure_return"] / x["hkma_usdcny_closure_return_rms60_prev"]
    denom = x["global_risk_z"].abs() + x["china_offshore_z"].abs() + x["fx_cny_z"].abs()
    x["driver_coherence"] = np.where(np.isfinite(denom) & denom.gt(0), (x["global_risk_z"] + x["china_offshore_z"] + x["fx_cny_z"]) / denom, np.nan)
    x["log_rvol20"] = np.where(x["rvol20"].gt(0), np.log(x["rvol20"]), np.nan)
    x["opening_gap_rvol"] = pd.to_numeric(x["gap"], errors="coerce") / x["rvol20"]
    return x


def class_labels(y: np.ndarray, low: float, high: float) -> np.ndarray:
    out = np.ones(len(y), dtype=np.int64)
    out[y <= low] = 0
    out[y >= high] = 2
    return out


def probabilities(z: np.ndarray, model: dict) -> np.ndarray:
    down_w = np.array([float(model["down"]["weights"][name]) for name in FEATURES])
    up_w = np.array([float(model["up"]["weights"][name]) for name in FEATURES])
    down = float(model["down"]["intercept"]) + z @ down_w
    up = float(model["up"]["intercept"]) + z @ up_w
    logits = np.column_stack([down, np.zeros(len(z)), up]) / float(model["temperature"])
    return np.exp(logits - logsumexp(logits, axis=1, keepdims=True))


def log_loss(y: np.ndarray, probs: np.ndarray) -> float:
    return float(-np.mean(np.log(np.clip(probs[np.arange(len(y)), y], 1e-15, 1.0))))


def brier(y: np.ndarray, probs: np.ndarray) -> float:
    truth = np.eye(3)[y]
    return float(np.mean(np.sum((probs - truth) ** 2, axis=1)))


def binary_auc(y_binary: np.ndarray, score: np.ndarray) -> float:
    yb = np.asarray(y_binary, dtype=bool)
    n_pos = int(yb.sum())
    n_neg = int((~yb).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = rankdata(score, method="average")
    return float((ranks[yb].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def evaluate(source_root: Path, model_path: Path, protocol_path: Path) -> dict:
    p = read_object(protocol_path)
    validate_protocol(p)
    model = read_object(model_path)
    validate_model(model, p)
    source_blobs = verify_source_files(source_root, p)
    panel = load_panel(source_root / "data/development/csi1000_open_pit_panel.parquet")
    panel, a50_ok = attach_a50(
        panel,
        source_root / "data/v6a_external_sources_2015_2025/sgx_a50_ordinary_preauction_endpoints.parquet",
        source_root / "data/v6a_external_sources_2015_2025/sgx_a50_holiday_endpoints.parquet",
    )
    panel, hkma_ok = attach_hkma(panel, source_root / "data/v6a_external_sources_2015_2025/hkma_usdcny_cross.parquet")
    x = build_coordinates(panel)
    bb = x.loc[x["trading_day"].between(BB_START, BB_END)].copy()
    numeric = bb[[*FEATURES, "opening_gap_rvol"]].apply(pd.to_numeric, errors="coerce")
    complete = numeric.notna().all(axis=1) & np.isfinite(numeric.to_numpy(float)).all(axis=1)
    bb = bb.loc[complete].reset_index(drop=True)

    low = float(model["tail_cutoffs"]["q10"])
    high = float(model["tail_cutoffs"]["q90"])
    y = class_labels(bb["opening_gap_rvol"].to_numpy(float), low, high) if len(bb) else np.array([], dtype=np.int64)
    counts = np.bincount(y, minlength=3) if len(y) else np.zeros(3, dtype=int)
    suff = p["internal_evidence_sufficiency"]
    sufficient = a50_ok and hkma_ok and len(bb) >= int(suff["pooled_complete_cases_min"])
    sufficient &= int(counts[0]) >= int(suff["pooled_each_tail_cases_min"]) and int(counts[2]) >= int(suff["pooled_each_tail_cases_min"])
    if sufficient:
        years = bb["trading_day"].dt.year.to_numpy()
        for year in range(2021, 2026):
            mask = years == year
            yc = y[mask]
            year_counts = np.bincount(yc, minlength=3) if len(yc) else np.zeros(3, dtype=int)
            if int(mask.sum()) < int(suff["each_calendar_year_complete_cases_min"]):
                sufficient = False
                break
            if int(year_counts[0]) < int(suff["each_calendar_year_each_tail_cases_min"]) or int(year_counts[2]) < int(suff["each_calendar_year_each_tail_cases_min"]):
                sufficient = False
                break

    decision = "INSUFFICIENT"
    if sufficient:
        means = np.array([float(model["feature_means"][name]) for name in FEATURES])
        sds = np.array([float(model["feature_population_sds"][name]) for name in FEATURES])
        if not np.isfinite(means).all() or not np.isfinite(sds).all() or np.any(sds <= 0):
            raise RuntimeError("model_standardization_invalid")
        z = (bb[FEATURES].to_numpy(float) - means) / sds
        probs = probabilities(z, model)
        priors = np.array([float(model["fit_class_priors"][name]) for name in CLASS_NAMES])
        prior_probs = np.tile(priors, (len(bb), 1))
        ll_model = log_loss(y, probs)
        ll_prior = log_loss(y, prior_probs)
        br_model = brier(y, probs)
        br_prior = brier(y, prior_probs)
        ll_improvement = (ll_prior - ll_model) / ll_prior
        br_improvement = (br_prior - br_model) / br_prior
        auc_down = binary_auc(y == 0, probs[:, 0])
        auc_up = binary_auc(y == 2, probs[:, 2])
        p_down = probs[:, 0]
        p_up = probs[:, 2]
        selected = np.where(p_up > p_down, 2, 0)
        ties = p_up == p_down
        margin = np.abs(p_up - p_down)
        selected_prob = np.where(selected == 2, p_up, p_down)
        selected_prior = np.where(selected == 2, priors[2], priors[0])
        active = (~ties) & (margin >= float(model["directional_margin_threshold"])) & (
            selected_prob >= float(model["minimum_selected_tail_uplift_vs_fit_class_prior"]) * selected_prior
        )
        active_count = int(active.sum())
        active_down = int(np.sum(active & (selected == 0)))
        active_up = int(np.sum(active & (selected == 2)))
        active_coverage = active_count / len(bb)
        active_precision = float(np.mean(y[active] == selected[active])) if active_count else 0.0
        combined_tail_prior = float(priors[0] + priors[2])
        precision_uplift = active_precision / combined_tail_prior if combined_tail_prior > 0 else float("nan")
        gates = p["internal_validation_gates"]
        passed = [
            ll_improvement >= float(gates["pooled_log_loss_relative_improvement_vs_frozen_fit_prior_min"]),
            br_improvement >= float(gates["pooled_multiclass_brier_relative_improvement_vs_frozen_fit_prior_min"]),
            auc_down >= float(gates["pooled_down_one_vs_rest_auc_min"]),
            auc_up >= float(gates["pooled_up_one_vs_rest_auc_min"]),
            float(gates["active_coverage_min"]) <= active_coverage <= float(gates["active_coverage_max"]),
            active_count >= int(gates["active_decisions_min"]),
            active_down >= int(gates["active_each_direction_min"]) and active_up >= int(gates["active_each_direction_min"]),
            precision_uplift >= float(gates["active_directional_tail_precision_uplift_vs_frozen_fit_combined_tail_prior_min"]),
        ]
        decision = "PASS" if all(passed) else "FAIL"

    protocol_sha = sha256_file(protocol_path)
    parent = p["parent_development_artifact"]
    parent_id = f"{parent['private_ref']}:{parent['frozen_model_path']}@{parent['frozen_model_git_blob_sha1']}"
    query_material = {
        "research_identity": IDENTITY,
        "parent_model_artifact_id": parent_id,
        "protocol_sha256": protocol_sha,
        "source_ref": SOURCE_REF,
        "source_file_blob_identities": source_blobs,
    }
    query_id = hashlib.sha256(json.dumps(query_material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]
    return {
        "schema_id": RECEIPT_SCHEMA,
        "query_id": query_id,
        "research_identity": IDENTITY,
        "parent_model_artifact_id": parent_id,
        "decision": decision,
        "protocol_sha256": protocol_sha,
        "source_ref": SOURCE_REF,
        "source_file_blob_identities": source_blobs,
        "public_detail_release": False,
        "internal_metrics_persisted": False,
        "reused_period_is_independent_oos": False,
        "production_authority": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", type=Path, required=True)
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--protocol", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    try:
        receipt = evaluate(args.source_root, args.model, args.protocol)
    except Exception:
        print("blackbox_execution_failed", flush=True)
        return 1
    if args.out.exists():
        raise RuntimeError("output_already_exists")
    args.out.mkdir(parents=True)
    (args.out / "blackbox_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(receipt["decision"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
