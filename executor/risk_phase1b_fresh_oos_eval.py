from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

TASK_ID = "CSI1000-RISK-V2-2026-FRESH-OOS-V1-20260914"
SCHEMA_ID = "risk_tool_v2_phase1b_fresh_oos_result@2.0"
IDENTITY_SCHEMA_ID = "risk_tool_v2_phase1b_accepted_carrier@1.0"
SYMBOLS = ("000688.SH", "000852.SH")
HORIZONS = (15, 30)
FRESH_YEAR = 2026
WARMUP_YEAR = 2025
CUTOFF_DAY = "2026-09-11"
CARRIER_BYTES = 3615731
CARRIER_SHA256 = "211448c914b547232bc536da7df94dc5ae279b8265a5cafe58409238485217d7"
MODEL_FREEZE_SHA256 = "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551"
CALIBRATION_FREEZE_SHA256 = "74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909"
PREREG_SHA256 = "c05bdf09c54626861f2a86abbcadb514fa90918320e2ab4be45e1e3217b7c9d7"

RV_WINDOW = 12
BG_WINDOW = 48
HIGHVOL_RATIO = 1.50
RECOVERY_NORMAL_RATIO = 1.10
SHOCK_SIGMA = 3.00
STATES = ("UNSAFE", "RECOVERING")
AGE_BUCKETS = ("LT15", "M15_25", "M30_40", "GE45")
REFERENCE_CELL = "UNSAFE|LT15"
PLATT_CLIP = 1e-6
LOGLOSS_CLIP = 1e-12

FRESH_ROWS_MIN = 1200
FRESH_ROWS_EACH_SYMBOL_MIN = 500
FRESH_POSITIVE_MIN = 100
FRESH_NEGATIVE_MIN = 100
TRADING_DAY_CLUSTERS_MIN = 100
BOOTSTRAP_REPS = 5000
BOOTSTRAP_SEED = 20260914
BOOTSTRAP_FAMILY_SIZE = 2
BOOTSTRAP_LOWER_QUANTILE = 0.025

FROZEN_CALIBRATION = {
    "15": {
        "B": [-0.0005783322327921923, 1.0012925611665986],
        "C": [-0.03819573273361419, 1.0031313564853719],
    },
    "30": {
        "B": [0.0048316291422488035, 1.0176058836682678],
        "C": [-0.01552854661043555, 0.9880960138797352],
    },
}


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"json_object_required:{path.name}")
    return value


def wallclock(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(str).str.slice(0, 19), errors="coerce")


def age_bucket(bars: int) -> str:
    if bars <= 2:
        return "LT15"
    if bars <= 5:
        return "M15_25"
    if bars <= 8:
        return "M30_40"
    return "GE45"


def transition(prev_state: str, ratio: float, is_shock: bool) -> str:
    if is_shock:
        return "UNSAFE"
    if prev_state == "UNSAFE":
        if pd.isna(ratio) or ratio >= HIGHVOL_RATIO:
            return "UNSAFE"
        if ratio > RECOVERY_NORMAL_RATIO:
            return "RECOVERING"
        return "NORMAL"
    if prev_state == "RECOVERING":
        if pd.isna(ratio):
            return "RECOVERING"
        if ratio >= HIGHVOL_RATIO:
            return "UNSAFE"
        if ratio > RECOVERY_NORMAL_RATIO:
            return "RECOVERING"
        return "NORMAL"
    return "NORMAL"


def validate_identity(inputs: Path) -> tuple[dict, Path]:
    identity = load_json(inputs / "DATA_IDENTITY.json")
    if identity.get("schema_id") != IDENTITY_SCHEMA_ID or identity.get("task_id") != TASK_ID:
        raise RuntimeError("identity_schema_or_task_mismatch")
    if identity.get("user_authorized_same_source_and_valid") is not True:
        raise RuntimeError("carrier_not_user_authorized")
    if identity.get("year_2026_semantic_read_before_compute") is not False:
        raise RuntimeError("identity_precompute_semantic_read_not_false")
    carrier = identity.get("carrier")
    expected = {
        "path": "data/index/5m_offset_0.parquet",
        "bytes": CARRIER_BYTES,
        "sha256": CARRIER_SHA256,
    }
    if not isinstance(carrier, dict):
        raise RuntimeError("carrier_identity_missing")
    for key, value in expected.items():
        if carrier.get(key) != value:
            raise RuntimeError(f"carrier_identity_mismatch:{key}")
    path = inputs / "market" / "5m_offset_0.parquet"
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("carrier_file_missing")
    if path.stat().st_size != CARRIER_BYTES or sha256_file(path) != CARRIER_SHA256:
        raise RuntimeError("carrier_file_digest_mismatch")
    return identity, path


