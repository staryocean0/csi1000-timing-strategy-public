from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

TASK_ID = "CSI1000-RISK-V2-PHASE1B-FRESH-OOS-2026-V1-20260914"
SCHEMA_ID = "risk_tool_v2_phase1b_fresh_oos_result@1.0"
IDENTITY_SCHEMA_ID = "risk_tool_v2_phase1b_fresh_oos_data_identity@1.0"
SYMBOLS = ("000688.SH", "000852.SH")
HORIZONS = (15, 30)
FRESH_YEAR = 2026
STATES = ("UNSAFE", "RECOVERING")
AGE_BUCKETS = ("LT15", "M15_25", "M30_40", "GE45")
REFERENCE_CELL = "UNSAFE|LT15"
MODEL_FREEZE_SHA256 = "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551"
CALIBRATION_FREEZE_SHA256 = "75d553d411f66842be8716acbe96d56de036e060c4097cc06e9e6a2333fa3a9b"
WARMUP = {
    "000688.SH": {
        "bytes": 320754,
        "sha256": "bb0b3a5747f11bf5e8908ac169185b582213fcc83a74567e683a56410ceb8511",
    },
    "000852.SH": {
        "bytes": 353882,
        "sha256": "5fbecf49d76cd2560e7db5af280b60c012a440a6e69ba6b8306acbbbd4e49333",
    },
}
BOOTSTRAP_REPS = 5000
BOOTSTRAP_SEED = 20260914
FAMILY_SIZE = 6
BONFERRONI_LOWER_QUANTILE = 0.05 / FAMILY_SIZE
PLATT_CLIP = 1e-6
LOGLOSS_CLIP = 1e-12
ATOL = 1e-11


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"json_object_required:{path.name}")
    return value


def close(a, b, atol: float = ATOL) -> bool:
    return bool(np.allclose(np.asarray(a, dtype=float), np.asarray(b, dtype=float), rtol=0.0, atol=atol, equal_nan=True))


def validate_inputs(inputs: Path) -> tuple[dict, dict, dict]:
    identity_path = inputs / "DATA_IDENTITY.json"
    model_path = inputs / "MODEL_FREEZE.json"
    calibration_path = inputs / "CALIBRATION_FREEZE.json"
    if sha256_file(model_path) != MODEL_FREEZE_SHA256:
        raise RuntimeError("model_freeze_digest_mismatch")
    if sha256_file(calibration_path) != CALIBRATION_FREEZE_SHA256:
        raise RuntimeError("calibration_freeze_digest_mismatch")
    identity = load_json(identity_path)
    model = load_json(model_path)
    calibration = load_json(calibration_path)
    if identity.get("schema_id") != IDENTITY_SCHEMA_ID or identity.get("task_id") != TASK_ID:
        raise RuntimeError("identity_receipt_schema_or_task_mismatch")
    if identity.get("canonical_repository") != "staryocean0/factorlab-trend-reversion-regime-lab":
        raise RuntimeError("identity_repository_mismatch")
    if identity.get("year_2026_semantic_read_before_identity_commit") is not False:
        raise RuntimeError("identity_precommit_semantic_read_not_false")
    rows = identity.get("files")
    if not isinstance(rows, list) or len(rows) != 2:
        raise RuntimeError("identity_file_set_invalid")
    expected_paths = {
        "000688.SH": "data/market/5m/000688.SH/2026.parquet",
        "000852.SH": "data/market/5m/000852.SH/2026.parquet",
    }
    seen = set()
    for row in rows:
        required = {
            "symbol", "canonical_repository", "immutable_source_commit", "path",
            "git_blob_sha1", "bytes", "sha256",
        }
        if not isinstance(row, dict) or not required.issubset(row):
            raise RuntimeError("identity_file_row_invalid")
        symbol = row["symbol"]
        if symbol not in SYMBOLS or symbol in seen:
            raise RuntimeError("identity_symbol_set_invalid")
        if row["canonical_repository"] != identity["canonical_repository"] or row["path"] != expected_paths[symbol]:
            raise RuntimeError("identity_path_or_repository_mismatch")
        local = inputs / "market" / symbol / "2026.parquet"
        if (
            not local.is_file()
            or local.is_symlink()
            or local.stat().st_size != row["bytes"]
            or sha256_file(local) != row["sha256"]
        ):
            raise RuntimeError("fresh_oos_file_identity_mismatch")
        seen.add(symbol)
    if seen != set(SYMBOLS):
        raise RuntimeError("identity_symbol_set_incomplete")
    for symbol, meta in WARMUP.items():
        path = inputs / "market" / symbol / "2025.parquet"
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != meta["bytes"]
            or sha256_file(path) != meta["sha256"]
        ):
            raise RuntimeError(f"warmup_identity_mismatch:{symbol}")
    if model.get("schema_id") != "risk_tool_v2_model_freeze@1.0":
        raise RuntimeError("model_freeze_schema_mismatch")
    if model.get("development_years") != [2021, 2022, 2023] or float(model.get("ridge_lambda")) != 0.01:
        raise RuntimeError("model_freeze_training_contract_mismatch")
    if model.get("audit_retuning") is not False:
        raise RuntimeError("model_freeze_retuning_flag_invalid")
    if calibration.get("method") != "Platt" or float(calibration.get("slope_ridge_lambda")) != 1e-6:
        raise RuntimeError("calibration_freeze_contract_mismatch")
    if calibration.get("year_2026_read") is not False:
        raise RuntimeError("calibration_freeze_2026_flag_invalid")
    return identity, model, calibration


