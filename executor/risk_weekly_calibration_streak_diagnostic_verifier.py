from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

EXPECTED_FILES = {
    "WEEKLY_CALIBRATION_BUCKETS.csv",
    "LONGEST_CALIBRATION_STREAK.csv",
    "STREAK_TAIL_DIAGNOSTICS.csv",
    "STREAK_REGIME_COMPOSITION.csv",
    "SUMMARY.json",
    "INPUT_DATA_RECEIPT.json",
    "MODEL_INPUT_RECEIPT.json",
}
PARENT_METRICS_SHA256 = "455a0f0d61993a933016e111aa1386eaf4ddf3ec6aeb9e28c109f08a559fd060"
V3_RESULT_SHA256 = "74df0b6b688d91f8f30c9dcdf3e16f9ddbe77204c9e702fe1d0476601ee3f5ca"
TAIL_ANCHOR = 0.2312353159391616
TAIL_LIMIT = 4.0
TOL = 1e-11


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module_unavailable:{name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def smooth_tail(p):
    p = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    z = np.log(p / (1 - p))
    a = np.log(TAIL_ANCHOR / (1 - TAIL_ANCHOR))
    z2 = a + TAIL_LIMIT * np.tanh((z - a) / TAIL_LIMIT)
    return 1 / (1 + np.exp(-z2))


def logloss_rows(y, p):
    y = np.asarray(y, float)
    q = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    return -(y * np.log(q) + (1 - y) * np.log(1 - q))


def top_share(values):
    x = np.asarray(values, float)
    x = x[np.isfinite(x) & (x > 0)]
    if not len(x) or float(x.sum()) <= 0:
        return 0.0
    n = max(1, int(np.ceil(len(x) * 0.05)))
    return float(np.sort(x)[-n:].sum() / x.sum())


def component(brier_gain, logloss_gain):
    bp = bool(brier_gain > 0)
    lp = bool(logloss_gain > 0)
    if bp and lp:
        return "pass"
    if (not bp) and lp:
        return "brier_only"
    if bp and (not lp):
        return "logloss_only"
    return "both"


def runs(flags):
    out = []
    start = None
    for i, flag in enumerate(list(flags) + [False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            out.append((start, i - 1, i - start))
            start = None
    return out


def reconstruct(inputs: Path):
    if sha256(inputs / "PARENT_TEMPORAL_METRICS_2W_V2.csv") != PARENT_METRICS_SHA256:
        raise RuntimeError("parent_metrics_identity_mismatch")
    if sha256(inputs / "V3_ACCEPTANCE_RESULT.json") != V3_RESULT_SHA256:
        raise RuntimeError("v3_result_identity_mismatch")
    v3 = json.loads((inputs / "V3_ACCEPTANCE_RESULT.json").read_text(encoding="utf-8"))
    node = v3.get("horizons", {}).get("15", {})
    weekly_v3 = node.get("levels", {}).get("weekly", {})
    if node.get("current_bottleneck") != "weekly.calibration" or weekly_v3.get("max_calibration_negative_streak") != 12:
        raise RuntimeError("v3_target_bottleneck_mismatch")

    temporal = load_module(inputs / "temporal_base.py", "verify_cal_streak_temporal")
    profile = json.loads((inputs / "TEMPORAL_PROFILE_V3.json").read_text(encoding="utf-8"))
    if profile.get("profile_id") != "risk-tool-v2-temporal-stability-hierarchical-v3":
        raise RuntimeError("v3_profile_identity_mismatch")
    gate = profile["levels"]["weekly"]["support"]
    base = temporal.load_base(inputs)
    model, cal, frames, receipt = temporal.load_inputs(inputs)
    frames, excluded = temporal.filter_complete_days(base, frames)
    states = base.build_state_rows(frames)
    cohort = base.build_primary_cohort(states)
    days = pd.concat([pd.to_datetime(f["trading_day"], errors="coerce") for f in frames.values()], ignore_index=True)
    ordered = sorted(temporal.labels_for_days(days)["weekly"].items())

    ycol = "normal_within_15m"
    z = cohort[cohort[ycol].notna()].copy()
    z["p_B"] = base.predict(model["models"]["15"]["B"], z)
    z["p_C"] = base.predict(model["models"]["15"]["C"], z)
    z["cal_B"] = temporal.platt(cal["fits"]["15"]["repeat_audit"]["B"], z.p_B)
    z["cal_C_pre_tail"] = temporal.platt(cal["fits"]["15"]["repeat_audit"]["C"], z.p_C)
    z["cal_C"] = smooth_tail(z.cal_C_pre_tail)
    z = temporal.add_period_labels(z)

    parent = pd.read_csv(inputs / "PARENT_TEMPORAL_METRICS_2W_V2.csv")
    parent = parent[(parent.horizon_minutes == 15) & (parent.period_level == "weekly")]
    authority = {str(r.period_label): r for _, r in parent.iterrows()}
    bucket_rows, tail_rows, regime_rows = [], [], []

    for i, (label, role) in enumerate(ordered):
        q = z.iloc[0:0].copy() if i < 1 else z[z.weekly_label.isin([ordered[i - 1][0], label])].copy()
        metric = temporal.metric_row(q, 15, "weekly", label, role)
        auth = authority.get(label)
        if auth is None:
            raise RuntimeError(f"authority_weekly_label_missing:{label}")
        for c in ("rows", "positive", "negative"):
            if int(metric[c]) != int(auth[c]):
                raise RuntimeError(f"authority_count_drift:{label}:{c}")
        evaluable = bool(
            role != "warmup"
            and int(metric["rows"]) >= gate["rows_min"]
            and int(metric["positive"]) >= gate["positive_min"]
            and int(metric["negative"]) >= gate["negative_min"]
        )
        if evaluable:
            for c in ("cal_brier_gain", "cal_logloss_gain"):
                if not np.isfinite(float(auth[c])) or abs(float(metric[c]) - float(auth[c])) > TOL:
                    raise RuntimeError(f"authority_gain_drift:{label}:{c}")
            pre = temporal.paired(q, ycol, "cal_B", "cal_C_pre_tail")
            bg = float(metric["cal_brier_gain"])
            lg = float(metric["cal_logloss_gain"])
            fc = component(bg, lg)
            y = q[ycol].astype(int).to_numpy()
            excess = np.maximum(logloss_rows(y, q.cal_C) - logloss_rows(y, q.cal_B), 0.0)
            tail_rows.append({
                "period_label": label,
                "role": role,
                "rows": int(len(q)),
                "event_rate": float(np.mean(y)),
                "mean_cal_B": float(q.cal_B.mean()),
                "mean_pre_tail_C": float(q.cal_C_pre_tail.mean()),
                "mean_post_tail_C": float(q.cal_C.mean()),
                "pre_tail_brier_gain": float(pre["brier_gain"]),
                "pre_tail_logloss_gain": float(pre["logloss_gain"]),
                "post_tail_brier_gain": bg,
                "post_tail_logloss_gain": lg,
                "tail_brier_gain_contribution": bg - float(pre["brier_gain"]),
                "tail_logloss_gain_contribution": lg - float(pre["logloss_gain"]),
                "mean_abs_tail_probability_shift": float(np.mean(np.abs(q.cal_C - q.cal_C_pre_tail))),
                "pre_tail_high_confidence_fraction": float(np.mean((q.cal_C_pre_tail <= 0.05) | (q.cal_C_pre_tail >= 0.95))),
                "post_tail_high_confidence_fraction": float(np.mean((q.cal_C <= 0.05) | (q.cal_C >= 0.95))),
                "positive_excess_logloss_sum": float(excess.sum()),
                "positive_excess_logloss_top5pct_share": top_share(excess),
                "median_shock_intensity": float(q.shock_intensity.median()),
                "median_vol_ratio": float(q.vol_ratio.median()),
                "failure_component": fc,
            })
            for dim, cats in (
                ("current_state", ("UNSAFE", "RECOVERING")),
                ("age_bucket", ("LT15", "M15_25", "M30_40", "GE45")),
                ("session", ("AM", "PM")),
            ):
                for cat in cats:
                    n = int(q[dim].eq(cat).sum())
                    regime_rows.append({
                        "period_label": label,
                        "dimension": dim,
                        "category": cat,
                        "rows": n,
                        "share": float(n / len(q)),
                    })
        else:
            fc = "unsupported"
        bucket_rows.append({
            "period_label": label,
            "role": role,
            "rows": int(metric["rows"]),
            "positive": int(metric["positive"]),
            "negative": int(metric["negative"]),
            "evaluable": evaluable,
            "cal_brier_gain": float(metric["cal_brier_gain"]),
            "cal_logloss_gain": float(metric["cal_logloss_gain"]),
            "failure_component": fc,
            "joint_calibration_pass": bool(evaluable and fc == "pass"),
        })

    buckets = pd.DataFrame(bucket_rows)
    evals = buckets[buckets.evaluable & buckets.role.ne("warmup")].reset_index(drop=True)
    streaks = runs(evals.failure_component.ne("pass").tolist())
    max_len = max((r[2] for r in streaks), default=0)
    maxima = [r for r in streaks if r[2] == max_len]
    if max_len != 12 or len(maxima) != 1:
        raise RuntimeError("longest_streak_identity_mismatch")
    s, e, _ = maxima[0]
    streak = evals.iloc[s : e + 1].copy()
    streak_labels = streak.period_label.tolist()
    pass_labels = evals.loc[evals.failure_component.eq("pass"), "period_label"].tolist()
    buckets["in_longest_streak"] = buckets.period_label.isin(streak_labels)

    tail = pd.DataFrame(tail_rows)
    tail["in_longest_streak"] = tail.period_label.isin(streak_labels)
    regimes = pd.DataFrame(regime_rows)
    regimes["in_longest_streak"] = regimes.period_label.isin(streak_labels)
    aggregates = []
    for group, labels in (("longest_streak", streak_labels), ("other_pass", pass_labels)):
        sub = regimes[regimes.period_label.isin(labels)]
        for (dim, cat), g in sub.groupby(["dimension", "category"], sort=True):
            aggregates.append({
                "period_label": f"__{group.upper()}__",
                "dimension": dim,
                "category": cat,
                "rows": int(g.rows.sum()),
                "share": float(g.share.mean()),
                "in_longest_streak": group == "longest_streak",
                "aggregation": "mean_endpoint_share",
            })
    regimes["aggregation"] = "endpoint"
    regimes = pd.concat([regimes, pd.DataFrame(aggregates)], ignore_index=True)

    labels = buckets.period_label.tolist()
    left, right = labels.index(streak_labels[0]), labels.index(streak_labels[-1])
    unsupported = buckets.iloc[left : right + 1].loc[lambda x: ~x.evaluable, "period_label"].tolist()
    failure_counts = streak.failure_component.value_counts().to_dict()
    summary = {
        "schema_id": "risk_tool_v2_15m_weekly_calibration_streak_diagnostic_summary@1.0",
        "profile": "risk-v2-weekly-calibration-streak-diagnostic-v1",
        "parent_metrics_authority_run": "34926868278-1",
        "v3_adjudication_authority_run": "34930354449-1",
        "target": "15m.weekly.calibration",
        "longest_evaluable_failure_streak": {
            "length": 12,
            "start_label": streak_labels[0],
            "end_label": streak_labels[-1],
            "labels": streak_labels,
            "failure_component_counts": {str(k): int(v) for k, v in failure_counts.items()},
            "unsupported_endpoints_inside_calendar_span": unsupported,
        },
        "tail_effect_within_streak": {
            "endpoints_tail_improves_brier_gain": int((tail[tail.in_longest_streak].tail_brier_gain_contribution > 0).sum()),
            "endpoints_tail_improves_logloss_gain": int((tail[tail.in_longest_streak].tail_logloss_gain_contribution > 0).sum()),
            "mean_tail_brier_gain_contribution": float(tail[tail.in_longest_streak].tail_brier_gain_contribution.mean()),
            "mean_tail_logloss_gain_contribution": float(tail[tail.in_longest_streak].tail_logloss_gain_contribution.mean()),
        },
        "diagnostic_only": True,
        "candidate_search": False,
        "calibration_refit": False,
        "numeric_threshold_change": False,
        "year_2026_read": False,
        "pnl": False,
        "production_authority": False,
    }
    input_receipt = {
        "source_receipt": receipt,
        "excluded_incomplete_days": excluded,
        "parent_metrics_sha256": PARENT_METRICS_SHA256,
        "v3_result_sha256": V3_RESULT_SHA256,
        "year_2026_read": False,
    }
    model_receipt = {
        "model_freeze_sha256": temporal.MODEL_SHA256,
        "calibration_freeze_sha256": temporal.CAL_SHA256,
        "tail_anchor": TAIL_ANCHOR,
        "tail_limit": TAIL_LIMIT,
        "new_training": False,
        "calibration_refit": False,
        "production_authority": False,
    }
    return buckets, streak, tail, regimes, summary, input_receipt, model_receipt


def compare_frame(path: Path, expected: pd.DataFrame):
    got = pd.read_csv(path)
    if list(got.columns) != list(expected.columns) or len(got) != len(expected):
        raise RuntimeError(f"frame_shape_mismatch:{path.name}")
    for column in expected.columns:
        e = expected[column]
        g = got[column]
        if pd.api.types.is_numeric_dtype(e.dtype):
            if not np.allclose(pd.to_numeric(g, errors="coerce"), pd.to_numeric(e, errors="coerce"), rtol=0, atol=TOL, equal_nan=True):
                raise RuntimeError(f"frame_numeric_mismatch:{path.name}:{column}")
        else:
            if g.fillna("").astype(str).tolist() != e.fillna("").astype(str).tolist():
                raise RuntimeError(f"frame_text_mismatch:{path.name}:{column}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--results", type=Path, required=True)
    a = p.parse_args()
    inputs, root = a.inputs.resolve(), a.results.resolve()
    if {p.name for p in root.iterdir() if p.is_file()} != EXPECTED_FILES:
        raise RuntimeError("result_file_set_mismatch")
    buckets, streak, tail, regimes, summary, input_receipt, model_receipt = reconstruct(inputs)
    compare_frame(root / "WEEKLY_CALIBRATION_BUCKETS.csv", buckets)
    compare_frame(root / "LONGEST_CALIBRATION_STREAK.csv", streak)
    compare_frame(root / "STREAK_TAIL_DIAGNOSTICS.csv", tail)
    compare_frame(root / "STREAK_REGIME_COMPOSITION.csv", regimes)
    if json.loads((root / "SUMMARY.json").read_text(encoding="utf-8")) != summary:
        raise RuntimeError("summary_mismatch")
    if json.loads((root / "INPUT_DATA_RECEIPT.json").read_text(encoding="utf-8")) != input_receipt:
        raise RuntimeError("input_receipt_mismatch")
    if json.loads((root / "MODEL_INPUT_RECEIPT.json").read_text(encoding="utf-8")) != model_receipt:
        raise RuntimeError("model_receipt_mismatch")
    print(json.dumps({
        "status": "passed",
        "streak_length": 12,
        "streak_start": summary["longest_evaluable_failure_streak"]["start_label"],
        "streak_end": summary["longest_evaluable_failure_streak"]["end_label"],
        "year_2026_read": False,
        "production_authority": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