def validate_authority_inputs(inputs: Path) -> tuple[dict, dict]:
    model_path = inputs / "MODEL_FREEZE.json"
    cal_path = inputs / "CALIBRATION_FREEZE.json"
    if sha256_file(model_path) != MODEL_FREEZE_SHA256:
        raise RuntimeError("model_freeze_digest_mismatch")
    if sha256_file(cal_path) != CALIBRATION_FREEZE_SHA256:
        raise RuntimeError("calibration_freeze_digest_mismatch")
    model = load_json(model_path)
    cal = load_json(cal_path)
    if model.get("schema_id") != "risk_tool_v2_model_freeze@1.0":
        raise RuntimeError("model_freeze_schema_mismatch")
    if model.get("development_years") != [2021, 2022, 2023] or float(model.get("ridge_lambda")) != 0.01:
        raise RuntimeError("model_freeze_training_contract_mismatch")
    if model.get("audit_retuning") is not False:
        raise RuntimeError("model_freeze_retuning_flag_invalid")
    if cal.get("method") != "Platt" or float(cal.get("slope_ridge_lambda")) != 1e-6:
        raise RuntimeError("calibration_freeze_contract_mismatch")
    if cal.get("year_2026_read") is not False:
        raise RuntimeError("calibration_freeze_2026_flag_invalid")
    for horizon in HORIZONS:
        models = model.get("models", {}).get(str(horizon))
        fits = cal.get("fits", {}).get(str(horizon), {}).get("audit")
        if not isinstance(models, dict) or set(models) != {"B", "C"}:
            raise RuntimeError(f"model_freeze_horizon_missing:{horizon}")
        if not isinstance(fits, dict) or set(fits) != {"B", "C"}:
            raise RuntimeError(f"calibration_freeze_horizon_missing:{horizon}")
        for label in ("B", "C"):
            if not np.allclose(
                np.asarray(fits[label], float),
                np.asarray(FROZEN_CALIBRATION[str(horizon)][label], float),
                rtol=0.0,
                atol=1e-15,
            ):
                raise RuntimeError(f"calibration_parameter_drift:{horizon}:{label}")
    return model, cal


def normalize_carrier(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"datetime", "symbol", "close"}
    if not required.issubset(frame.columns):
        raise RuntimeError("carrier_columns_missing")
    z = pd.DataFrame(
        {
            "symbol": frame["symbol"].astype(str),
            "bar_end": wallclock(frame["datetime"]),
            "close": pd.to_numeric(frame["close"], errors="coerce"),
        }
    ).dropna()
    z = z[z.symbol.isin(SYMBOLS)].copy()
    z["trading_day"] = z.bar_end.dt.strftime("%Y-%m-%d")
    years = z.bar_end.dt.year
    z = z[(years == WARMUP_YEAR) | ((years == FRESH_YEAR) & z.trading_day.le(CUTOFF_DAY))].copy()
    if z.empty:
        raise RuntimeError("accepted_carrier_has_no_required_rows")
    if z.duplicated(["symbol", "bar_end"]).any():
        raise RuntimeError("duplicate_symbol_timestamp")
    return z.sort_values(["symbol", "trading_day", "bar_end"], kind="stable").reset_index(drop=True)