def raw_design(rows: pd.DataFrame, challenger: bool) -> tuple[np.ndarray, list[str]]:
    n = len(rows)
    cols = [np.ones(n, float)]
    names = ["intercept"]
    symbol = rows.symbol.eq("000852.SH").astype(float).to_numpy()
    cols.append(symbol)
    names.append("symbol_000852")
    cells = rows.current_state.astype(str) + "|" + rows.age_bucket.astype(str)
    for state in STATES:
        for bucket in AGE_BUCKETS:
            key = f"{state}|{bucket}"
            if key == REFERENCE_CELL:
                continue
            cols.append(cells.eq(key).astype(float).to_numpy())
            names.append("cell_" + key)
    if challenger:
        a = np.log1p(np.maximum(rows.shock_intensity.to_numpy(float), 0.0))
        b = np.log(np.maximum(rows.vol_ratio.to_numpy(float), 1e-12))
        base = [a, b, a * a, b * b, a * b]
        base_names = ["a", "b", "a2", "b2", "ab"]
        recovering = rows.current_state.eq("RECOVERING").astype(float).to_numpy()
        for x, name in zip(base, base_names):
            cols.append(x)
            names.append(name)
        for x, name in zip(base, base_names):
            cols.append(x * recovering)
            names.append(name + "_x_RECOVERING")
    return np.column_stack(cols), names


def predict_frozen(model: dict, rows: pd.DataFrame) -> np.ndarray:
    X, names = raw_design(rows, bool(model["challenger"]))
    if names != list(model["names"]):
        raise RuntimeError("frozen_model_design_drift")
    means = np.asarray(model["means"], float)
    sds = np.asarray(model["sds"], float)
    beta = np.asarray(model["beta"], float)
    if X.shape[1] != len(means) or X.shape[1] != len(sds) or X.shape[1] != len(beta):
        raise RuntimeError("frozen_model_dimension_mismatch")
    if float(model["ridge_lambda"]) != 0.01:
        raise RuntimeError("frozen_model_ridge_mismatch")
    for j in range(1, X.shape[1]):
        if sds[j] <= 0:
            raise RuntimeError("frozen_model_sd_invalid")
        X[:, j] = (X[:, j] - means[j]) / sds[j]
    return np.clip(X @ beta, 0.0, 1.0)


def apply_platt(beta: list[float], p: np.ndarray) -> np.ndarray:
    if len(beta) != 2:
        raise RuntimeError("platt_parameter_shape_invalid")
    q = np.clip(np.asarray(p, float), PLATT_CLIP, 1.0 - PLATT_CLIP)
    z = np.log(q / (1.0 - q))
    eta = np.clip(float(beta[0]) + float(beta[1]) * z, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-eta))


