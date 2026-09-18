"""Post-t+8 state persistence study for frozen Two-Wave current-band states.

Issue #429 preregistration is authoritative. This module studies the dynamics
of the already-frozen delayed state process. It never changes the primary
classifier and never consumes PnL, future-return magnitude, routing or trade
outcomes.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

import two_wave_delayed_causal_wrapper_v1 as wrapper


HORIZONS = (1, 2, 4, 8, 12, 16, 24, 32)
PARENT_PERIODS = (128, 256)
TAU_PARENT = 0.20
FIRST_COMMON_K = 255
MAX_HORIZON = max(HORIZONS)
BOOTSTRAP_REPLICATES = 2000
BOOTSTRAP_SEED = 20260918

DIRECTIONAL_STATES = ("CURRENT_UP", "CURRENT_DOWN")
PRIMARY_STATES = (
    "CURRENT_UP",
    "CURRENT_RANGE",
    "CURRENT_DOWN",
    "LOW_AMPLITUDE_VETO",
    "FINER_SCALE_OUT_OF_BAND",
)
PARENT_PHASES = ("PARENT_UP", "PARENT_RANGE", "PARENT_DOWN")
RELATIONS = ("ALIGNED", "NEUTRAL", "OPPOSED")


def normalized_ols_drift(values: Sequence[float]) -> float:
    """Causal OLS migration normalized by the path's own log-price range."""
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or len(x) < 2:
        raise ValueError("one-dimensional path with at least two prices required")
    if not np.isfinite(x).all() or np.any(x <= 0):
        raise ValueError("finite positive prices required")
    y = np.log(x)
    span = float(y.max() - y.min())
    if span <= 1e-15:
        return 0.0
    t = np.arange(len(y), dtype=float)
    slope = float(np.polyfit(t, y, 1)[0])
    return slope * (len(y) - 1) / span


def parent_phase(values: Sequence[float]) -> tuple[str, float]:
    g = normalized_ols_drift(values)
    if g > TAU_PARENT:
        return "PARENT_UP", g
    if g < -TAU_PARENT:
        return "PARENT_DOWN", g
    return "PARENT_RANGE", g


def directional_relation(primary_state: str, phase: str) -> str | None:
    if primary_state == "CURRENT_UP":
        if phase == "PARENT_UP":
            return "ALIGNED"
        if phase == "PARENT_DOWN":
            return "OPPOSED"
        if phase == "PARENT_RANGE":
            return "NEUTRAL"
    elif primary_state == "CURRENT_DOWN":
        if phase == "PARENT_DOWN":
            return "ALIGNED"
        if phase == "PARENT_UP":
            return "OPPOSED"
        if phase == "PARENT_RANGE":
            return "NEUTRAL"
    return None
def consensus_phase(phase128: str, phase256: str) -> str:
    if phase128 == phase256 == "PARENT_UP":
        return "CONSENSUS_UP"
    if phase128 == phase256 == "PARENT_RANGE":
        return "CONSENSUS_RANGE"
    if phase128 == phase256 == "PARENT_DOWN":
        return "CONSENSUS_DOWN"
    return "MIXED"


def consensus_relation(
    primary_state: str,
    relation128: str | None,
    relation256: str | None,
) -> str | None:
    if primary_state not in DIRECTIONAL_STATES:
        return None
    if relation128 == relation256 == "ALIGNED":
        return "CONSENSUS_ALIGNED"
    if relation128 == relation256 == "OPPOSED":
        return "CONSENSUS_OPPOSED"
    return "OTHER_OR_MIXED"