def build_state_rows(source: pd.DataFrame) -> pd.DataFrame:
    out = []
    for symbol in SYMBOLS:
        z = source[source.symbol.eq(symbol)].copy()
        if z.empty:
            continue
        counts = z.groupby("trading_day", sort=False).size()
        if bool((counts != 48).any()):
            bad = counts[counts != 48]
            raise RuntimeError(f"non_48_row_trading_day:{symbol}:{bad.index[0]}:{int(bad.iloc[0])}")
        z["session"] = np.where(z.bar_end.dt.hour < 12, "AM", "PM")
        session_counts = z.groupby(["trading_day", "session"]).size()
        if bool((session_counts != 24).any()):
            raise RuntimeError(f"non_24_row_session:{symbol}")
        z["ret_5m"] = z.groupby("trading_day", sort=False).close.transform(lambda s: np.log(s).diff())
        valid = z.ret_5m.dropna()
        z["rv12"] = valid.rolling(RV_WINDOW, min_periods=RV_WINDOW).std(ddof=0).reindex(z.index)
        z["bg_vol48"] = valid.shift(1).rolling(BG_WINDOW, min_periods=BG_WINDOW).std(ddof=0).reindex(z.index)
        z.loc[z.bg_vol48 <= 0, "bg_vol48"] = np.nan
        z["vol_ratio"] = z.rv12 / z.bg_vol48
        z["shock_intensity"] = z.ret_5m.abs() / z.bg_vol48
        z["shock"] = z.shock_intensity.ge(SHOCK_SIGMA).fillna(False)
        state = pd.Series("NORMAL", index=z.index, dtype="object")
        for _, idx in z.groupby("trading_day", sort=False).groups.items():
            mode = "NORMAL"
            for i in idx:
                ratio = float(z.at[i, "vol_ratio"]) if pd.notna(z.at[i, "vol_ratio"]) else np.nan
                mode = transition(mode, ratio, bool(z.at[i, "shock"]))
                state.at[i] = mode
        z["risk_state"] = state
        z["year"] = z.bar_end.dt.year.astype(int)
        out.append(z)
    if not out:
        raise RuntimeError("accepted_carrier_has_no_required_symbols")
    return pd.concat(out, ignore_index=True).sort_values(
        ["symbol", "trading_day", "bar_end"], kind="stable"
    ).reset_index(drop=True)


def build_fresh_cohort(states: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (symbol, day_name), z0 in states.groupby(["symbol", "trading_day"], sort=False):
        if int(str(day_name)[:4]) != FRESH_YEAR:
            continue
        day = z0.sort_values("bar_end", kind="stable").reset_index(drop=True)
        prev_unsafe = day.risk_state.shift(1).eq("UNSAFE").fillna(False)
        starts = list(day.index[day.shock.astype(bool) & ~prev_unsafe])
        occupied = -1
        episode_no = 0
        for j0 in starts:
            j = int(j0)
            if j <= occupied:
                continue
            normals = day.index[(day.index > j) & day.risk_state.eq("NORMAL")]
            end = int(normals[0]) if len(normals) else None
            occupied = (end - 1) if end is not None else int(day.index.max())
            episode_no += 1
            last_shock = j
            for k in range(j + 1, occupied + 1):
                if bool(day.at[k, "shock"]):
                    last_shock = k
                    continue
                state = str(day.at[k, "risk_state"])
                if state not in STATES:
                    continue
                age = k - last_shock
                if age < 1:
                    continue
                rec = {
                    "symbol": symbol,
                    "trading_day": str(day_name),
                    "year": FRESH_YEAR,
                    "bar_end": pd.Timestamp(day.at[k, "bar_end"]),
                    "session": str(day.at[k, "session"]),
                    "episode_no": episode_no,
                    "current_state": state,
                    "recent_shock_age_bars": int(age),
                    "age_bucket": age_bucket(age),
                    "shock_intensity": float(day.at[k, "shock_intensity"]),
                    "vol_ratio": float(day.at[k, "vol_ratio"]),
                }
                for horizon in HORIZONS:
                    bars = horizon // 5
                    future = day.iloc[k + 1:k + 1 + bars]
                    if len(future) != bars or not future.session.eq(day.at[k, "session"]).all():
                        rec[f"normal_within_{horizon}m"] = np.nan
                    else:
                        rec[f"normal_within_{horizon}m"] = int(future.risk_state.eq("NORMAL").any())
                rows.append(rec)
    if not rows:
        raise RuntimeError("fresh_oos_cohort_empty")
    return pd.DataFrame(rows).sort_values(
        ["symbol", "trading_day", "bar_end"], kind="stable"
    ).reset_index(drop=True)


def raw_design(rows: pd.DataFrame, challenger: bool) -> tuple[np.ndarray, list[str]]:
    n = len(rows)
    cols = [np.ones(n, float)]
    names = ["intercept"]
    cols.append(rows.symbol.eq("000852.SH").astype(float).to_numpy())
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
    q = np.clip(np.asarray(p, float), PLATT_CLIP, 1.0 - PLATT_CLIP)
    z = np.log(q / (1.0 - q))
    eta = np.clip(float(beta[0]) + float(beta[1]) * z, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-eta))


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
    clusters = int(z.trading_day.nunique())
    checks = {
        "fresh_rows_ge_1200": len(z) >= FRESH_ROWS_MIN,
        "fresh_rows_each_symbol_ge_500": len(symbol_counts) == 2 and int(symbol_counts.min()) >= FRESH_ROWS_EACH_SYMBOL_MIN,
        "fresh_positive_ge_100": int(y.sum()) >= FRESH_POSITIVE_MIN,
        "fresh_negative_ge_100": int((1 - y).sum()) >= FRESH_NEGATIVE_MIN,
        "trading_day_clusters_ge_100": clusters >= TRADING_DAY_CLUSTERS_MIN,
    }
    return {
        "horizon_minutes": horizon,
        "rows": int(len(z)),
        "positive": int(y.sum()) if len(y) else 0,
        "negative": int((1 - y).sum()) if len(y) else 0,
        "trading_day_clusters": clusters,
        "by_symbol_rows": {s: int(symbol_counts.get(s, 0)) for s in SYMBOLS},
        "supported_horizon": bool(all(checks.values())),
        "checks": checks,
    }