def verify_frozen_scores(scored: pd.DataFrame, model: dict, calibration: dict) -> None:
    for horizon in HORIZONS:
        models = model.get("models", {}).get(str(horizon))
        fits = calibration.get("fits", {}).get(str(horizon), {}).get("audit")
        if not isinstance(models, dict) or set(models) != {"B", "C"}:
            raise RuntimeError("model_freeze_horizon_missing")
        if not isinstance(fits, dict) or set(fits) != {"B", "C"}:
            raise RuntimeError("calibration_freeze_horizon_missing")
        expected_b_raw = predict_frozen(models["B"], scored)
        expected_c_raw = predict_frozen(models["C"], scored)
        expected_b_cal = apply_platt(fits["B"], expected_b_raw)
        expected_c_cal = apply_platt(fits["C"], expected_c_raw)
        comparisons = {
            f"p_B_raw_{horizon}m": expected_b_raw,
            f"p_C_raw_{horizon}m": expected_c_raw,
            f"p_B_cal_{horizon}m": expected_b_cal,
            f"p_C_cal_{horizon}m": expected_c_cal,
        }
        for column, expected in comparisons.items():
            if column not in scored or not close(scored[column].to_numpy(float), expected):
                raise RuntimeError(f"frozen_score_mismatch:{column}")


def auc(y, p) -> float:
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    n1 = int(y.sum())
    n0 = int(len(y) - n1)
    if n1 <= 0 or n0 <= 0:
        raise RuntimeError("auc_single_class")
    ranks = rankdata(p, method="average")
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def score(y, p) -> dict:
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    if len(y) == 0 or len(y) != len(p) or not np.isfinite(p).all():
        raise RuntimeError("score_input_invalid")
    if np.any((p < 0.0) | (p > 1.0)):
        raise RuntimeError("probability_out_of_range")
    q = np.clip(p, LOGLOSS_CLIP, 1.0 - LOGLOSS_CLIP)
    return {
        "n": int(len(y)),
        "auroc": auc(y, p),
        "brier": float(np.mean((p - y) ** 2)),
        "log_loss": float(-np.mean(y * np.log(q) + (1.0 - y) * np.log(1.0 - q))),
        "observed_rate": float(np.mean(y)),
        "mean_prediction": float(np.mean(p)),
    }


def gains(frame: pd.DataFrame, horizon: int) -> dict:
    ycol = f"normal_within_{horizon}m"
    y = frame[ycol].to_numpy(int)
    b_raw = score(y, frame[f"p_B_raw_{horizon}m"].to_numpy(float))
    c_raw = score(y, frame[f"p_C_raw_{horizon}m"].to_numpy(float))
    b_cal = score(y, frame[f"p_B_cal_{horizon}m"].to_numpy(float))
    c_cal = score(y, frame[f"p_C_cal_{horizon}m"].to_numpy(float))
    return {
        "B_raw": b_raw,
        "C_raw": c_raw,
        "B_cal": b_cal,
        "C_cal": c_cal,
        "raw_auroc_gain": float(c_raw["auroc"] - b_raw["auroc"]),
        "calibrated_brier_gain": float(b_cal["brier"] - c_cal["brier"]),
        "calibrated_logloss_gain": float(b_cal["log_loss"] - c_cal["log_loss"]),
    }


def support_gate(frame: pd.DataFrame, horizon: int) -> dict:
    ycol = f"normal_within_{horizon}m"
    z = frame[frame[ycol].notna()].copy()
    y = z[ycol].astype(int)
    symbol_counts = z.groupby("symbol").size()
    symbol_classes = z.groupby("symbol")[ycol].nunique()
    checks = {
        "fresh_oos_rows_ge_1000": len(z) >= 1000,
        "fresh_oos_each_symbol_rows_ge_150": len(symbol_counts) == 2 and int(symbol_counts.min()) >= 150,
        "fresh_oos_positive_ge_100": int(y.sum()) >= 100,
        "fresh_oos_negative_ge_100": int((1 - y).sum()) >= 100,
        "fresh_oos_each_symbol_has_both_classes": len(symbol_classes) == 2 and bool((symbol_classes >= 2).all()),
    }
    return {
        "horizon_minutes": horizon,
        "rows": int(len(z)),
        "positive": int(y.sum()) if len(y) else 0,
        "negative": int((1 - y).sum()) if len(y) else 0,
        "by_symbol_rows": {s: int(symbol_counts.get(s, 0)) for s in SYMBOLS},
        "by_symbol_classes": {s: int(symbol_classes.get(s, 0)) for s in SYMBOLS},
        "supported_horizon": bool(all(checks.values())),
        "checks": checks,
    }


