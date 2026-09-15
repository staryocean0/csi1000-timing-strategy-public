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
WARMUP_YEAR = 2025
FRESH_YEAR = 2026
HORIZONS = (15, 30)
RV_WINDOW = 12
BG_WINDOW = 48
HIGHVOL_RATIO = 1.50
RECOVERY_NORMAL_RATIO = 1.10
SHOCK_SIGMA = 3.00
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
BONFERRONI_LOWER_QUANTILE = 0.008333333333333333
PLATT_CLIP = 1e-6
LOGLOSS_CLIP = 1e-12


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


def validate_identity(inputs: Path) -> tuple[dict, dict[str, Path]]:
    identity_path = inputs / "DATA_IDENTITY.json"
    identity = load_json(identity_path)
    if identity.get("schema_id") != IDENTITY_SCHEMA_ID or identity.get("task_id") != TASK_ID:
        raise RuntimeError("identity_receipt_schema_or_task_mismatch")
    if identity.get("canonical_repository") != "staryocean0/factorlab-trend-reversion-regime-lab":
        raise RuntimeError("identity_repository_mismatch")
    if identity.get("year_2026_semantic_read_before_identity_commit") is not False:
        raise RuntimeError("identity_precommit_semantic_read_not_false")

    rows = identity.get("files")
    if not isinstance(rows, list) or len(rows) != 2:
        raise RuntimeError("identity_file_set_invalid")

    by_symbol = {}
    paths = {}
    expected_paths = {
        "000688.SH": "data/market/5m/000688.SH/2026.parquet",
        "000852.SH": "data/market/5m/000852.SH/2026.parquet",
    }
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("identity_file_row_invalid")
        required = {
            "symbol",
            "canonical_repository",
            "immutable_source_commit",
            "path",
            "git_blob_sha1",
            "bytes",
            "sha256",
        }
        if not required.issubset(row):
            raise RuntimeError("identity_required_field_missing")
        symbol = row["symbol"]
        if symbol not in SYMBOLS or symbol in by_symbol:
            raise RuntimeError("identity_symbol_set_invalid")
        if row["canonical_repository"] != identity["canonical_repository"]:
            raise RuntimeError("identity_repository_row_mismatch")
        if row["path"] != expected_paths[symbol]:
            raise RuntimeError("identity_path_mismatch")
        if not isinstance(row["immutable_source_commit"], str) or len(row["immutable_source_commit"]) != 40:
            raise RuntimeError("identity_commit_invalid")
        if not isinstance(row["git_blob_sha1"], str) or len(row["git_blob_sha1"]) != 40:
            raise RuntimeError("identity_blob_invalid")
        if not isinstance(row["bytes"], int) or row["bytes"] <= 0:
            raise RuntimeError("identity_bytes_invalid")
        if not isinstance(row["sha256"], str) or len(row["sha256"]) != 64:
            raise RuntimeError("identity_sha256_invalid")
        local = inputs / "market" / symbol / "2026.parquet"
        if not local.is_file() or local.is_symlink():
            raise RuntimeError("fresh_oos_file_missing")
        if local.stat().st_size != row["bytes"] or sha256_file(local) != row["sha256"]:
            raise RuntimeError("fresh_oos_file_identity_mismatch")
        by_symbol[symbol] = row
        paths[symbol] = local

    if set(by_symbol) != set(SYMBOLS):
        raise RuntimeError("identity_symbol_set_incomplete")
    return identity, paths


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
        if not isinstance(models, dict) or set(models) != {"B", "C"}:
            raise RuntimeError(f"model_freeze_horizon_missing:{horizon}")
        fits = cal.get("fits", {}).get(str(horizon), {}).get("audit")
        if not isinstance(fits, dict) or set(fits) != {"B", "C"}:
            raise RuntimeError(f"calibration_freeze_horizon_missing:{horizon}")
        for label in ("B", "C"):
            if not isinstance(fits[label], list) or len(fits[label]) != 2:
                raise RuntimeError("calibration_fit_shape_invalid")
    return model, cal


def validate_warmup(inputs: Path) -> dict[str, Path]:
    paths = {}
    for symbol in SYMBOLS:
        path = inputs / "market" / symbol / "2025.parquet"
        meta = WARMUP[symbol]
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != meta["bytes"]
            or sha256_file(path) != meta["sha256"]
        ):
            raise RuntimeError(f"warmup_identity_mismatch:{symbol}")
        paths[symbol] = path
    return paths