def bootstrap_raw_auroc_gain(frame: pd.DataFrame, horizon: int) -> dict:
    ycol = f"normal_within_{horizon}m"
    z = frame[frame[ycol].notna()].copy()
    groups = [g for _, g in z.groupby("trading_day", sort=True)]
    if not groups:
        raise RuntimeError("bootstrap_no_clusters")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = np.empty(BOOTSTRAP_REPS, float)
    for i in range(BOOTSTRAP_REPS):
        indexes = rng.integers(0, len(groups), size=len(groups))
        sampled = pd.concat([groups[j] for j in indexes], ignore_index=True)
        draws[i] = gains(sampled, horizon)["raw_auroc_gain"]
    return {
        "metric": "raw-score AUROC(C)-AUROC(B)",
        "cluster": "trading_day across both symbols",
        "clusters": int(len(groups)),
        "repetitions": BOOTSTRAP_REPS,
        "seed": BOOTSTRAP_SEED,
        "family_size": BOOTSTRAP_FAMILY_SIZE,
        "family_one_sided_alpha": 0.05,
        "lower_quantile": BOOTSTRAP_LOWER_QUANTILE,
        "point": float(gains(z, horizon)["raw_auroc_gain"]),
        "lower": float(np.quantile(draws, BOOTSTRAP_LOWER_QUANTILE)),
    }


def score_cohort(cohort: pd.DataFrame, model_freeze: dict, calibration_freeze: dict) -> pd.DataFrame:
    scored = cohort.copy()
    for horizon in HORIZONS:
        models = model_freeze["models"][str(horizon)]
        fits = calibration_freeze["fits"][str(horizon)]["audit"]
        scored[f"p_B_raw_{horizon}m"] = predict_frozen(models["B"], scored)
        scored[f"p_C_raw_{horizon}m"] = predict_frozen(models["C"], scored)
        scored[f"p_B_cal_{horizon}m"] = apply_platt(fits["B"], scored[f"p_B_raw_{horizon}m"].to_numpy())
        scored[f"p_C_cal_{horizon}m"] = apply_platt(fits["C"], scored[f"p_C_raw_{horizon}m"].to_numpy())
    return scored