def bootstrap_family(frame: pd.DataFrame, horizon: int, repetitions: int, seed: int) -> dict:
    ycol = f"normal_within_{horizon}m"
    z = frame[frame[ycol].notna()].copy()
    groups = [g for _, g in z.groupby("trading_day", sort=True)]
    if not groups:
        raise RuntimeError("bootstrap_no_clusters")
    rng = np.random.default_rng(seed)
    draws = {
        "raw_auroc_gain": np.empty(repetitions, float),
        "calibrated_brier_gain": np.empty(repetitions, float),
        "calibrated_logloss_gain": np.empty(repetitions, float),
    }
    for i in range(repetitions):
        indexes = rng.integers(0, len(groups), size=len(groups))
        sampled = pd.concat([groups[j] for j in indexes], ignore_index=True)
        value = gains(sampled, horizon)
        for key in draws:
            draws[key][i] = value[key]
    point = gains(z, horizon)
    return {
        "cluster": "trading_day",
        "joint_symbols_within_cluster": True,
        "clusters": int(len(groups)),
        "repetitions": int(repetitions),
        "seed": int(seed),
        "family_size": FAMILY_SIZE,
        "one_sided_family_alpha": 0.05,
        "bonferroni_lower_quantile": BONFERRONI_LOWER_QUANTILE,
        "metrics": {
            key: {
                "point": float(point[key]),
                "lower": float(np.quantile(values, BONFERRONI_LOWER_QUANTILE)),
            }
            for key, values in draws.items()
        },
    }


