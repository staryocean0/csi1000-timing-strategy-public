#!/usr/bin/env python3
"""Execute the frozen development protocol for continuous Overnight tail likelihood."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from scipy.special import logsumexp
from scipy.stats import rankdata

IDENTITY = "overnight_continuous_driver_tail_likelihood_v1"
SCHEMA = "csi1000.overnight_continuous_driver_tail_likelihood_dev@1.0"
MODEL_SCHEMA = "csi1000.overnight_continuous_driver_tail_likelihood_model@1.0"
YEARS = tuple(range(2015, 2021))
FEATURES = ["global_risk_z", "china_offshore_z", "driver_coherence", "log_rvol20"]
CLASS_NAMES = ["DOWN", "MID", "UP"]
FIT_START, FIT_END = pd.Timestamp("2015-01-05"), pd.Timestamp("2018-12-31")
CAL_START, CAL_END = pd.Timestamp("2019-01-02"), pd.Timestamp("2019-12-31")
HOLD_START, HOLD_END = pd.Timestamp("2020-01-02"), pd.Timestamp("2020-12-31")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("json_object_required")
    return value


def validate_protocol(p: dict) -> None:
    if p.get("schema_id") != "csi1000.overnight_continuous_driver_tail_likelihood_prereg@1.0":
        raise RuntimeError("protocol_schema_drift")
    if p.get("research_identity") != IDENTITY or p.get("stage") != "result_free_development_preregistration":
        raise RuntimeError("protocol_identity_drift")
    if p.get("feature_vector") != FEATURES:
        raise RuntimeError("feature_vector_drift")
    norm = p.get("coordinate_normalization", {})
    expected_norm = {"method": "lagged_trailing_RMS", "window": 60, "min_periods": 20, "shift": 1, "current_observation_excluded": True}
    if norm != expected_norm:
        raise RuntimeError("coordinate_normalization_drift")
    target = p.get("target", {})
    if target.get("fit_lower_quantile") != 0.10 or target.get("fit_upper_quantile") != 0.90:
        raise RuntimeError("tail_quantile_drift")
    if target.get("quantile_method") != "linear" or target.get("class_order") != CLASS_NAMES:
        raise RuntimeError("tail_contract_drift")
    splits = p.get("time_splits", {})
    if splits != {
        "fit": "2015-01-05..2018-12-31",
        "calibration": "2019-01-02..2019-12-31",
        "development_holdout": "2020-01-02..2020-12-31",
        "blackbox": "not_authorized_by_this_protocol",
    }:
        raise RuntimeError("time_split_drift")
    model = p.get("model", {})
    required_model = {
        "family": "multinomial_logistic_regression",
        "parameterization": "MID_reference_two_logit_softmax",
        "l2_lambda": 0.01,
        "intercepts_penalized": False,
        "optimizer": "scipy.optimize.minimize_L-BFGS-B",
        "max_iterations": 2000,
        "ftol": 1e-12,
        "gtol": 1e-08,
        "randomness": "none",
    }
    for key, value in required_model.items():
        if model.get(key) != value:
            raise RuntimeError("model_contract_drift")
    cal = p.get("probability_calibration", {})
    if cal.get("method") != "single_temperature_scaling" or cal.get("temperature_lower") != 0.5 or cal.get("temperature_upper") != 3.0:
        raise RuntimeError("calibration_contract_drift")
    abst = p.get("abstention", {})
    if abst.get("minimum_selected_tail_uplift_vs_fit_class_prior") != 1.5:
        raise RuntimeError("abstention_contract_drift")
    if p.get("future_reusable_blackbox", {}).get("authorized_now") is not False:
        raise RuntimeError("blackbox_not_authorized")
    if p.get("new_training") is not True or p.get("production_authority") is not False:
        raise RuntimeError("scope_drift")


def trailing_rms_prev(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce")
    return np.sqrt(x.pow(2).shift(1).rolling(window=60, min_periods=20).mean())


def load_carrier(carrier_root: Path) -> tuple[pd.DataFrame, dict]:
    runtime_root = carrier_root / "data/runtime_text_2015_2025"
    driver_root = carrier_root / "data/driver_runtime_text_2015_2020"
    runtime_manifest = read_json(runtime_root / "manifest.json")
    driver_manifest = read_json(driver_root / "manifest.json")
    if runtime_manifest.get("schema_id") != "overnight_runtime_text_carrier@1.0":
        raise RuntimeError("runtime_manifest_identity")
    if runtime_manifest.get("years") != list(YEARS) or runtime_manifest.get("withheld_years") != [2021, 2022, 2023, 2024, 2025]:
        raise RuntimeError("runtime_year_boundary")
    if driver_manifest.get("schema_id") != "overnight_driver_runtime_text_2015_2020@1.0":
        raise RuntimeError("driver_manifest_identity")
    if driver_manifest.get("withheld_years") != [2021, 2022, 2023, 2024, 2025] or driver_manifest.get("blackbox_opened") is not False:
        raise RuntimeError("driver_year_boundary")

    factor_required = {
        "trading_day", "gap", "rvol20", "us_nasdaq", "us_vix_chg",
    }
    driver_required = {
        "trading_day", "a50_channel_return", "hkma_usdcny_closure_return",
    }
    parts = []
    hashes = {}
    for year in YEARS:
        fp = runtime_root / f"factor_panel_{year}.csv"
        dp = driver_root / f"driver_external_{year}.csv"
        f = pd.read_csv(fp)
        d = pd.read_csv(dp)
        if factor_required.difference(f.columns) or driver_required.difference(d.columns):
            raise RuntimeError("carrier_schema_missing")
        f["trading_day"] = pd.to_datetime(f["trading_day"], errors="raise").dt.normalize()
        d["trading_day"] = pd.to_datetime(d["trading_day"], errors="raise").dt.normalize()
        if not f["trading_day"].dt.year.eq(year).all() or not d["trading_day"].dt.year.eq(year).all():
            raise RuntimeError("carrier_year_crossing")
        merged = f.merge(
            d[["trading_day", "a50_channel_return", "hkma_usdcny_closure_return"]],
            on="trading_day", how="inner", validate="one_to_one",
        )
        parts.append(merged)
        hashes[str(year)] = {
            "factor_panel_sha256": sha256_file(fp),
            "driver_external_sha256": sha256_file(dp),
        }
    x = pd.concat(parts, ignore_index=True).sort_values("trading_day", kind="mergesort").reset_index(drop=True)
    if x["trading_day"].min() != pd.Timestamp("2015-01-05") or x["trading_day"].max() != pd.Timestamp("2020-12-31"):
        raise RuntimeError("carrier_window_drift")
    if x["trading_day"].duplicated().any():
        raise RuntimeError("duplicate_trading_day")
    return x, {
        "runtime_manifest_sha256": sha256_file(runtime_root / "manifest.json"),
        "driver_manifest_sha256": sha256_file(driver_root / "manifest.json"),
        "yearly_inputs": hashes,
    }


def build_coordinates(frame: pd.DataFrame) -> pd.DataFrame:
    x = frame.copy()
    x["rvol20"] = pd.to_numeric(x["rvol20"], errors="coerce")
    for raw in ["us_nasdaq", "us_vix_chg", "a50_channel_return", "hkma_usdcny_closure_return"]:
        x[raw] = pd.to_numeric(x[raw], errors="coerce")
        x[f"{raw}_rms60_prev"] = trailing_rms_prev(x[raw])
    x["global_risk_z"] = 0.5 * (
        x["us_nasdaq"] / x["us_nasdaq_rms60_prev"]
        - x["us_vix_chg"] / x["us_vix_chg_rms60_prev"]
    )
    x["china_offshore_z"] = x["a50_channel_return"] / x["a50_channel_return_rms60_prev"]
    x["fx_cny_z"] = -x["hkma_usdcny_closure_return"] / x["hkma_usdcny_closure_return_rms60_prev"]
    denom = x["global_risk_z"].abs() + x["china_offshore_z"].abs() + x["fx_cny_z"].abs()
    x["driver_coherence"] = np.where(
        np.isfinite(denom) & denom.gt(0),
        (x["global_risk_z"] + x["china_offshore_z"] + x["fx_cny_z"]) / denom,
        np.nan,
    )
    x["log_rvol20"] = np.where(x["rvol20"].gt(0), np.log(x["rvol20"]), np.nan)
    x["opening_gap_rvol"] = pd.to_numeric(x["gap"], errors="coerce") / x["rvol20"]
    cols = [*FEATURES, "opening_gap_rvol"]
    numeric = x[cols].apply(pd.to_numeric, errors="coerce")
    x["complete"] = numeric.notna().all(axis=1) & np.isfinite(numeric.to_numpy(float)).all(axis=1)
    return x


def class_labels(y: np.ndarray, low: float, high: float) -> np.ndarray:
    out = np.ones(len(y), dtype=np.int64)
    out[y <= low] = 0
    out[y >= high] = 2
    return out


def logits_from_theta(z: np.ndarray, theta: np.ndarray) -> np.ndarray:
    design = np.column_stack([np.ones(len(z)), z])
    down = design @ theta[0]
    up = design @ theta[1]
    return np.column_stack([down, np.zeros(len(z)), up])


def probabilities(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    scaled = logits / float(temperature)
    return np.exp(scaled - logsumexp(scaled, axis=1, keepdims=True))


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


def fit_model(z: np.ndarray, y: np.ndarray, p: dict) -> tuple[np.ndarray, object]:
    priors = np.bincount(y, minlength=3).astype(float) / len(y)
    if np.any(priors <= 0):
        raise RuntimeError("fit_class_absent")
    theta0 = np.zeros((2, 1 + z.shape[1]), dtype=float)
    theta0[0, 0] = np.log(priors[0] / priors[1])
    theta0[1, 0] = np.log(priors[2] / priors[1])
    lam = float(p["model"]["l2_lambda"])

    def objective(flat):
        theta = flat.reshape(2, -1)
        logits = logits_from_theta(z, theta)
        probs = probabilities(logits)
        n = len(y)
        loss = log_loss(y, probs) + 0.5 * lam * float(np.sum(theta[:, 1:] ** 2))
        residual = probs.copy()
        residual[np.arange(n), y] -= 1.0
        residual /= n
        design = np.column_stack([np.ones(n), z])
        grad = np.vstack([residual[:, 0] @ design, residual[:, 2] @ design])
        grad[:, 1:] += lam * theta[:, 1:]
        return loss, grad.ravel()

    result = minimize(
        objective,
        theta0.ravel(),
        method="L-BFGS-B",
        jac=True,
        options={
            "maxiter": int(p["model"]["max_iterations"]),
            "ftol": float(p["model"]["ftol"]),
            "gtol": float(p["model"]["gtol"]),
        },
    )
    return np.asarray(result.x, dtype=float).reshape(2, -1), result


def calibrate_temperature(logits: np.ndarray, y: np.ndarray, p: dict) -> tuple[float, object]:
    cfg = p["probability_calibration"]
    def objective(temp):
        return log_loss(y, probabilities(logits, float(temp)))
    result = minimize_scalar(
        objective,
        bounds=(float(cfg["temperature_lower"]), float(cfg["temperature_upper"])),
        method="bounded",
        options={"xatol": float(cfg["xatol"])},
    )
    if not result.success or not np.isfinite(result.x):
        raise RuntimeError("temperature_calibration_failed")
    return float(result.x), result


def split_complete(x: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return x.loc[x["complete"] & x["trading_day"].between(start, end)].copy().reset_index(drop=True)


def count_classes(labels: np.ndarray) -> dict:
    counts = np.bincount(labels, minlength=3)
    return {CLASS_NAMES[i]: int(counts[i]) for i in range(3)}


def execute(carrier_root: Path, protocol_path: Path) -> tuple[dict, dict]:
    p = read_json(protocol_path)
    validate_protocol(p)
    frame, provenance = load_carrier(carrier_root)
    x = build_coordinates(frame)
    fit = split_complete(x, FIT_START, FIT_END)
    cal = split_complete(x, CAL_START, CAL_END)
    hold = split_complete(x, HOLD_START, HOLD_END)
    suff = p["evidence_sufficiency"]

    base_report = {
        "schema_id": SCHEMA,
        "research_identity": IDENTITY,
        "status": "completed",
        "protocol_sha256": sha256_file(protocol_path),
        "private_materialization_run_id": p["private_development_snapshot"]["materialization_public_run_id"],
        "provenance": provenance,
        "complete_cases": {"fit": int(len(fit)), "calibration": int(len(cal)), "holdout": int(len(hold))},
        "blackbox_rows_read": 0,
        "opening_clock_files_read": 0,
        "row_level_predictions_persisted": False,
        "new_training": True,
        "production_authority": False,
    }

    if len(fit) < int(suff["fit_complete_cases_min"]):
        report = {**base_report, "decision": "DEV_INSUFFICIENT", "reason": "fit_complete_cases"}
        return report, {"schema_id": MODEL_SCHEMA, "research_identity": IDENTITY, "available": False, "blackbox_authorized": False, "production_authority": False}

    y_fit_cont = fit["opening_gap_rvol"].to_numpy(float)
    low = float(np.quantile(y_fit_cont, p["target"]["fit_lower_quantile"], method=p["target"]["quantile_method"]))
    high = float(np.quantile(y_fit_cont, p["target"]["fit_upper_quantile"], method=p["target"]["quantile_method"]))
    if not np.isfinite(low) or not np.isfinite(high) or not low < high:
        report = {**base_report, "decision": "DEV_INSUFFICIENT", "reason": "tail_cutoff_degenerate"}
        return report, {"schema_id": MODEL_SCHEMA, "research_identity": IDENTITY, "available": False, "blackbox_authorized": False, "production_authority": False}

    y_fit = class_labels(y_fit_cont, low, high)
    y_cal = class_labels(cal["opening_gap_rvol"].to_numpy(float), low, high)
    y_hold = class_labels(hold["opening_gap_rvol"].to_numpy(float), low, high)
    counts = {"fit": count_classes(y_fit), "calibration": count_classes(y_cal), "holdout": count_classes(y_hold)}
    insufficient = (
        counts["fit"]["DOWN"] < int(suff["fit_each_tail_cases_min"])
        or counts["fit"]["UP"] < int(suff["fit_each_tail_cases_min"])
        or len(cal) < int(suff["calibration_complete_cases_min"])
        or counts["calibration"]["DOWN"] < int(suff["calibration_each_tail_cases_min"])
        or counts["calibration"]["UP"] < int(suff["calibration_each_tail_cases_min"])
        or len(hold) < int(suff["holdout_complete_cases_min"])
        or counts["holdout"]["DOWN"] < int(suff["holdout_each_tail_cases_min"])
        or counts["holdout"]["UP"] < int(suff["holdout_each_tail_cases_min"])
    )
    if insufficient:
        report = {**base_report, "decision": "DEV_INSUFFICIENT", "reason": "class_or_split_sufficiency", "tail_cutoffs": {"q10": low, "q90": high}, "class_counts": counts}
        return report, {"schema_id": MODEL_SCHEMA, "research_identity": IDENTITY, "available": False, "blackbox_authorized": False, "production_authority": False}

    fit_features = fit[FEATURES].to_numpy(float)
    means = fit_features.mean(axis=0)
    sds = fit_features.std(axis=0, ddof=0)
    if not np.isfinite(means).all() or not np.isfinite(sds).all() or np.any(sds <= 0):
        report = {**base_report, "decision": "DEV_INSUFFICIENT", "reason": "fit_feature_standardization_degenerate", "tail_cutoffs": {"q10": low, "q90": high}, "class_counts": counts}
        return report, {"schema_id": MODEL_SCHEMA, "research_identity": IDENTITY, "available": False, "blackbox_authorized": False, "production_authority": False}

    z_fit = (fit_features - means) / sds
    z_cal = (cal[FEATURES].to_numpy(float) - means) / sds
    z_hold = (hold[FEATURES].to_numpy(float) - means) / sds
    theta, opt = fit_model(z_fit, y_fit, p)
    if not np.isfinite(theta).all():
        raise RuntimeError("model_parameter_nonfinite")
    fit_priors = np.bincount(y_fit, minlength=3).astype(float) / len(y_fit)
    cal_logits = logits_from_theta(z_cal, theta)
    temperature, _ = calibrate_temperature(cal_logits, y_cal, p)
    cal_probs = probabilities(cal_logits, temperature)
    cal_margin = np.abs(cal_probs[:, 2] - cal_probs[:, 0])
    margin_threshold = float(np.quantile(cal_margin, 0.80, method="higher"))

    model = {
        "schema_id": MODEL_SCHEMA,
        "research_identity": IDENTITY,
        "available": True,
        "protocol_sha256": sha256_file(protocol_path),
        "features": FEATURES,
        "class_order": CLASS_NAMES,
        "tail_cutoffs": {"q10": low, "q90": high},
        "feature_means": {FEATURES[i]: float(means[i]) for i in range(len(FEATURES))},
        "feature_population_sds": {FEATURES[i]: float(sds[i]) for i in range(len(FEATURES))},
        "fit_class_priors": {CLASS_NAMES[i]: float(fit_priors[i]) for i in range(3)},
        "down": {"intercept": float(theta[0, 0]), "weights": {FEATURES[i]: float(theta[0, i + 1]) for i in range(len(FEATURES))}},
        "up": {"intercept": float(theta[1, 0]), "weights": {FEATURES[i]: float(theta[1, i + 1]) for i in range(len(FEATURES))}},
        "mid_logit": 0.0,
        "temperature": temperature,
        "directional_margin_threshold": margin_threshold,
        "minimum_selected_tail_uplift_vs_fit_class_prior": float(p["abstention"]["minimum_selected_tail_uplift_vs_fit_class_prior"]),
        "model_frozen_before_holdout_evaluation": True,
        "blackbox_authorized": False,
        "production_authority": False,
    }

    hold_logits = logits_from_theta(z_hold, theta)
    hold_probs = probabilities(hold_logits, temperature)
    prior_probs = np.tile(fit_priors, (len(hold), 1))
    ll_model = log_loss(y_hold, hold_probs)
    ll_prior = log_loss(y_hold, prior_probs)
    br_model = brier(y_hold, hold_probs)
    br_prior = brier(y_hold, prior_probs)
    ll_improvement = (ll_prior - ll_model) / ll_prior
    br_improvement = (br_prior - br_model) / br_prior
    auc_down = binary_auc(y_hold == 0, hold_probs[:, 0])
    auc_up = binary_auc(y_hold == 2, hold_probs[:, 2])

    p_down = hold_probs[:, 0]
    p_up = hold_probs[:, 2]
    selected = np.where(p_up > p_down, 2, 0)
    ties = p_up == p_down
    margin = np.abs(p_up - p_down)
    selected_prob = np.where(selected == 2, p_up, p_down)
    selected_prior = np.where(selected == 2, fit_priors[2], fit_priors[0])
    active = (~ties) & (margin >= margin_threshold) & (
        selected_prob >= float(p["abstention"]["minimum_selected_tail_uplift_vs_fit_class_prior"]) * selected_prior
    )
    active_count = int(active.sum())
    active_down = int(np.sum(active & (selected == 0)))
    active_up = int(np.sum(active & (selected == 2)))
    active_coverage = active_count / len(hold)
    if active_count:
        active_precision = float(np.mean(y_hold[active] == selected[active]))
    else:
        active_precision = 0.0
    combined_tail_prior = float(fit_priors[0] + fit_priors[2])
    precision_uplift = active_precision / combined_tail_prior if combined_tail_prior > 0 else float("nan")

    metrics = {
        "holdout_log_loss_model": ll_model,
        "holdout_log_loss_prior": ll_prior,
        "holdout_log_loss_relative_improvement": ll_improvement,
        "holdout_brier_model": br_model,
        "holdout_brier_prior": br_prior,
        "holdout_brier_relative_improvement": br_improvement,
        "holdout_down_auc": auc_down,
        "holdout_up_auc": auc_up,
        "active_count": active_count,
        "active_down_count": active_down,
        "active_up_count": active_up,
        "active_coverage": active_coverage,
        "active_directional_tail_precision": active_precision,
        "fit_combined_tail_prior": combined_tail_prior,
        "active_precision_uplift_vs_fit_combined_tail_prior": precision_uplift,
    }
    gates_cfg = p["development_gates"]
    gates = {
        "model_optimizer_converged": bool(opt.success),
        "log_loss_improvement": ll_improvement >= float(gates_cfg["holdout_log_loss_relative_improvement_vs_prior_min"]),
        "brier_improvement": br_improvement >= float(gates_cfg["holdout_multiclass_brier_relative_improvement_vs_prior_min"]),
        "down_auc": auc_down >= float(gates_cfg["holdout_down_one_vs_rest_auc_min"]),
        "up_auc": auc_up >= float(gates_cfg["holdout_up_one_vs_rest_auc_min"]),
        "active_coverage": float(gates_cfg["active_coverage_min"]) <= active_coverage <= float(gates_cfg["active_coverage_max"]),
        "active_decisions": active_count >= int(gates_cfg["active_decisions_min"]),
        "active_each_direction": active_down >= int(gates_cfg["active_each_direction_min"]) and active_up >= int(gates_cfg["active_each_direction_min"]),
        "active_precision_uplift": precision_uplift >= float(gates_cfg["active_directional_tail_precision_uplift_vs_fit_combined_tail_prior_min"]),
    }
    decision = "DEV_PASS" if all(gates.values()) else "DEV_NO_PROGRESS"
    report = {
        **base_report,
        "decision": decision,
        "tail_cutoffs": {"q10": low, "q90": high},
        "class_counts": counts,
        "model_optimizer": {"success": bool(opt.success), "iterations": int(getattr(opt, "nit", 0))},
        "frozen_model_sha256": None,
        "metrics": metrics,
        "gates": gates,
        "blackbox_authorized": False,
        "automatic_successor_authorized": False,
    }
    return report, model


def write_outputs(out: Path, report: dict, model: dict) -> None:
    if out.exists():
        raise RuntimeError("output_already_exists")
    out.mkdir(parents=True)
    model_path = out / "frozen_model.json"
    model_path.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = dict(report)
    report["frozen_model_sha256"] = sha256_file(model_path)
    (out / "dev_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--carrier-root", type=Path, required=True)
    ap.add_argument("--protocol", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    report, model = execute(args.carrier_root, args.protocol)
    write_outputs(args.out, report, model)
    print(report["decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