def evaluate_horizon(scored: pd.DataFrame, horizon: int) -> dict:
    support = support_gate(scored, horizon)
    if not support["supported_horizon"]:
        return {
            "horizon_minutes": horizon,
            "status": "INSUFFICIENT_2026_SUPPORT",
            "support": support,
            "scientific_support": False,
        }
    ycol = f"normal_within_{horizon}m"
    z = scored[scored[ycol].notna()].copy()
    pooled = gains(z, horizon)
    by_symbol = {s: gains(z[z.symbol.eq(s)], horizon) for s in SYMBOLS}
    bootstrap = bootstrap_raw_auroc_gain(z, horizon)
    gates = {
        "raw_auroc_gain_gt_zero": pooled["raw_auroc_gain"] > 0,
        "raw_auroc_family_adjusted_bootstrap_lower_gt_zero": bootstrap["lower"] > 0,
        "raw_auroc_gain_each_symbol_nonnegative": all(by_symbol[s]["raw_auroc_gain"] >= 0 for s in SYMBOLS),
        "calibrated_brier_gain_gt_zero": pooled["calibrated_brier_gain"] > 0,
        "calibrated_logloss_gain_gt_zero": pooled["calibrated_logloss_gain"] > 0,
        "calibrated_brier_gain_each_symbol_nonnegative": all(by_symbol[s]["calibrated_brier_gain"] >= 0 for s in SYMBOLS),
        "calibrated_logloss_gain_each_symbol_nonnegative": all(by_symbol[s]["calibrated_logloss_gain"] >= 0 for s in SYMBOLS),
    }
    supported = bool(all(gates.values()))
    return {
        "horizon_minutes": horizon,
        "status": "FRESH_OOS_SUPPORTED" if supported else "FRESH_OOS_NOT_SUPPORTED",
        "support": support,
        "pooled": pooled,
        "by_symbol": by_symbol,
        "bootstrap": bootstrap,
        "acceptance_gates": gates,
        "scientific_support": supported,
    }


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def run(inputs: Path, out: Path) -> dict:
    if out.exists():
        raise RuntimeError("output_directory_already_exists")
    identity, carrier_path = validate_identity(inputs)
    model_freeze, calibration_freeze = validate_authority_inputs(inputs)

    source = pd.read_parquet(carrier_path, columns=["datetime", "symbol", "close"])
    normalized = normalize_carrier(source)
    states = build_state_rows(normalized)
    cohort = build_fresh_cohort(states)
    scored = score_cohort(cohort, model_freeze, calibration_freeze)
    horizons = {str(h): evaluate_horizon(scored, h) for h in HORIZONS}
    statuses = [horizons[str(h)]["status"] for h in HORIZONS]
    if all(s == "FRESH_OOS_SUPPORTED" for s in statuses):
        overall = "FRESH_OOS_SUPPORTED"
    elif all(s == "INSUFFICIENT_2026_SUPPORT" for s in statuses):
        overall = "INSUFFICIENT_2026_SUPPORT"
    elif all(s == "FRESH_OOS_NOT_SUPPORTED" for s in statuses):
        overall = "FRESH_OOS_NOT_SUPPORTED"
    else:
        overall = "MIXED_BY_HORIZON"

    result = {
        "schema_id": SCHEMA_ID,
        "task_id": TASK_ID,
        "prereg_sha256": PREREG_SHA256,
        "fresh_oos_year": FRESH_YEAR,
        "cutoff_trading_day_inclusive": CUTOFF_DAY,
        "carrier_identity_sha256": CARRIER_SHA256,
        "model_freeze_sha256": MODEL_FREEZE_SHA256,
        "calibration_freeze_sha256": CALIBRATION_FREEZE_SHA256,
        "year_2026_semantic_read": True,
        "parent_model_refit": False,
        "calibrator_refit": False,
        "sensor_retuning": False,
        "cohort_retuning": False,
        "substitute_data_used": False,
        "user_authorized_same_source_and_valid": identity["user_authorized_same_source_and_valid"],
        "horizons": horizons,
        "overall_status": overall,
        "production_authority": False,
    }
    out.mkdir(parents=True)
    scored.to_parquet(out / "FRESH_OOS_SCORED.parquet", index=False)
    (out / "SUMMARY.json").write_text(json.dumps(clean(result), indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.inputs.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