def compare_tree(got, expected, path="root") -> None:
    if isinstance(expected, dict):
        if not isinstance(got, dict) or set(got) != set(expected):
            raise RuntimeError(f"summary_shape_mismatch:{path}")
        for key in expected:
            compare_tree(got[key], expected[key], f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(got, list) or len(got) != len(expected):
            raise RuntimeError(f"summary_shape_mismatch:{path}")
        for i, (gv, ev) in enumerate(zip(got, expected)):
            compare_tree(gv, ev, f"{path}[{i}]")
        return
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        if got != expected:
            raise RuntimeError(f"summary_value_mismatch:{path}")
        return
    if isinstance(expected, (int, float)):
        if not close(got, expected):
            raise RuntimeError(f"summary_numeric_mismatch:{path}")
        return
    if got != expected:
        raise RuntimeError(f"summary_value_mismatch:{path}")


def recompute_horizon(scored: pd.DataFrame, horizon: int, repetitions: int) -> dict:
    support = support_gate(scored, horizon)
    if not support["supported_horizon"]:
        return {
            "horizon_minutes": horizon,
            "status": "OUT_OF_SUPPORTED_FRESH_OOS",
            "support": support,
            "scientific_support": False,
        }
    ycol = f"normal_within_{horizon}m"
    z = scored[scored[ycol].notna()].copy()
    pooled = gains(z, horizon)
    by_symbol = {s: gains(z[z.symbol.eq(s)], horizon) for s in SYMBOLS}
    bootstrap = bootstrap_family(z, horizon, repetitions, BOOTSTRAP_SEED)
    gates = {
        "raw_auroc_gain_gt_zero": pooled["raw_auroc_gain"] > 0,
        "raw_auroc_family_adjusted_bootstrap_lower_gt_zero": bootstrap["metrics"]["raw_auroc_gain"]["lower"] > 0,
        "raw_auroc_gain_each_symbol_nonnegative": all(by_symbol[s]["raw_auroc_gain"] >= 0 for s in SYMBOLS),
        "calibrated_brier_gain_gt_zero": pooled["calibrated_brier_gain"] > 0,
        "calibrated_brier_family_adjusted_bootstrap_lower_gt_zero": bootstrap["metrics"]["calibrated_brier_gain"]["lower"] > 0,
        "calibrated_logloss_gain_gt_zero": pooled["calibrated_logloss_gain"] > 0,
        "calibrated_logloss_family_adjusted_bootstrap_lower_gt_zero": bootstrap["metrics"]["calibrated_logloss_gain"]["lower"] > 0,
        "calibrated_brier_gain_each_symbol_nonnegative": all(by_symbol[s]["calibrated_brier_gain"] >= 0 for s in SYMBOLS),
        "calibrated_logloss_gain_each_symbol_nonnegative": all(by_symbol[s]["calibrated_logloss_gain"] >= 0 for s in SYMBOLS),
    }
    validated = bool(all(gates.values()))
    return {
        "horizon_minutes": horizon,
        "status": "FRESH_OOS_VALIDATED" if validated else "FRESH_OOS_NOT_VALIDATED",
        "support": support,
        "pooled": pooled,
        "by_symbol": by_symbol,
        "bootstrap": bootstrap,
        "acceptance_gates": gates,
        "scientific_support": validated,
    }


def verify(inputs: Path, results: Path, repetitions: int = BOOTSTRAP_REPS) -> dict:
    expected_files = {"FRESH_OOS_SCORED.parquet", "SUMMARY.json"}
    present = {p.name for p in results.iterdir() if p.is_file()}
    if present != expected_files:
        raise RuntimeError("result_file_set_mismatch")
    identity, model, calibration = validate_inputs(inputs)
    summary = load_json(results / "SUMMARY.json")
    scored = pd.read_parquet(results / "FRESH_OOS_SCORED.parquet")
    required = {
        "symbol", "trading_day", "year", "current_state", "age_bucket",
        "shock_intensity", "vol_ratio",
    }
    for horizon in HORIZONS:
        required |= {
            f"normal_within_{horizon}m",
            f"p_B_raw_{horizon}m", f"p_C_raw_{horizon}m",
            f"p_B_cal_{horizon}m", f"p_C_cal_{horizon}m",
        }
    if not required.issubset(scored.columns):
        raise RuntimeError("scored_columns_missing")
    if scored.empty or set(scored.symbol.dropna().unique()) != set(SYMBOLS):
        raise RuntimeError("scored_symbol_set_mismatch")
    if set(scored.year.dropna().astype(int).unique()) != {FRESH_YEAR}:
        raise RuntimeError("scored_year_leak")
    verify_frozen_scores(scored, model, calibration)

    horizons = {str(h): recompute_horizon(scored, h, repetitions) for h in HORIZONS}
    validated = sum(horizons[str(h)]["status"] == "FRESH_OOS_VALIDATED" for h in HORIZONS)
    overall = (
        "FRESH_OOS_FULL_VALIDATION" if validated == 2
        else "FRESH_OOS_PARTIAL_VALIDATION" if validated == 1
        else "FRESH_OOS_NOT_VALIDATED"
    )
    expected_summary = {
        "schema_id": SCHEMA_ID,
        "task_id": TASK_ID,
        "fresh_oos_year": FRESH_YEAR,
        "horizons_minutes": list(HORIZONS),
        "identity_receipt_sha256": sha256_file(inputs / "DATA_IDENTITY.json"),
        "model_freeze_sha256": MODEL_FREEZE_SHA256,
        "calibration_freeze_sha256": CALIBRATION_FREEZE_SHA256,
        "year_2026_semantic_read": True,
        "parent_model_refit": False,
        "calibrator_refit": False,
        "sensor_retuning": False,
        "cohort_retuning": False,
        "substitute_data_used": False,
        "identity": identity,
        "horizons": horizons,
        "overall_status": overall,
        "production_authority": False,
    }
    compare_tree(summary, expected_summary)
    return expected_summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    verified = verify(args.inputs.resolve(), args.results.resolve(), BOOTSTRAP_REPS)
    print(json.dumps({
        "status": "verified",
        "overall_status": verified["overall_status"],
        "production_authority": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