def normalize_source(frame: pd.DataFrame, symbol: str, year: int) -> pd.DataFrame:
    required = {"trading_day", "timestamp", "close"}
    if not required.issubset(frame.columns):
        raise RuntimeError(f"5m_columns_missing:{symbol}:{year}")
    z = pd.DataFrame(
        {
            "symbol": symbol,
            "trading_day": pd.to_datetime(frame["trading_day"], errors="coerce").dt.strftime("%Y-%m-%d"),
            "bar_end": wallclock(frame["timestamp"]),
            "close": pd.to_numeric(frame["close"], errors="coerce"),
        }
    ).dropna()
    z = z[pd.to_datetime(z.trading_day).dt.year.eq(year)].copy()
    z = z.sort_values(["trading_day", "bar_end"], kind="stable").reset_index(drop=True)
    if z.empty:
        raise RuntimeError(f"empty_5m_source:{symbol}:{year}")
    return z


def build_state_rows(frames: dict[tuple[str, int], pd.DataFrame]) -> pd.DataFrame:
    out = []
    for symbol in SYMBOLS:
        z = pd.concat(
            [
                normalize_source(frames[(symbol, WARMUP_YEAR)], symbol, WARMUP_YEAR),
                normalize_source(frames[(symbol, FRESH_YEAR)], symbol, FRESH_YEAR),
            ],
            ignore_index=True,
        )
        z = z.sort_values(["trading_day", "bar_end"], kind="stable").reset_index(drop=True)
        counts = z.groupby("trading_day", sort=False).size()
        if len(counts[counts != 48]):
            raise RuntimeError(f"non_48_row_trading_day:{symbol}")
        z["session"] = np.where(z.bar_end.dt.hour < 12, "AM", "PM")
        session_counts = z.groupby(["trading_day", "session"]).size()
        if len(session_counts[session_counts != 24]):
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
        z["year"] = pd.to_datetime(z.trading_day).dt.year.astype(int)
        out.append(z)
    return pd.concat(out, ignore_index=True).sort_values(
        ["symbol", "trading_day", "bar_end"], kind="stable"
    ).reset_index(drop=True)


def build_fresh_cohort(states: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (symbol, day_name), z0 in states.groupby(["symbol", "trading_day"], sort=False):
        year = int(str(day_name)[:4])
        if year != FRESH_YEAR:
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
                    "year": year,
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
    result = pd.DataFrame(rows).sort_values(
        ["symbol", "trading_day", "bar_end"], kind="stable"
    ).reset_index(drop=True)
    if set(result.year.unique()) != {FRESH_YEAR}:
        raise RuntimeError("fresh_oos_cohort_year_leak")
    return result


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
    required = {"names", "means", "sds", "beta", "challenger", "ridge_lambda"}
    if not required.issubset(model):
        raise RuntimeError("frozen_model_shape_invalid")
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
                "lower": float(np.quantile(value, BONFERRONI_LOWER_QUANTILE)),
            }
            for key, value in draws.items()
        },
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
            "status": "OUT_OF_SUPPORTED_FRESH_OOS",
            "support": support,
            "scientific_support": False,
        }
    ycol = f"normal_within_{horizon}m"
    z = scored[scored[ycol].notna()].copy()
    pooled = gains(z, horizon)
    by_symbol = {s: gains(z[z.symbol.eq(s)], horizon) for s in SYMBOLS}
    bootstrap = bootstrap_family(z, horizon, BOOTSTRAP_REPS, BOOTSTRAP_SEED)
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


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, tuple):
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
    identity, fresh_paths = validate_identity(inputs)
    model_freeze, calibration_freeze = validate_authority_inputs(inputs)
    warmup_paths = validate_warmup(inputs)

    frames = {}
    for symbol in SYMBOLS:
        frames[(symbol, WARMUP_YEAR)] = pd.read_parquet(warmup_paths[symbol])
        frames[(symbol, FRESH_YEAR)] = pd.read_parquet(fresh_paths[symbol])

    states = build_state_rows(frames)
    cohort = build_fresh_cohort(states)
    scored = score_cohort(cohort, model_freeze, calibration_freeze)
    horizon_results = {str(h): evaluate_horizon(scored, h) for h in HORIZONS}
    validated_count = sum(result["status"] == "FRESH_OOS_VALIDATED" for result in horizon_results.values())
    if validated_count == 2:
        overall = "FRESH_OOS_FULL_VALIDATION"
    elif validated_count == 1:
        overall = "FRESH_OOS_PARTIAL_VALIDATION"
    else:
        overall = "FRESH_OOS_NOT_VALIDATED"

    result = {
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
        "horizons": horizon_results,
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
