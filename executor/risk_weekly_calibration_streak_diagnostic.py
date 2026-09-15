from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROFILE = "risk-v2-weekly-calibration-streak-diagnostic-v1"
HORIZON = 15
PARENT_RUN = "34926868278-1"
V3_RUN = "34930354449-1"
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


def top_share(values, frac=0.05):
    x = np.asarray(values, float)
    x = x[np.isfinite(x) & (x > 0)]
    if not len(x) or float(x.sum()) <= 0:
        return 0.0
    n = max(1, int(np.ceil(len(x) * frac)))
    return float(np.sort(x)[-n:].sum() / x.sum())


def failure_component(brier_gain, logloss_gain):
    bp = bool(brier_gain > 0)
    lp = bool(logloss_gain > 0)
    if bp and lp:
        return "pass"
    if (not bp) and lp:
        return "brier_only"
    if bp and (not lp):
        return "logloss_only"
    return "both"


def longest_runs(flags):
    runs = []
    start = None
    for i, flag in enumerate(flags + [False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            runs.append((start, i - 1, i - start))
            start = None
    return runs


def build(inputs: Path):
    if sha256(inputs / "PARENT_TEMPORAL_METRICS_2W_V2.csv") != PARENT_METRICS_SHA256:
        raise RuntimeError("parent_metrics_identity_mismatch")
    if sha256(inputs / "V3_ACCEPTANCE_RESULT.json") != V3_RESULT_SHA256:
        raise RuntimeError("v3_result_identity_mismatch")
    v3 = json.loads((inputs / "V3_ACCEPTANCE_RESULT.json").read_text(encoding="utf-8"))
    node = v3.get("horizons", {}).get("15", {})
    weekly = node.get("levels", {}).get("weekly", {})
    if (
        node.get("acceptance_state") != "IN_PROGRESS"
        or node.get("current_bottleneck") != "weekly.calibration"
        or weekly.get("max_calibration_negative_streak") != 12
    ):
        raise RuntimeError("v3_target_bottleneck_mismatch")

    temporal = load_module(inputs / "temporal_base.py", "cal_streak_temporal")
    two_week = load_module(inputs / "risk_temporal_stability_2week_v2.py", "cal_streak_2w")
    profile = json.loads((inputs / "TEMPORAL_PROFILE_V3.json").read_text(encoding="utf-8"))
    if profile.get("profile_id") != "risk-tool-v2-temporal-stability-hierarchical-v3":
        raise RuntimeError("v3_profile_identity_mismatch")
    support = profile["levels"]["weekly"]["support"]

    base = temporal.load_base(inputs)
    model, cal, frames, receipt = temporal.load_inputs(inputs)
    frames, excluded = temporal.filter_complete_days(base, frames)
    states = base.build_state_rows(frames)
    cohort = base.build_primary_cohort(states)
    market_days = pd.concat(
        [pd.to_datetime(frame["trading_day"], errors="coerce") for frame in frames.values()],
        ignore_index=True,
    )
    expected = temporal.labels_for_days(market_days)["weekly"]

    ycol = "normal_within_15m"
    z = cohort[cohort[ycol].notna()].copy()
    z["p_B"] = base.predict(model["models"]["15"]["B"], z)
    z["p_C"] = base.predict(model["models"]["15"]["C"], z)
    z["cal_B"] = temporal.platt(cal["fits"]["15"]["repeat_audit"]["B"], z.p_B)
    z["cal_C_pre_tail"] = temporal.platt(cal["fits"]["15"]["repeat_audit"]["C"], z.p_C)
    z["cal_C"] = smooth_tail(z.cal_C_pre_tail)
    z = temporal.add_period_labels(z)

    parent = pd.read_csv(inputs / "PARENT_TEMPORAL_METRICS_2W_V2.csv")
    parent = parent[(parent.horizon_minutes == 15) & (parent.period_level == "weekly")].copy()
    parent_index = {str(r.period_label): r for _, r in parent.iterrows()}
    ordered = sorted(expected.items())
    bucket_rows = []
    frames_by_label = {}
    regime_rows = []
    tail_rows = []

    for i, (label, role) in enumerate(ordered):
        frame = z.iloc[0:0].copy() if i < 1 else z[z.weekly_label.isin([ordered[i - 1][0], label])].copy()
        frames_by_label[label] = frame
        metric = temporal.metric_row(frame, 15, "weekly", label, role)
        if label not in parent_index:
            raise RuntimeError(f"parent_weekly_label_missing:{label}")
        auth = parent_index[label]
        for key, parent_key in (("rows", "rows"), ("positive", "positive"), ("negative", "negative")):
            if int(metric[key]) != int(auth[parent_key]):
                raise RuntimeError(f"authority_count_drift:{label}:{key}")
        evaluable = (
            role != "warmup"
            and int(metric["rows"]) >= support["rows_min"]
            and int(metric["positive"]) >= support["positive_min"]
            and int(metric["negative"]) >= support["negative_min"]
        )
        if evaluable:
            for key, parent_key in (("cal_brier_gain", "cal_brier_gain"), ("cal_logloss_gain", "cal_logloss_gain")):
                if not np.isfinite(float(auth[parent_key])) or abs(float(metric[key]) - float(auth[parent_key])) > TOL:
                    raise RuntimeError(f"authority_gain_drift:{label}:{key}")
            pre = temporal.paired(frame, ycol, "cal_B", "cal_C_pre_tail")
            post_brier = float(metric["cal_brier_gain"])
            post_log = float(metric["cal_logloss_gain"])
            component = failure_component(post_brier, post_log)
            y = frame[ycol].astype(int).to_numpy()
            ll_b = logloss_rows(y, frame.cal_B)
            ll_c = logloss_rows(y, frame.cal_C)
            excess = np.maximum(ll_c - ll_b, 0.0)
            tail_rows.append({
                "period_label": label,
                "role": role,
                "rows": int(len(frame)),
                "event_rate": float(np.mean(y)),
                "mean_cal_B": float(frame.cal_B.mean()),
                "mean_pre_tail_C": float(frame.cal_C_pre_tail.mean()),
                "mean_post_tail_C": float(frame.cal_C.mean()),
                "pre_tail_brier_gain": float(pre["brier_gain"]),
                "pre_tail_logloss_gain": float(pre["logloss_gain"]),
                "post_tail_brier_gain": post_brier,
                "post_tail_logloss_gain": post_log,
                "tail_brier_gain_contribution": post_brier - float(pre["brier_gain"]),
                "tail_logloss_gain_contribution": post_log - float(pre["logloss_gain"]),
                "mean_abs_tail_probability_shift": float(np.mean(np.abs(frame.cal_C - frame.cal_C_pre_tail))),
                "pre_tail_high_confidence_fraction": float(np.mean((frame.cal_C_pre_tail <= 0.05) | (frame.cal_C_pre_tail >= 0.95))),
                "post_tail_high_confidence_fraction": float(np.mean((frame.cal_C <= 0.05) | (frame.cal_C >= 0.95))),
                "positive_excess_logloss_sum": float(excess.sum()),
                "positive_excess_logloss_top5pct_share": top_share(excess, 0.05),
                "median_shock_intensity": float(frame.shock_intensity.median()),
                "median_vol_ratio": float(frame.vol_ratio.median()),
                "failure_component": component,
            })
            for dimension, categories in (
                ("current_state", ("UNSAFE", "RECOVERING")),
                ("age_bucket", ("LT15", "M15_25", "M30_40", "GE45")),
                ("session", ("AM", "PM")),
            ):
                for category in categories:
                    count = int(frame[dimension].eq(category).sum())
                    regime_rows.append({
                        "period_label": label,
                        "dimension": dimension,
                        "category": category,
                        "rows": count,
                        "share": float(count / len(frame)) if len(frame) else float("nan"),
                    })
        else:
            component = "unsupported"
        bucket_rows.append({
            "period_label": label,
            "role": role,
            "rows": int(metric["rows"]),
            "positive": int(metric["positive"]),
            "negative": int(metric["negative"]),
            "evaluable": bool(evaluable),
            "cal_brier_gain": float(metric["cal_brier_gain"]),
            "cal_logloss_gain": float(metric["cal_logloss_gain"]),
            "failure_component": component,
            "joint_calibration_pass": bool(evaluable and component == "pass"),
        })

    buckets = pd.DataFrame(bucket_rows)
    evals = buckets[buckets.evaluable & buckets.role.ne("warmup")].reset_index(drop=True)
    flags = evals.failure_component.ne("pass").tolist()
    runs = longest_runs(flags)
    max_len = max((x[2] for x in runs), default=0)
    maxima = [x for x in runs if x[2] == max_len]
    if max_len != 12 or len(maxima) != 1:
        raise RuntimeError(f"authority_streak_identity_mismatch:{max_len}:{len(maxima)}")
    start_i, end_i, _ = maxima[0]
    streak = evals.iloc[start_i : end_i + 1].copy()
    streak_labels = streak.period_label.tolist()
    pass_labels = evals.loc[evals.failure_component.eq("pass"), "period_label"].tolist()
    buckets["in_longest_streak"] = buckets.period_label.isin(streak_labels)

    tail = pd.DataFrame(tail_rows)
    tail["in_longest_streak"] = tail.period_label.isin(streak_labels)
    regimes = pd.DataFrame(regime_rows)
    regimes["in_longest_streak"] = regimes.period_label.isin(streak_labels)
    aggregate = []
    for group_name, labels in (("longest_streak", streak_labels), ("other_pass", pass_labels)):
        q = regimes[regimes.period_label.isin(labels)]
        for (dimension, category), g in q.groupby(["dimension", "category"], sort=True):
            aggregate.append({
                "period_label": f"__{group_name.upper()}__",
                "dimension": dimension,
                "category": category,
                "rows": int(g.rows.sum()),
                "share": float(g.share.mean()),
                "in_longest_streak": group_name == "longest_streak",
                "aggregation": "mean_endpoint_share",
            })
    regimes["aggregation"] = "endpoint"
    regimes = pd.concat([regimes, pd.DataFrame(aggregate)], ignore_index=True)

    all_labels = buckets.period_label.tolist()
    a, b = all_labels.index(streak_labels[0]), all_labels.index(streak_labels[-1])
    calendar_slice = buckets.iloc[a : b + 1]
    unsupported_inside = calendar_slice.loc[~calendar_slice.evaluable, "period_label"].tolist()
    failure_counts = streak.failure_component.value_counts().to_dict()
    summary = {
        "schema_id": "risk_tool_v2_15m_weekly_calibration_streak_diagnostic_summary@1.0",
        "profile": PROFILE,
        "parent_metrics_authority_run": PARENT_RUN,
        "v3_adjudication_authority_run": V3_RUN,
        "target": "15m.weekly.calibration",
        "longest_evaluable_failure_streak": {
            "length": 12,
            "start_label": streak_labels[0],
            "end_label": streak_labels[-1],
            "labels": streak_labels,
            "failure_component_counts": {str(k): int(v) for k, v in failure_counts.items()},
            "unsupported_endpoints_inside_calendar_span": unsupported_inside,
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
    receipts = {
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
    return buckets, streak, tail, regimes, summary, receipts, model_receipt


def run(inputs: Path, out: Path):
    buckets, streak, tail, regimes, summary, receipts, model_receipt = build(inputs)
    out.mkdir(parents=True, exist_ok=False)
    buckets.to_csv(out / "WEEKLY_CALIBRATION_BUCKETS.csv", index=False)
    streak.to_csv(out / "LONGEST_CALIBRATION_STREAK.csv", index=False)
    tail.to_csv(out / "STREAK_TAIL_DIAGNOSTICS.csv", index=False)
    regimes.to_csv(out / "STREAK_REGIME_COMPOSITION.csv", index=False)
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    (out / "INPUT_DATA_RECEIPT.json").write_text(json.dumps(receipts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "MODEL_INPUT_RECEIPT.json").write_text(json.dumps(model_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    run(a.inputs.resolve(), a.out.resolve())


if __name__ == "__main__":
    main()