def _state_by_known_index(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> dict[int, str]:
    rows = wrapper.replay_wrapper(highs, lows, closes)
    return {row.known_from_index: row.label for row in rows}


def delayed_state_outcomes(
    states: Mapping[int, str],
    *,
    known_index: int,
    state: str,
) -> dict[str, object]:
    """Compute outcomes strictly from k+1..k+32 of the delayed state process."""
    future = [states[known_index + j] for j in range(1, MAX_HORIZON + 1)]

    first_change_delay: int | None = None
    first_exit_state: str | None = None
    for j, future_state in enumerate(future, start=1):
        if future_state != state:
            first_change_delay = j
            first_exit_state = future_state
            break

    opposite = None
    if state == "CURRENT_UP":
        opposite = "CURRENT_DOWN"
    elif state == "CURRENT_DOWN":
        opposite = "CURRENT_UP"

    first_slap_delay: int | None = None
    if opposite is not None:
        for j, future_state in enumerate(future, start=1):
            if future_state == opposite:
                first_slap_delay = j
                break

    out: dict[str, object] = {
        "first_change_delay": first_change_delay,
        "first_exit_state": first_exit_state,
        "lifetime_censored_32": first_change_delay is None,
        "first_slap_delay": first_slap_delay,
    }
    for h in HORIZONS:
        window = future[:h]
        out[f"survive_{h}"] = int(all(x == state for x in window))
        if opposite is not None:
            out[f"slap_{h}"] = int(opposite in window)
            out[f"end_same_dir_{h}"] = int(future[h - 1] == state)
        else:
            out[f"slap_{h}"] = np.nan
            out[f"end_same_dir_{h}"] = np.nan
    return out


def build_event_ledger(
    bars: pd.DataFrame,
) -> pd.DataFrame:
    required = {"high", "low", "close", "trading_day"}
    if not required.issubset(bars.columns):
        raise ValueError("bars missing required columns")

    high = bars["high"].to_numpy(float)
    low = bars["low"].to_numpy(float)
    close = bars["close"].to_numpy(float)
    states = _state_by_known_index(high, low, close)

    last_k = len(bars) - 1 - MAX_HORIZON
    if last_k < FIRST_COMMON_K:
        raise ValueError("insufficient common support")

    rows: list[dict[str, object]] = []
    for k in range(FIRST_COMMON_K, last_k + 1):
        state = states.get(k)
        if state not in PRIMARY_STATES:
            raise AssertionError(f"missing frozen state at k={k}")

        p128, g128 = parent_phase(close[k - 127 : k + 1])
        p256, g256 = parent_phase(close[k - 255 : k + 1])
        r128 = directional_relation(state, p128)
        r256 = directional_relation(state, p256)
        cphase = consensus_phase(p128, p256)
        crel = consensus_relation(state, r128, r256)

        outcomes = delayed_state_outcomes(
            states,
            known_index=k,
            state=state,
        )

        day = pd.Timestamp(bars.iloc[k]["trading_day"])
        row: dict[str, object] = {
            "known_index": k,
            "target_index": k - 8,
            "knowledge_day": day.strftime("%Y-%m-%d"),
            "year": int(day.year),
            "state": state,
            "parent_phase_128": p128,
            "parent_g_128": g128,
            "parent_phase_256": p256,
            "parent_g_256": g256,
            "relation_128": r128,
            "relation_256": r256,
            "parent_consensus_phase": cphase,
            "parent_consensus_relation": crel,
            **outcomes,
        }
        rows.append(row)

    frame = pd.DataFrame(rows)
    expected = len(bars) - MAX_HORIZON - FIRST_COMMON_K
    if len(frame) != expected:
        raise AssertionError((len(frame), expected))
    return frame
def baseline_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for state, part in events.groupby("state", sort=False):
        support = len(part)
        first = part["first_change_delay"].dropna().astype(int)
        base = {
            "state": state,
            "support": support,
            "exit_within_32_rate": float(part["first_change_delay"].notna().mean()),
            "survive_32_rate": float(part["survive_32"].mean()),
            "median_first_change_if_observed": (
                float(first.median()) if len(first) else np.nan
            ),
        }
        for h in HORIZONS:
            base[f"survive_{h}"] = float(part[f"survive_{h}"].mean())
            if state in DIRECTIONAL_STATES:
                base[f"slap_{h}"] = float(part[f"slap_{h}"].mean())
                base[f"end_same_dir_{h}"] = float(
                    part[f"end_same_dir_{h}"].mean()
                )
        rows.append(base)
    return pd.DataFrame(rows)


def first_exit_matrix(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for state, part in events.groupby("state", sort=False):
        counts = Counter(part["first_exit_state"].fillna("NO_EXIT_WITHIN_32"))
        total = len(part)
        for dest, count in sorted(counts.items()):
            rows.append(
                {
                    "state": state,
                    "first_exit_state": dest,
                    "count": int(count),
                    "rate": float(count / total),
                }
            )
    return pd.DataFrame(rows)


def raw_parent_phase_survival(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for period in PARENT_PERIODS:
        phase_col = f"parent_phase_{period}"
        for (state, phase), part in events.groupby(["state", phase_col]):
            for h in HORIZONS:
                rows.append(
                    {
                        "period": period,
                        "state": state,
                        "parent_phase": phase,
                        "horizon": h,
                        "support": len(part),
                        "survival": float(part[f"survive_{h}"].mean()),
                    }
                )
    return pd.DataFrame(rows)
def directional_relation_summary(events: pd.DataFrame) -> pd.DataFrame:
    directional = events[events["state"].isin(DIRECTIONAL_STATES)].copy()
    rows: list[dict[str, object]] = []
    for period in PARENT_PERIODS:
        relation_col = f"relation_{period}"
        for relation, part in directional.groupby(relation_col):
            for h in HORIZONS:
                rows.append(
                    {
                        "period": period,
                        "relation": relation,
                        "horizon": h,
                        "support": len(part),
                        "survival": float(part[f"survive_{h}"].mean()),
                        "slap": float(part[f"slap_{h}"].mean()),
                        "end_same_dir": float(part[f"end_same_dir_{h}"].mean()),
                    }
                )
    return pd.DataFrame(rows)


def consensus_summary(events: pd.DataFrame) -> pd.DataFrame:
    directional = events[events["state"].isin(DIRECTIONAL_STATES)].copy()
    rows: list[dict[str, object]] = []
    for relation, part in directional.groupby("parent_consensus_relation"):
        for h in HORIZONS:
            rows.append(
                {
                    "consensus_relation": relation,
                    "horizon": h,
                    "support": len(part),
                    "survival": float(part[f"survive_{h}"].mean()),
                    "slap": float(part[f"slap_{h}"].mean()),
                    "end_same_dir": float(part[f"end_same_dir_{h}"].mean()),
                }
            )
    return pd.DataFrame(rows)


def _cluster_arrays(
    events: pd.DataFrame,
    period: int,
    horizon: int,
    metric: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    directional = events[events["state"].isin(DIRECTIONAL_STATES)].copy()
    relation = f"relation_{period}"
    grouped = directional.groupby("knowledge_day", sort=True)
    days = sorted(grouped.groups)
    a_num = []
    a_den = []
    o_num = []
    o_den = []
    column = f"{metric}_{horizon}"
    for day in days:
        part = grouped.get_group(day)
        aligned = part[part[relation] == "ALIGNED"]
        opposed = part[part[relation] == "OPPOSED"]
        a_num.append(float(aligned[column].sum()))
        a_den.append(float(len(aligned)))
        o_num.append(float(opposed[column].sum()))
        o_den.append(float(len(opposed)))
    return (
        np.asarray(a_num),
        np.asarray(a_den),
        np.asarray(o_num),
        np.asarray(o_den),
        days,
    )


def cluster_bootstrap_effect(
    events: pd.DataFrame,
    *,
    period: int,
    horizon: int,
    metric: str,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, float]:
    if metric not in {"survive", "slap", "end_same_dir"}:
        raise ValueError("unsupported metric")
    a_num, a_den, o_num, o_den, days = _cluster_arrays(
        events, period, horizon, metric
    )
    if not len(days):
        raise ValueError("no clusters")

    total_a_den = float(a_den.sum())
    total_o_den = float(o_den.sum())
    if total_a_den <= 0 or total_o_den <= 0:
        raise ValueError("aligned/opposed support required")
    point = float(a_num.sum() / total_a_den - o_num.sum() / total_o_den)

    rng = np.random.default_rng(seed + period * 100 + horizon)
    n = len(days)
    effects = np.empty(replicates, dtype=float)
    valid = 0
    for _ in range(replicates):
        idx = rng.integers(0, n, size=n)
        ad = float(a_den[idx].sum())
        od = float(o_den[idx].sum())
        if ad <= 0 or od <= 0:
            continue
        effects[valid] = (
            float(a_num[idx].sum()) / ad
            - float(o_num[idx].sum()) / od
        )
        valid += 1
    if valid < int(0.95 * replicates):
        raise RuntimeError("too many invalid bootstrap replicates")
    effects = effects[:valid]
    lo, hi = np.quantile(effects, [0.025, 0.975])
    return {
        "effect": point,
        "ci_low": float(lo),
        "ci_high": float(hi),
        "valid_bootstrap_replicates": int(valid),
        "aligned_support": int(total_a_den),
        "opposed_support": int(total_o_den),
    }
def bootstrap_effect_table(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for period in PARENT_PERIODS:
        for h in HORIZONS:
            for metric in ("survive", "slap", "end_same_dir"):
                result = cluster_bootstrap_effect(
                    events,
                    period=period,
                    horizon=h,
                    metric=metric,
                )
                rows.append(
                    {
                        "period": period,
                        "horizon": h,
                        "metric": metric,
                        **result,
                    }
                )
    return pd.DataFrame(rows)


def yearly_effects(events: pd.DataFrame) -> pd.DataFrame:
    directional = events[events["state"].isin(DIRECTIONAL_STATES)].copy()
    rows: list[dict[str, object]] = []
    for period in PARENT_PERIODS:
        relation_col = f"relation_{period}"
        for year, year_part in directional.groupby("year"):
            aligned = year_part[year_part[relation_col] == "ALIGNED"]
            opposed = year_part[year_part[relation_col] == "OPPOSED"]
            for h in HORIZONS:
                for metric in ("survive", "slap", "end_same_dir"):
                    column = f"{metric}_{h}"
                    effect = np.nan
                    if len(aligned) and len(opposed):
                        effect = float(
                            aligned[column].mean() - opposed[column].mean()
                        )
                    rows.append(
                        {
                            "period": period,
                            "year": int(year),
                            "horizon": h,
                            "metric": metric,
                            "aligned_support": len(aligned),
                            "opposed_support": len(opposed),
                            "effect": effect,
                        }
                    )
    return pd.DataFrame(rows)


def _metric_gate(
    bootstrap: pd.DataFrame,
    yearly: pd.DataFrame,
    *,
    period: int,
    metric: str,
) -> dict[str, object]:
    b = bootstrap[(bootstrap["period"] == period) & (bootstrap["metric"] == metric)]
    h8 = b[b["horizon"] == 8].iloc[0]
    h16 = b[b["horizon"] == 16].iloc[0]
    y8 = yearly[
        (yearly["period"] == period)
        & (yearly["metric"] == metric)
        & (yearly["horizon"] == 8)
    ]
    if metric == "survive":
        practical = float(h8.effect) >= 0.05
        ci_ok = float(h8.ci_low) > 0.0
        h16_ok = (
            float(h16.effect) > 0.0
            and abs(float(h16.effect)) >= 0.5 * abs(float(h8.effect))
        )
        year_signs = int((y8["effect"] > 0).sum())
    elif metric == "slap":
        practical = float(h8.effect) <= -0.03
        ci_ok = float(h8.ci_high) < 0.0
        h16_ok = (
            float(h16.effect) < 0.0
            and abs(float(h16.effect)) >= 0.5 * abs(float(h8.effect))
        )
        year_signs = int((y8["effect"] < 0).sum())
    else:
        raise ValueError("gate only defined for survive/slap")

    support_ok = (
        int(h8.aligned_support) >= 500 and int(h8.opposed_support) >= 500
    )
    passed = bool(
        support_ok
        and practical
        and ci_ok
        and h16_ok
        and year_signs >= 5
    )
    return {
        "period": period,
        "metric": metric,
        "h8_effect": float(h8.effect),
        "h8_ci_low": float(h8.ci_low),
        "h8_ci_high": float(h8.ci_high),
        "h16_effect": float(h16.effect),
        "aligned_support": int(h8.aligned_support),
        "opposed_support": int(h8.opposed_support),
        "expected_sign_years": year_signs,
        "support_ok": support_ok,
        "practical_effect_ok": practical,
        "ci_ok": ci_ok,
        "h16_persistence_ok": h16_ok,
        "passed": passed,
    }


def conditioner_verdicts(
    bootstrap: pd.DataFrame,
    yearly: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[int, str]]:
    details = []
    verdicts: dict[int, str] = {}
    for period in PARENT_PERIODS:
        survive = _metric_gate(
            bootstrap, yearly, period=period, metric="survive"
        )
        slap = _metric_gate(
            bootstrap, yearly, period=period, metric="slap"
        )
        details.extend([survive, slap])
        supported = bool(survive["passed"] or slap["passed"])
        verdicts[period] = (
            "SUPPORTED_PERSISTENCE_CONDITIONER"
            if supported
            else "NOT_SUPPORTED_AS_PERSISTENCE_CONDITIONER"
        )
    return pd.DataFrame(details), verdicts
