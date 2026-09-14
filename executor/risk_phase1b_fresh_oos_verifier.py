from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

TASK_ID = "CSI1000-RISK-V2-PHASE1B-FRESH-OOS-2026-V1-20260914"
SCHEMA_ID = "risk_tool_v2_phase1b_fresh_oos_result@1.0"
SYMBOLS = ("000688.SH", "000852.SH")
HORIZONS = (15, 30)
FRESH_YEAR = 2026
BOOTSTRAP_REPS = 5000
BOOTSTRAP_SEED = 20260914
FAMILY_SIZE = 6
BONFERRONI_LOWER_QUANTILE = 0.05 / FAMILY_SIZE
LOGLOSS_CLIP = 1e-12
ATOL = 1e-11


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
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
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
    z = frame[frame[ycol].notna()].copy()
    y = z[ycol].astype(int).to_numpy()
    b_raw = score(y, z[f"p_B_raw_{horizon}m"].to_numpy(float))
    c_raw = score(y, z[f"p_C_raw_{horizon}m"].to_numpy(float))
    b_cal = score(y, z[f"p_B_cal_{horizon}m"].to_numpy(float))
    c_cal = score(y, z[f"p_C_cal_{horizon}m"].to_numpy(float))
    return {
        "B_raw": b_raw,
        "C_raw": c_raw,
        "B_cal": b_cal,
        "C_cal": c_cal,
        "auroc_gain": float(c_raw["auroc"] - b_raw["auroc"]),
        "brier_gain": float(b_cal["brier"] - c_cal["brier"]),
        "logloss_gain": float(b_cal["log_loss"] - c_cal["log_loss"]),
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
        "horizon_minutes": int(horizon),
        "fresh_oos_rows": int(len(z)),
        "fresh_oos_min_symbol_rows": int(symbol_counts.min()) if len(symbol_counts) else 0,
        "fresh_oos_positive": int(y.sum()) if len(y) else 0,
        "fresh_oos_negative": int((1 - y).sum()) if len(y) else 0,
        "supported_horizon": bool(all(checks.values())),
        "checks": checks,
    }


def bootstrap_family(frame: pd.DataFrame, horizon: int, repetitions: int = BOOTSTRAP_REPS, seed: int = BOOTSTRAP_SEED) -> dict:
    ycol = f"normal_within_{horizon}m"
    z = frame[frame[ycol].notna()].copy()
    groups = [g for _, g in z.groupby("trading_day", sort=True)]
    if not groups:
        raise RuntimeError("bootstrap_no_clusters")
    point = gains(z, horizon)
    rng = np.random.default_rng(seed)
    draws = {
        "auroc_gain": np.empty(repetitions, dtype=float),
        "brier_gain": np.empty(repetitions, dtype=float),
        "logloss_gain": np.empty(repetitions, dtype=float),
    }
    for i in range(repetitions):
        indexes = rng.integers(0, len(groups), size=len(groups))
        sampled = pd.concat([groups[j] for j in indexes], ignore_index=True)
        try:
            g = gains(sampled, horizon)
        except RuntimeError as exc:
            if str(exc) != "auc_single_class":
                raise
            # A single-class bootstrap draw contains no AUROC information. The
            # confirmatory implementation treats this as an invalid sample and
            # deterministically redraws from the same RNG stream.
            while True:
                indexes = rng.integers(0, len(groups), size=len(groups))
                sampled = pd.concat([groups[j] for j in indexes], ignore_index=True)
                try:
                    g = gains(sampled, horizon)
                    break
                except RuntimeError as retry:
                    if str(retry) != "auc_single_class":
                        raise
        for key in draws:
            draws[key][i] = float(g[key])
    return {
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


def close(a, b, atol: float = ATOL) -> bool:
    return bool(np.allclose(np.asarray(a, dtype=float), np.asarray(b, dtype=float), rtol=0.0, atol=atol, equal_nan=True))


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


def recompute_horizon(scored: pd.DataFrame, horizon: int) -> dict:
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
    by_symbol = {symbol: gains(z[z.symbol.eq(symbol)], horizon) for symbol in SYMBOLS}
    bootstrap = bootstrap_family(z, horizon)
    gates = {
        "raw_auroc_gain_gt_zero": pooled["auroc_gain"] > 0,
        "raw_auroc_family_adjusted_bootstrap_lower_gt_zero": bootstrap["metrics"]["auroc_gain"]["lower"] > 0,
        "raw_auroc_gain_each_symbol_nonnegative": all(by_symbol[s]["auroc_gain"] >= 0 for s in SYMBOLS),
        "calibrated_brier_gain_gt_zero": pooled["brier_gain"] > 0,
        "calibrated_brier_family_adjusted_bootstrap_lower_gt_zero": bootstrap["metrics"]["brier_gain"]["lower"] > 0,
        "calibrated_logloss_gain_gt_zero": pooled["logloss_gain"] > 0,
        "calibrated_logloss_family_adjusted_bootstrap_lower_gt_zero": bootstrap["metrics"]["logloss_gain"]["lower"] > 0,
        "calibrated_brier_gain_each_symbol_nonnegative": all(by_symbol[s]["brier_gain"] >= 0 for s in SYMBOLS),
        "calibrated_logloss_gain_each_symbol_nonnegative": all(by_symbol[s]["logloss_gain"] >= 0 for s in SYMBOLS),
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


def verify(results: Path) -> dict:
    expected_files = {"FRESH_OOS_SCORED.parquet", "SUMMARY.json"}
    present = {p.name for p in results.iterdir() if p.is_file()}
    if present != expected_files:
        raise RuntimeError("result_file_set_mismatch")
    summary = json.loads((results / "SUMMARY.json").read_text())
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
    if set(scored.symbol.dropna().unique()) != set(SYMBOLS):
        raise RuntimeError("scored_symbol_set_mismatch")
    if set(scored.year.dropna().astype(int).unique()) != {FRESH_YEAR}:
        raise RuntimeError("scored_year_leak")
    if scored.empty:
        raise RuntimeError("scored_empty")

    horizons = {str(h): recompute_horizon(scored, h) for h in HORIZONS}
    validated = sum(horizons[str(h)]["status"] == "FRESH_OOS_VALIDATED" for h in HORIZONS)
    if validated == 2:
        overall = "FRESH_OOS_FULL_VALIDATION"
    elif validated == 1:
        overall = "FRESH_OOS_PARTIAL_VALIDATION"
    else:
        overall = "FRESH_OOS_NOT_VALIDATED"
    expected_summary = {
        "schema_id": SCHEMA_ID,
        "task_id": TASK_ID,
        "fresh_oos_year": FRESH_YEAR,
        "horizons": horizons,
        "overall_status": overall,
        "production_authority": False,
    }
    compare_tree(summary, expected_summary)
    return expected_summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    verified = verify(args.results.resolve())
    print(json.dumps({
        "status": "verified",
        "overall_status": verified["overall_status"],
        "production_authority": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
