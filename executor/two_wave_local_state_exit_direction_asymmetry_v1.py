from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ISSUE = 647
SCHEMA_ID = "csi1000.two_wave_local_state_exit_direction_asymmetry_result@1.0"
EXPECTED_LEDGER_SHA256 = "c1ef13cfc3b2bc5669955ff62a5200b6c56c6868b459421d7e621e5ed189f46f"
EXPECTED_ROWS = 29_713
EXPECTED_YEARS = (2018, 2019, 2020)
EXPECTED_BLOCKS = 38
TARGET = "structural_exit_next8"
STATES = ("CURRENT_UP", "CURRENT_DOWN")
AGE_BINS = ("A1_1_4", "A2_5_8", "A3_9_16", "A4_17_32", "A5_33_PLUS")
COMPONENTS = (
    "risk_abs_ret_8",
    "risk_range_8",
    "risk_rv_8",
    "risk_efficiency_8",
)
REFERENCE = "compression_score"
METRICS = COMPONENTS + (REFERENCE,)
ALLOWED_COLUMNS = (
    "known_index",
    "knowledge_day",
    "year",
    "state",
    "state_age",
    "age_bin",
    TARGET,
    "abs_ret_8",
    "range_8",
    "rv_8",
    "efficiency_8",
    *COMPONENTS,
    REFERENCE,
    "risk_band",
)
BOOTSTRAP_REPETITIONS = 5000
BOOTSTRAP_SEED = 20260920
BLOCK_TRADING_DAYS = 20


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _quintile(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if not np.isfinite(arr).all() or np.any(arr < 0.0) or np.any(arr > 1.0):
        raise ValueError("risk percentile outside [0,1]")
    # side='left' freezes Q1=[0,.2], Q2=(.2,.4], ..., Q5=(.8,1].
    return np.searchsorted(np.asarray([0.2, 0.4, 0.6, 0.8]), arr, side="left") + 1


def _validate_frame(df: pd.DataFrame, *, enforce_canonical: bool) -> pd.DataFrame:
    missing = [c for c in ALLOWED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError("missing required columns: " + ",".join(missing))
    out = df.loc[:, list(ALLOWED_COLUMNS)].copy()
    if enforce_canonical and len(out) != EXPECTED_ROWS:
        raise ValueError("canonical row count drift")
    years = tuple(sorted(int(x) for x in out["year"].unique()))
    if years != EXPECTED_YEARS:
        raise ValueError("year identity drift")
    states = tuple(sorted(str(x) for x in out["state"].unique()))
    if states != tuple(sorted(STATES)):
        raise ValueError("state identity drift")
    if not set(out["age_bin"].astype(str)).issubset(set(AGE_BINS)):
        raise ValueError("age bin drift")
    if not set(pd.to_numeric(out[TARGET]).astype(int).unique()).issubset({0, 1}):
        raise ValueError("target must be binary")
    if out["known_index"].duplicated().any():
        raise ValueError("known_index must be unique")
    if not np.isfinite(out[list(COMPONENTS) + [REFERENCE]].to_numpy(float)).all():
        raise ValueError("non-finite risk metric")
    for c in COMPONENTS + (REFERENCE,):
        vals = out[c].to_numpy(float)
        if np.any(vals < 0.0) or np.any(vals > 1.0):
            raise ValueError("risk metric outside [0,1]")
    out["knowledge_day"] = pd.to_datetime(out["knowledge_day"], errors="raise")
    out["year"] = out["year"].astype(int)
    out["known_index"] = out["known_index"].astype(int)
    out[TARGET] = out[TARGET].astype(int)
    out["state"] = out["state"].astype(str)
    out["age_bin"] = out["age_bin"].astype(str)
    return out


def _attach_quintiles(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for metric in METRICS:
        out[f"q__{metric}"] = _quintile(out[metric].to_numpy(float))
    return out


def _base_exit_by_age(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for state in STATES:
        for age in AGE_BINS:
            part = df[(df["state"] == state) & (df["age_bin"] == age)]
            if part.empty:
                raise ValueError("empty state-age cell")
            rows.append(
                {
                    "state": state,
                    "age_bin": age,
                    "n": int(len(part)),
                    "events": int(part[TARGET].sum()),
                    "event_rate": float(part[TARGET].mean()),
                }
            )
    return rows


def _q_effect(part: pd.DataFrame, qcol: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for q in range(1, 6):
        cell = part[part[qcol] == q]
        if cell.empty:
            raise ValueError("empty quintile cell")
        rows.append(
            {
                "quintile": q,
                "n": int(len(cell)),
                "events": int(cell[TARGET].sum()),
                "event_rate": float(cell[TARGET].mean()),
            }
        )
    return {
        "quintiles": rows,
        "q5_minus_q1": float(rows[4]["event_rate"] - rows[0]["event_rate"]),
    }


def _age_effects(df: pd.DataFrame, state: str, metric: str) -> tuple[list[dict[str, Any]], float]:
    qcol = f"q__{metric}"
    rows: list[dict[str, Any]] = []
    supports: list[int] = []
    diffs: list[float] = []
    for age in AGE_BINS:
        part = df[(df["state"] == state) & (df["age_bin"] == age)]
        q1 = part[part[qcol] == 1]
        q5 = part[part[qcol] == 5]
        if q1.empty or q5.empty:
            raise ValueError("empty age-tail cell")
        diff = float(q5[TARGET].mean() - q1[TARGET].mean())
        support = int(len(q1) + len(q5))
        rows.append(
            {
                "age_bin": age,
                "q1_n": int(len(q1)),
                "q1_rate": float(q1[TARGET].mean()),
                "q5_n": int(len(q5)),
                "q5_rate": float(q5[TARGET].mean()),
                "q5_minus_q1": diff,
                "support": support,
            }
        )
        supports.append(support)
        diffs.append(diff)
    weights = np.asarray(supports, dtype=float)
    weights /= weights.sum()
    standardized = float(np.dot(weights, np.asarray(diffs, dtype=float)))
    for row, w in zip(rows, weights.tolist()):
        row["state_specific_weight"] = float(w)
    return rows, standardized


def _common_age_weights(df: pd.DataFrame, metric: str) -> dict[str, float]:
    qcol = f"q__{metric}"
    support = []
    for age in AGE_BINS:
        part = df[df["age_bin"] == age]
        n = int(part[qcol].isin([1, 5]).sum())
        if n <= 0:
            raise ValueError("empty common age support")
        support.append(n)
    arr = np.asarray(support, dtype=float)
    arr /= arr.sum()
    return {age: float(w) for age, w in zip(AGE_BINS, arr.tolist())}


def _common_age_standardized(age_rows: list[dict[str, Any]], weights: dict[str, float]) -> float:
    by_age = {str(r["age_bin"]): float(r["q5_minus_q1"]) for r in age_rows}
    return float(sum(weights[a] * by_age[a] for a in AGE_BINS))


def _year_effects(df: pd.DataFrame, state: str, metric: str) -> list[dict[str, Any]]:
    qcol = f"q__{metric}"
    rows = []
    for year in EXPECTED_YEARS:
        part = df[(df["state"] == state) & (df["year"] == year)]
        q1 = part[part[qcol] == 1]
        q5 = part[part[qcol] == 5]
        if q1.empty or q5.empty:
            raise ValueError("empty year-tail cell")
        diff = float(q5[TARGET].mean() - q1[TARGET].mean())
        rows.append({"year": year, "q5_minus_q1": diff, "positive": bool(diff > 0.0)})
    return rows


def _phase_effects(df: pd.DataFrame, state: str, metric: str) -> list[dict[str, Any]]:
    qcol = f"q__{metric}"
    rows = []
    for phase in range(8):
        part = df[(df["state"] == state) & ((df["known_index"] % 8) == phase)]
        q1 = part[part[qcol] == 1]
        q5 = part[part[qcol] == 5]
        if q1.empty or q5.empty:
            raise ValueError("empty phase-tail cell")
        diff = float(q5[TARGET].mean() - q1[TARGET].mean())
        rows.append({"phase": phase, "q5_minus_q1": diff, "positive": bool(diff > 0.0)})
    return rows


def _static_summary(df: pd.DataFrame) -> dict[str, Any]:
    result: dict[str, Any] = {"base_exit_by_age": _base_exit_by_age(df), "metrics": {}}
    for metric in METRICS:
        common_weights = _common_age_weights(df, metric)
        metric_out: dict[str, Any] = {"common_age_weights": common_weights, "states": {}}
        for state in STATES:
            part = df[df["state"] == state]
            pooled = _q_effect(part, f"q__{metric}")
            age_rows, state_std = _age_effects(df, state, metric)
            common_std = _common_age_standardized(age_rows, common_weights)
            years = _year_effects(df, state, metric)
            phases = _phase_effects(df, state, metric)
            metric_out["states"][state] = {
                "pooled": pooled,
                "by_age": age_rows,
                "state_specific_age_standardized_q5_minus_q1": state_std,
                "common_age_standardized_q5_minus_q1": common_std,
                "by_year": years,
                "positive_years": int(sum(int(r["positive"]) for r in years)),
                "by_phase": phases,
                "positive_phases": int(sum(int(r["positive"]) for r in phases)),
            }
        up = metric_out["states"]["CURRENT_UP"]
        down = metric_out["states"]["CURRENT_DOWN"]
        metric_out["common_age_interaction_down_minus_up"] = float(
            down["common_age_standardized_q5_minus_q1"]
            - up["common_age_standardized_q5_minus_q1"]
        )
        metric_out["pooled_direction_gap_down_minus_up"] = float(
            down["pooled"]["q5_minus_q1"] - up["pooled"]["q5_minus_q1"]
        )
        result["metrics"][metric] = metric_out

    ref = result["metrics"][REFERENCE]
    raw_gap = float(ref["pooled_direction_gap_down_minus_up"])
    common_gap = float(ref["common_age_interaction_down_minus_up"])
    reduction = None if raw_gap == 0.0 else float(1.0 - abs(common_gap) / abs(raw_gap))
    result["reference_age_composition"] = {
        "raw_direction_gap": raw_gap,
        "common_age_direction_gap": common_gap,
        "age_gap_reduction_fraction": reduction,
    }
    return result


def _block_tensor(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, int]:
    days = sorted(pd.Timestamp(x) for x in df["knowledge_day"].drop_duplicates().tolist())
    day_to_block = {day: i // BLOCK_TRADING_DAYS for i, day in enumerate(days)}
    blocks = max(day_to_block.values()) + 1
    state_pos = {s: i for i, s in enumerate(STATES)}
    age_pos = {a: i for i, a in enumerate(AGE_BINS)}
    metric_pos = {m: i for i, m in enumerate(METRICS)}
    counts = np.zeros((blocks, len(STATES), len(METRICS), len(AGE_BINS), 5), dtype=np.int64)
    events = np.zeros_like(counts)
    for row in df.itertuples(index=False):
        block = day_to_block[pd.Timestamp(row.knowledge_day)]
        s = state_pos[str(row.state)]
        a = age_pos[str(row.age_bin)]
        event = int(getattr(row, TARGET))
        for metric in METRICS:
            q = int(getattr(row, f"q__{metric}"))
            m = metric_pos[metric]
            counts[block, s, m, a, q - 1] += 1
            events[block, s, m, a, q - 1] += event
    return counts, events, blocks


def _effects_from_aggregate(counts: np.ndarray, events: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, float | None]:
    # arrays: state x metric x age x quintile. Missing tail support makes only
    # the affected standardized statistic invalid for this resample.
    q1_c = counts[..., 0].astype(float)
    q5_c = counts[..., 4].astype(float)
    q1_e = events[..., 0].astype(float)
    q5_e = events[..., 4].astype(float)

    state_std = np.full((len(STATES), len(METRICS)), np.nan, dtype=float)
    common_std = np.full_like(state_std, np.nan)
    interaction = np.full(len(METRICS), np.nan, dtype=float)

    for mi in range(len(METRICS)):
        age_diff = np.full((len(STATES), len(AGE_BINS)), np.nan, dtype=float)
        state_valid = [False] * len(STATES)
        for si in range(len(STATES)):
            valid = bool(np.all(q1_c[si, mi] > 0) and np.all(q5_c[si, mi] > 0))
            if not valid:
                continue
            state_valid[si] = True
            age_diff[si] = q5_e[si, mi] / q5_c[si, mi] - q1_e[si, mi] / q1_c[si, mi]
            support = q1_c[si, mi] + q5_c[si, mi]
            weights = support / support.sum()
            state_std[si, mi] = float(np.dot(weights, age_diff[si]))

        if all(state_valid):
            common_support = (
                q1_c[:, mi, :].sum(axis=0) + q5_c[:, mi, :].sum(axis=0)
            )
            if np.all(common_support > 0):
                weights = common_support / common_support.sum()
                for si in range(len(STATES)):
                    common_std[si, mi] = float(np.dot(weights, age_diff[si]))
                interaction[mi] = float(common_std[1, mi] - common_std[0, mi])

    ref_idx = len(METRICS) - 1
    pooled = np.full((len(STATES), len(METRICS)), np.nan, dtype=float)
    for si in range(len(STATES)):
        for mi in range(len(METRICS)):
            d1 = float(q1_c[si, mi].sum())
            d5 = float(q5_c[si, mi].sum())
            if d1 > 0 and d5 > 0:
                pooled[si, mi] = float(q5_e[si, mi].sum() / d5 - q1_e[si, mi].sum() / d1)
    raw_gap = float(pooled[1, ref_idx] - pooled[0, ref_idx]) if np.isfinite(pooled[:, ref_idx]).all() else np.nan
    common_gap = float(interaction[ref_idx])
    reduction = None
    if np.isfinite(raw_gap) and raw_gap != 0.0 and np.isfinite(common_gap):
        reduction = float(1.0 - abs(common_gap) / abs(raw_gap))
    return state_std, common_std, interaction, reduction


def _ci(values: list[float], repetitions: int) -> dict[str, Any]:
    arr = np.asarray([x for x in values if np.isfinite(x)], dtype=float)
    if len(arr) == 0:
        return {
            "median": None,
            "ci95": [None, None],
            "n_draws": 0,
            "valid_draw_fraction": 0.0,
        }
    return {
        "median": float(np.median(arr)),
        "ci95": [float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))],
        "n_draws": int(len(arr)),
        "valid_draw_fraction": float(len(arr) / repetitions),
    }


def _bootstrap(df: pd.DataFrame, repetitions: int, seed: int) -> dict[str, Any]:
    block_counts, block_events, blocks = _block_tensor(df)
    if repetitions <= 0:
        raise ValueError("bootstrap repetitions must be positive")
    rng = np.random.default_rng(seed)
    state_std_draws = [[[] for _ in METRICS] for _ in STATES]
    common_std_draws = [[[] for _ in METRICS] for _ in STATES]
    interaction_draws = [[] for _ in METRICS]
    reduction_draws: list[float] = []
    p = np.full(blocks, 1.0 / blocks)
    for _ in range(repetitions):
        mult = rng.multinomial(blocks, p)
        counts = np.tensordot(mult, block_counts, axes=(0, 0))
        events = np.tensordot(mult, block_events, axes=(0, 0))
        state_std, common_std, interaction, reduction = _effects_from_aggregate(counts, events)
        for si in range(len(STATES)):
            for mi in range(len(METRICS)):
                if np.isfinite(state_std[si, mi]):
                    state_std_draws[si][mi].append(float(state_std[si, mi]))
                if np.isfinite(common_std[si, mi]):
                    common_std_draws[si][mi].append(float(common_std[si, mi]))
        for mi in range(len(METRICS)):
            if np.isfinite(interaction[mi]):
                interaction_draws[mi].append(float(interaction[mi]))
        if reduction is not None and np.isfinite(reduction):
            reduction_draws.append(float(reduction))

    out: dict[str, Any] = {
        "seed": int(seed),
        "repetitions": int(repetitions),
        "block_trading_days": BLOCK_TRADING_DAYS,
        "blocks": int(blocks),
        "minimum_valid_draw_fraction": 0.98,
        "metrics": {},
        "reference_age_gap_reduction_fraction": _ci(reduction_draws, repetitions),
    }
    for mi, metric in enumerate(METRICS):
        m: dict[str, Any] = {
            "states": {},
            "common_age_interaction_down_minus_up": _ci(interaction_draws[mi], repetitions),
        }
        for si, state in enumerate(STATES):
            m["states"][state] = {
                "state_specific_age_standardized_q5_minus_q1": _ci(state_std_draws[si][mi], repetitions),
                "common_age_standardized_q5_minus_q1": _ci(common_std_draws[si][mi], repetitions),
            }
        out["metrics"][metric] = m
    return out


def _classify(static: dict[str, Any], boot: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    down_pass = 0
    up_pass = 0
    interaction_pass = 0
    component_checks: dict[str, Any] = {}
    minimum = float(boot["minimum_valid_draw_fraction"])

    def boot_positive(stat: dict[str, Any]) -> bool:
        lo = stat["ci95"][0]
        return (
            float(stat["valid_draw_fraction"]) >= minimum
            and lo is not None
            and float(lo) > 0.0
        )

    for metric in COMPONENTS:
        s = static["metrics"][metric]["states"]
        b = boot["metrics"][metric]
        down_stat = b["states"]["CURRENT_DOWN"]["state_specific_age_standardized_q5_minus_q1"]
        up_stat = b["states"]["CURRENT_UP"]["state_specific_age_standardized_q5_minus_q1"]
        interaction_stat = b["common_age_interaction_down_minus_up"]
        down_ok = (
            float(s["CURRENT_DOWN"]["state_specific_age_standardized_q5_minus_q1"]) > 0.0
            and boot_positive(down_stat)
            and int(s["CURRENT_DOWN"]["positive_years"]) >= 2
        )
        up_ok = (
            float(s["CURRENT_UP"]["state_specific_age_standardized_q5_minus_q1"]) > 0.0
            and boot_positive(up_stat)
            and int(s["CURRENT_UP"]["positive_years"]) >= 2
        )
        int_ok = boot_positive(interaction_stat)
        down_pass += int(down_ok)
        up_pass += int(up_ok)
        interaction_pass += int(int_ok)
        component_checks[metric] = {
            "current_down_pass": bool(down_ok),
            "current_up_pass": bool(up_ok),
            "interaction_pass": bool(int_ok),
            "current_down_valid_draw_fraction": float(down_stat["valid_draw_fraction"]),
            "current_up_valid_draw_fraction": float(up_stat["valid_draw_fraction"]),
            "interaction_valid_draw_fraction": float(interaction_stat["valid_draw_fraction"]),
        }

    coherent = down_pass >= 3 and up_pass <= 1 and interaction_pass >= 2
    reduction = static["reference_age_composition"]["age_gap_reduction_fraction"]
    reduction_stat = boot["reference_age_gap_reduction_fraction"]
    reduction_support = float(reduction_stat["valid_draw_fraction"]) >= minimum
    age_dominant = (
        (not coherent)
        and reduction is not None
        and float(reduction) >= 0.50
        and reduction_support
    )
    if coherent:
        label = "COMPONENT_COHERENT_DIRECTION_ASYMMETRY"
    elif age_dominant:
        label = "AGE_COMPOSITION_DOMINANT"
    else:
        label = "MIXED_OR_INCONCLUSIVE"
    return label, {
        "component_checks": component_checks,
        "current_down_components_pass": int(down_pass),
        "current_up_components_pass": int(up_pass),
        "interaction_components_pass": int(interaction_pass),
        "component_coherent_direction_asymmetry": bool(coherent),
        "reference_age_gap_reduction_valid_draw_fraction": float(reduction_stat["valid_draw_fraction"]),
        "age_composition_dominant": bool(age_dominant),
    }

def analyze(df: pd.DataFrame, *, repetitions: int = BOOTSTRAP_REPETITIONS, seed: int = BOOTSTRAP_SEED, enforce_canonical: bool = True) -> dict[str, Any]:
    clean = _validate_frame(df, enforce_canonical=enforce_canonical)
    scored = _attach_quintiles(clean)
    static = _static_summary(scored)
    boot = _bootstrap(scored, repetitions, seed)
    if enforce_canonical and int(boot["blocks"]) != EXPECTED_BLOCKS:
        raise ValueError("canonical block count drift")
    label, checks = _classify(static, boot)
    return {
        "schema_id": SCHEMA_ID,
        "issue": ISSUE,
        "status": "completed",
        "study_class": "mechanism_audit_only",
        "fresh_oos": False,
        "scientific_authority_from_this_study": False,
        "meta": {
            "rows": int(len(scored)),
            "years": [int(x) for x in sorted(scored["year"].unique())],
            "states": list(STATES),
            "components": list(COMPONENTS),
            "reference_score": REFERENCE,
        },
        "static": static,
        "bootstrap": boot,
        "mechanism_label": label,
        "mechanism_checks": checks,
        "interpretation": {
            "can_reclassify_issue_624": False,
            "can_authorize_down_only_rule": False,
            "can_authorize_new_context": False,
            "followup_requires_separate_preregistration": True,
        },
        "authority": {
            "signal": False,
            "router": False,
            "trade": False,
            "paper_trading": False,
            "live_trading": False,
            "production": False,
        },
    }


def run_file(ledger_path: Path, out_path: Path) -> dict[str, Any]:
    actual_sha = sha256_file(ledger_path)
    if actual_sha != EXPECTED_LEDGER_SHA256:
        raise ValueError("canonical ledger sha256 drift")
    df = pd.read_csv(ledger_path)
    result = analyze(df, enforce_canonical=True)
    result["input_identity"] = {
        "path_name": ledger_path.name,
        "sha256": actual_sha,
        "expected_sha256": EXPECTED_LEDGER_SHA256,
        "canonical_run_identity": "35488698309-1",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = run_file(Path(args.ledger), Path(args.out))
    print(result["mechanism_label"])


if __name__ == "__main__":
    main()
