"""Local-only compression ranking of same-frequency directional state-exit hazard.

Issue #624 preregistration is authoritative.

The study uses only:
- the frozen accepted delayed-causal current-band state process;
- native OHLC bars available at the knowledge clock.

No parent-frequency state, PnL, trade outcome, route outcome, or future-state
information enters score construction.
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

import two_wave_delayed_causal_wrapper_v1 as wrapper
import two_wave_current_band_recognizer_v1 as oracle


FEATURES = ("abs_ret_8", "range_8", "rv_8", "efficiency_8")
TEST_YEARS = (2018, 2019, 2020)
DIRECTIONAL_STATES = ("CURRENT_UP", "CURRENT_DOWN")
CARRIER_DIRECTIONAL_STATES = ("DIR_UP", "DIR_DOWN")
CARRIER_RANGE = "DIR_RANGE"
AGE_BINS = ("A1_1_4", "A2_5_8", "A3_9_16", "A4_17_32", "A5_33_PLUS")
PRIMARY_HORIZON = 8
SECONDARY_HORIZON = 16
BOOT_REPS = 5000
BOOT_SEED = 20260920
BLOCK_DAYS = 20
MIN_TOTAL_SCORED = 20_000
MIN_STATE_BAND = 1_000
MIN_AGE_STRATUM_COMBINED = 200
MIN_VALID_BOOT = int(0.95 * BOOT_REPS)


def _require_bars(bars: pd.DataFrame) -> None:
    required = {"timestamp", "trading_day", "high", "low", "close"}
    missing = required.difference(bars.columns)
    if missing:
        raise ValueError(f"bars missing required columns: {sorted(missing)}")
    if len(bars) <= wrapper.FIRST_ELIGIBLE_K + SECONDARY_HORIZON:
        raise ValueError("insufficient bars")


def _age_bin(age: int) -> str:
    if age <= 0:
        raise ValueError("state age must be positive")
    if age <= 4:
        return AGE_BINS[0]
    if age <= 8:
        return AGE_BINS[1]
    if age <= 16:
        return AGE_BINS[2]
    if age <= 32:
        return AGE_BINS[3]
    return AGE_BINS[4]


def _local_features(
    high: np.ndarray,
    low: np.ndarray,
    log_close: np.ndarray,
    k: int,
) -> dict[str, float]:
    if k < 8:
        raise ValueError("k must have eight bars of history")
    ret = float(log_close[k] - log_close[k - 8])
    high8 = high[k - 7 : k + 1]
    low8 = low[k - 7 : k + 1]
    range8 = float(math.log(float(np.max(high8)) / float(np.min(low8))))
    returns = np.diff(log_close[k - 8 : k + 1])
    rv8 = float(np.std(returns))
    variation = float(np.sum(np.abs(returns)))
    efficiency = 0.0 if variation == 0.0 else abs(ret) / variation
    return {
        "abs_ret_8": abs(ret),
        "range_8": range8,
        "rv_8": rv8,
        "efficiency_8": float(efficiency),
    }


def _carrier_label(close: np.ndarray, k: int) -> str:
    start = k - wrapper.VIEW_BARS + 1
    if start < 0:
        raise ValueError("carrier requires full frozen 64-bar view")
    score = float(
        oracle.direction_score(
            close[start : k + 1],
            oracle.FROZEN_WEIGHTS,
        )
    )
    if score > oracle.TAU_DIR:
        return "DIR_UP"
    if score < -oracle.TAU_DIR:
        return "DIR_DOWN"
    return CARRIER_RANGE


def _state_process(
    bars: pd.DataFrame,
) -> tuple[dict[int, str], dict[int, str], dict[int, int], dict[int, int], int]:
    high = bars["high"].to_numpy(float)
    low = bars["low"].to_numpy(float)
    close = bars["close"].to_numpy(float)
    rows = wrapper.replay_wrapper(high, low, close)
    five_states = {int(row.known_from_index): str(row.label) for row in rows}
    if not five_states:
        raise ValueError("empty delayed state process")
    keys = sorted(five_states)
    if keys != list(range(keys[0], keys[-1] + 1)):
        raise AssertionError("delayed state process is not contiguous")

    carriers = {k: _carrier_label(close, k) for k in keys}

    carrier_ages: dict[int, int] = {}
    exact_ages: dict[int, int] = {}
    previous_carrier: str | None = None
    previous_exact: str | None = None
    carrier_age = 0
    exact_age = 0
    for k in keys:
        carrier = carriers[k]
        exact = five_states[k]
        if carrier == previous_carrier:
            carrier_age += 1
        else:
            previous_carrier = carrier
            carrier_age = 1
        if exact == previous_exact:
            exact_age += 1
        else:
            previous_exact = exact
            exact_age = 1
        carrier_ages[k] = carrier_age
        exact_ages[k] = exact_age

        if exact == "CURRENT_UP" and carrier != "DIR_UP":
            raise AssertionError("CURRENT_UP carrier identity mismatch")
        if exact == "CURRENT_DOWN" and carrier != "DIR_DOWN":
            raise AssertionError("CURRENT_DOWN carrier identity mismatch")

    return five_states, carriers, carrier_ages, exact_ages, len(rows)


def _future_outcomes(
    five_states: dict[int, str],
    carriers: dict[int, str],
    *,
    k: int,
    exact_state: str,
    carrier_state: str,
) -> dict[str, object]:
    future_exact = [five_states[k + j] for j in range(1, SECONDARY_HORIZON + 1)]
    future_carrier = [carriers[k + j] for j in range(1, SECONDARY_HORIZON + 1)]

    opposite_carrier = "DIR_DOWN" if carrier_state == "DIR_UP" else "DIR_UP"

    structural8 = int(any(x != carrier_state for x in future_carrier[:PRIMARY_HORIZON]))
    structural16 = int(any(x != carrier_state for x in future_carrier))
    exact8 = int(any(x != exact_state for x in future_exact[:PRIMARY_HORIZON]))
    exact16 = int(any(x != exact_state for x in future_exact))
    slap8 = int(opposite_carrier in future_carrier[:PRIMARY_HORIZON])

    first_structural_delay: int | None = None
    first_structural_state: str | None = None
    for j, future_state in enumerate(future_carrier, start=1):
        if future_state != carrier_state:
            first_structural_delay = j
            first_structural_state = future_state
            break

    first_exact_delay: int | None = None
    first_exact_state: str | None = None
    for j, future_state in enumerate(future_exact, start=1):
        if future_state != exact_state:
            first_exact_delay = j
            first_exact_state = future_state
            break

    technical_first = int(
        first_exact_state in {"LOW_AMPLITUDE_VETO", "FINER_SCALE_OUT_OF_BAND"}
    )
    return {
        "structural_exit_next8": structural8,
        "structural_exit_next16": structural16,
        "exact_label_exit_next8": exact8,
        "exact_label_exit_next16": exact16,
        "slap_next8": slap8,
        "first_structural_exit_delay": first_structural_delay,
        "first_structural_exit_state": first_structural_state,
        "first_exact_exit_delay": first_exact_delay,
        "first_exact_exit_state": first_exact_state,
        "technical_first_exit": technical_first,
    }

def build_ledger(bars: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    _require_bars(bars)
    high = bars["high"].to_numpy(float)
    low = bars["low"].to_numpy(float)
    close = bars["close"].to_numpy(float)
    log_close = np.log(close)
    five_states, carriers, carrier_ages, exact_ages, wrapper_rows = _state_process(bars)

    first_k = max(wrapper.FIRST_ELIGIBLE_K, 8)
    last_k = len(bars) - 1 - SECONDARY_HORIZON
    rows: list[dict[str, object]] = []

    for k in range(first_k, last_k + 1):
        exact_state = five_states.get(k)
        if exact_state not in DIRECTIONAL_STATES:
            continue
        carrier_state = carriers[k]
        expected_carrier = "DIR_UP" if exact_state == "CURRENT_UP" else "DIR_DOWN"
        if carrier_state != expected_carrier:
            raise AssertionError("eligible exact state/carrier mismatch")
        if any(
            k + j not in five_states or k + j not in carriers
            for j in range(1, SECONDARY_HORIZON + 1)
        ):
            raise AssertionError("missing future state within frozen horizon")

        outcomes = _future_outcomes(
            five_states,
            carriers,
            k=k,
            exact_state=exact_state,
            carrier_state=carrier_state,
        )
        features = _local_features(high, low, log_close, k)
        knowledge_day = pd.Timestamp(bars.iloc[k]["trading_day"])
        timestamp = pd.Timestamp(bars.iloc[k]["timestamp"])
        carrier_age = int(carrier_ages[k])
        exact_age = int(exact_ages[k])
        rows.append(
            {
                "known_index": int(k),
                "target_index": int(k - wrapper.DELAY_BARS),
                "timestamp": timestamp,
                "knowledge_day": knowledge_day.strftime("%Y-%m-%d"),
                "year": int(knowledge_day.year),
                "state": exact_state,
                "carrier_state": carrier_state,
                "state_age": carrier_age,
                "exact_label_age": exact_age,
                "age_bin": _age_bin(carrier_age),
                **outcomes,
                **features,
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError("no directional state rows")
    if not np.isfinite(out[list(FEATURES)].to_numpy(float)).all():
        raise ValueError("non-finite local feature")
    meta = {
        "wrapper_rows": int(wrapper_rows),
        "first_eligible_k": int(first_k),
        "last_eligible_k": int(last_k),
        "directional_rows": int(len(out)),
    }
    return out, meta

def _reverse_percentiles(
    train_values: Sequence[float],
    test_values: Sequence[float],
) -> np.ndarray:
    calibration = np.sort(np.asarray(train_values, dtype=float))
    values = np.asarray(test_values, dtype=float)
    if not len(calibration):
        raise ValueError("empty calibration")
    if not np.isfinite(calibration).all() or not np.isfinite(values).all():
        raise ValueError("finite calibration/test values required")
    left = np.searchsorted(calibration, values, side="left")
    return (len(calibration) - left) / len(calibration)


def _score_with_training(
    train: pd.DataFrame,
    test: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    out = test.copy()
    train_scores = np.zeros(len(train), dtype=float)
    test_scores = np.zeros(len(test), dtype=float)

    for feature in FEATURES:
        train_component = _reverse_percentiles(train[feature], train[feature])
        test_component = _reverse_percentiles(train[feature], test[feature])
        train_scores += train_component / len(FEATURES)
        test_scores += test_component / len(FEATURES)
        out[f"risk_{feature}"] = test_component

    cuts = np.quantile(train_scores, [0.2, 0.4, 0.6, 0.8])
    out["compression_score"] = test_scores
    out["risk_band"] = np.searchsorted(cuts, test_scores, side="right") + 1
    return out, {
        "train_n": int(len(train)),
        "test_n": int(len(test)),
        "score_cutpoints": [float(x) for x in cuts],
    }


def walk_forward(ledger: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    scored: list[pd.DataFrame] = []
    folds: list[dict[str, object]] = []
    for year in TEST_YEARS:
        train = ledger[ledger["year"] < year].copy()
        test = ledger[ledger["year"] == year].copy()
        if len(train) < 10_000 or len(test) < 5_000:
            raise ValueError(f"insufficient fold support for {year}")
        result, meta = _score_with_training(train, test)
        scored.append(result)
        folds.append({"year": int(year), **meta})
    out = pd.concat(scored, ignore_index=True)
    if sorted(out["year"].unique().tolist()) != list(TEST_YEARS):
        raise AssertionError("unexpected scored years")
    return out, folds


def _band_table(df: pd.DataFrame, target: str = "structural_exit_next8") -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for band in range(1, 6):
        part = df[df["risk_band"] == band]
        rows.append(
            {
                "band": int(band),
                "n": int(len(part)),
                "events": int(part[target].sum()),
                "event_rate": float(part[target].mean()) if len(part) else math.nan,
                "score_median": (
                    float(part["compression_score"].median()) if len(part) else math.nan
                ),
            }
        )
    return rows


def _ranking_metrics(df: pd.DataFrame) -> dict[str, object]:
    table = _band_table(df, "structural_exit_next8")
    rates = np.asarray([row["event_rate"] for row in table], dtype=float)
    if not np.isfinite(rates).all():
        raise ValueError("all five risk bands require support")
    b1 = float(rates[0])
    b5 = float(rates[4])
    auc = float(roc_auc_score(df["structural_exit_next8"], df["compression_score"]))
    rho = float(spearmanr(np.arange(1, 6), rates).statistic)
    return {
        "n": int(len(df)),
        "events": int(df["structural_exit_next8"].sum()),
        "base_rate": float(df["structural_exit_next8"].mean()),
        "bands": table,
        "B5_minus_B1": float(b5 - b1),
        "B5_over_B1": float(b5 / b1) if b1 > 0 else math.inf,
        "band_rate_spearman": rho,
        "auc": auc,
        "exit16_B5_minus_B1": float(
            df[df["risk_band"] == 5]["structural_exit_next16"].mean()
            - df[df["risk_band"] == 1]["structural_exit_next16"].mean()
        ),
    }


def age_standardized_diff(
    df: pd.DataFrame,
    *,
    target: str = "structural_exit_next8",
) -> dict[str, object]:
    primary = df[df["risk_band"].isin([1, 5])].copy()
    strata: list[dict[str, object]] = []
    total = int(len(primary))
    if total <= 0:
        raise ValueError("no B1/B5 rows")
    effect = 0.0
    supported = True
    for state in DIRECTIONAL_STATES:
        for age_bin in AGE_BINS:
            part = primary[
                (primary["state"] == state) & (primary["age_bin"] == age_bin)
            ]
            b1 = part[part["risk_band"] == 1]
            b5 = part[part["risk_band"] == 5]
            combined = int(len(part))
            ok = (
                combined >= MIN_AGE_STRATUM_COMBINED
                and len(b1) > 0
                and len(b5) > 0
            )
            supported = supported and ok
            diff = (
                float(b5[target].mean() - b1[target].mean())
                if len(b1) and len(b5)
                else math.nan
            )
            weight = float(combined / total)
            if math.isfinite(diff):
                effect += weight * diff
            strata.append(
                {
                    "state": state,
                    "age_bin": age_bin,
                    "combined_n": combined,
                    "B1_n": int(len(b1)),
                    "B5_n": int(len(b5)),
                    "B1_rate": float(b1[target].mean()) if len(b1) else math.nan,
                    "B5_rate": float(b5[target].mean()) if len(b5) else math.nan,
                    "risk_diff": diff,
                    "weight": weight,
                    "support_ok": bool(ok),
                }
            )
    return {
        "supported": bool(supported),
        "risk_diff": float(effect) if supported else math.nan,
        "strata": strata,
    }


def overlap_phase_table(df: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for phase in range(8):
        part = df[df["known_index"] % 8 == phase]
        b1 = part[part["risk_band"] == 1]
        b5 = part[part["risk_band"] == 5]
        rows.append(
            {
                "phase": int(phase),
                "n": int(len(part)),
                "B1_n": int(len(b1)),
                "B5_n": int(len(b5)),
                "B1_rate": float(b1["structural_exit_next8"].mean()),
                "B5_rate": float(b5["structural_exit_next8"].mean()),
                "risk_diff": float(
                    b5["structural_exit_next8"].mean() - b1["structural_exit_next8"].mean()
                ),
            }
        )
    return rows


def _attach_blocks(scored: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    unique_days = list(dict.fromkeys(str(x) for x in bars["trading_day"].tolist()))
    order = {day: i for i, day in enumerate(unique_days)}
    out = scored.copy()
    out["block_id"] = [
        int(order[str(day)] // BLOCK_DAYS)
        for day in out["knowledge_day"].tolist()
    ]
    return out


def _bootstrap_arrays(scored: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[int]]:
    primary = scored[scored["risk_band"].isin([1, 5])].copy()
    blocks = sorted(int(x) for x in primary["block_id"].unique())
    block_pos = {block: i for i, block in enumerate(blocks)}
    state_pos = {state: i for i, state in enumerate(DIRECTIONAL_STATES)}
    age_pos = {age: i for i, age in enumerate(AGE_BINS)}
    band_pos = {1: 0, 5: 1}

    shape = (len(blocks), len(DIRECTIONAL_STATES), len(AGE_BINS), 2)
    counts = np.zeros(shape, dtype=float)
    exits8 = np.zeros(shape, dtype=float)
    exits16 = np.zeros(shape, dtype=float)

    grouped = primary.groupby(
        ["block_id", "state", "age_bin", "risk_band"], sort=False
    )
    for (block, state, age_bin, band), part in grouped:
        idx = (
            block_pos[int(block)],
            state_pos[str(state)],
            age_pos[str(age_bin)],
            band_pos[int(band)],
        )
        counts[idx] = float(len(part))
        exits8[idx] = float(part["structural_exit_next8"].sum())
        exits16[idx] = float(part["structural_exit_next16"].sum())
    return counts, exits8, exits16, blocks


def bootstrap(scored: pd.DataFrame, bars: pd.DataFrame) -> dict[str, object]:
    with_blocks = _attach_blocks(scored, bars)
    counts, exits8, exits16, blocks = _bootstrap_arrays(with_blocks)
    rng = np.random.default_rng(BOOT_SEED)
    n_blocks = len(blocks)

    pooled_diff: list[float] = []
    pooled_ratio: list[float] = []
    up_diff: list[float] = []
    down_diff: list[float] = []
    age_diff: list[float] = []
    exit16_diff: list[float] = []

    for _ in range(BOOT_REPS):
        draw = rng.integers(0, n_blocks, size=n_blocks)
        c = counts[draw].sum(axis=0)
        e8 = exits8[draw].sum(axis=0)
        e16 = exits16[draw].sum(axis=0)

        d1 = float(c[:, :, 0].sum())
        d5 = float(c[:, :, 1].sum())
        if d1 > 0 and d5 > 0:
            r1 = float(e8[:, :, 0].sum() / d1)
            r5 = float(e8[:, :, 1].sum() / d5)
            pooled_diff.append(r5 - r1)
            if r1 > 0:
                pooled_ratio.append(r5 / r1)
            r1_16 = float(e16[:, :, 0].sum() / d1)
            r5_16 = float(e16[:, :, 1].sum() / d5)
            exit16_diff.append(r5_16 - r1_16)

        for state_index, destination in ((0, up_diff), (1, down_diff)):
            sd1 = float(c[state_index, :, 0].sum())
            sd5 = float(c[state_index, :, 1].sum())
            if sd1 > 0 and sd5 > 0:
                destination.append(
                    float(e8[state_index, :, 1].sum() / sd5)
                    - float(e8[state_index, :, 0].sum() / sd1)
                )

        valid_age = True
        total = float(c.sum())
        standardized = 0.0
        if total <= 0:
            valid_age = False
        else:
            for si in range(len(DIRECTIONAL_STATES)):
                for ai in range(len(AGE_BINS)):
                    s1 = float(c[si, ai, 0])
                    s5 = float(c[si, ai, 1])
                    if s1 <= 0 or s5 <= 0:
                        valid_age = False
                        break
                    weight = (s1 + s5) / total
                    standardized += weight * (
                        float(e8[si, ai, 1] / s5)
                        - float(e8[si, ai, 0] / s1)
                    )
                if not valid_age:
                    break
        if valid_age:
            age_diff.append(float(standardized))

    def summarize(values: list[float]) -> dict[str, object]:
        if not values:
            return {"n_draws": 0, "median": math.nan, "ci95": [math.nan, math.nan]}
        arr = np.asarray(values, dtype=float)
        return {
            "n_draws": int(len(arr)),
            "median": float(np.median(arr)),
            "ci95": [float(x) for x in np.quantile(arr, [0.025, 0.975])],
        }

    return {
        "blocks": int(n_blocks),
        "block_trading_days": int(BLOCK_DAYS),
        "repetitions": int(BOOT_REPS),
        "seed": int(BOOT_SEED),
        "pooled_risk_diff": summarize(pooled_diff),
        "pooled_risk_ratio": summarize(pooled_ratio),
        "CURRENT_UP_risk_diff": summarize(up_diff),
        "CURRENT_DOWN_risk_diff": summarize(down_diff),
        "age_standardized_risk_diff": summarize(age_diff),
        "exit16_pooled_risk_diff": summarize(exit16_diff),
    }


def support_gate(
    scored: pd.DataFrame,
    age_adjusted: dict[str, object],
    boot: dict[str, object],
) -> dict[str, object]:
    cells: list[dict[str, object]] = []
    state_band_ok = True
    for state in DIRECTIONAL_STATES:
        for band in (1, 5):
            n = int(
                len(scored[(scored["state"] == state) & (scored["risk_band"] == band)])
            )
            ok = n >= MIN_STATE_BAND
            state_band_ok = state_band_ok and ok
            cells.append({"state": state, "band": band, "n": n, "passed": bool(ok)})

    boot_keys = (
        "pooled_risk_diff",
        "pooled_risk_ratio",
        "CURRENT_UP_risk_diff",
        "CURRENT_DOWN_risk_diff",
        "age_standardized_risk_diff",
        "exit16_pooled_risk_diff",
    )
    boot_ok = all(int(boot[key]["n_draws"]) >= MIN_VALID_BOOT for key in boot_keys)
    checks = {
        "total_scored_ge_20000": bool(len(scored) >= MIN_TOTAL_SCORED),
        "state_B1_B5_cells_ge_1000": bool(state_band_ok),
        "age_strata_supported": bool(age_adjusted["supported"]),
        "bootstrap_valid_draws_ge_95pct": bool(boot_ok),
    }
    return {
        "passed": bool(all(checks.values())),
        "checks": checks,
        "state_band_cells": cells,
    }


def adjudicate(
    pooled: dict[str, object],
    yearly: list[dict[str, object]],
    by_state: dict[str, dict[str, object]],
    age_adjusted: dict[str, object],
    phases: list[dict[str, object]],
    boot: dict[str, object],
    support: dict[str, object],
) -> dict[str, object]:
    years_b5_gt_b1 = sum(
        float(row["B5_minus_B1"]) > 0 for row in yearly
    )
    positive_phases = sum(float(row["risk_diff"]) > 0 for row in phases)

    up = by_state["CURRENT_UP"]
    down = by_state["CURRENT_DOWN"]

    checks = {
        "pooled_B5_gt_B1": bool(float(pooled["B5_minus_B1"]) > 0),
        "pooled_diff_ge_5pp": bool(float(pooled["B5_minus_B1"]) >= 0.05),
        "pooled_diff_ci_lower_gt0": bool(
            float(boot["pooled_risk_diff"]["ci95"][0]) > 0
        ),
        "pooled_ratio_ci_lower_gt1": bool(
            float(boot["pooled_risk_ratio"]["ci95"][0]) > 1
        ),
        "pooled_spearman_ge_0p70": bool(
            float(pooled["band_rate_spearman"]) >= 0.70
        ),
        "pooled_auc_ge_0p55": bool(float(pooled["auc"]) >= 0.55),
        "years_B5_gt_B1_eq3": bool(years_b5_gt_b1 == 3),
        "CURRENT_UP_diff_ge_3pp": bool(float(up["B5_minus_B1"]) >= 0.03),
        "CURRENT_UP_diff_ci_lower_gt0": bool(
            float(boot["CURRENT_UP_risk_diff"]["ci95"][0]) > 0
        ),
        "CURRENT_DOWN_diff_ge_3pp": bool(float(down["B5_minus_B1"]) >= 0.03),
        "CURRENT_DOWN_diff_ci_lower_gt0": bool(
            float(boot["CURRENT_DOWN_risk_diff"]["ci95"][0]) > 0
        ),
        "age_standardized_diff_ge_3pp": bool(
            bool(age_adjusted["supported"])
            and float(age_adjusted["risk_diff"]) >= 0.03
        ),
        "age_standardized_ci_lower_gt0": bool(
            float(boot["age_standardized_risk_diff"]["ci95"][0]) > 0
        ),
        "positive_overlap_phases_ge6": bool(positive_phases >= 6),
        "exit16_diff_ci_lower_gt0": bool(
            float(boot["exit16_pooled_risk_diff"]["ci95"][0]) > 0
        ),
    }
    passed = bool(support["passed"] and all(checks.values()))
    return {
        "verdict": (
            "LOCAL_COMPRESSION_STATE_EXIT_HAZARD_SUPPORTED"
            if passed
            else "LOCAL_COMPRESSION_STATE_EXIT_HAZARD_NOT_SUPPORTED"
        ),
        "years_B5_gt_B1": int(years_b5_gt_b1),
        "positive_overlap_phases": int(positive_phases),
        "checks": checks,
    }


def analyze(bars: pd.DataFrame) -> dict[str, object]:
    ledger, meta = build_ledger(bars)
    scored, folds = walk_forward(ledger)

    pooled = _ranking_metrics(scored)
    yearly = [
        {"year": int(year), **_ranking_metrics(part)}
        for year, part in scored.groupby("year", sort=True)
    ]
    by_state = {
        state: _ranking_metrics(scored[scored["state"] == state])
        for state in DIRECTIONAL_STATES
    }
    age_adjusted = age_standardized_diff(scored)
    phases = overlap_phase_table(scored)
    boot = bootstrap(scored, bars)
    support = support_gate(scored, age_adjusted, boot)
    decision = adjudicate(
        pooled,
        yearly,
        by_state,
        age_adjusted,
        phases,
        boot,
        support,
    )

    return {
        "status": "LOCAL_STATE_EXIT_COMPRESSION_COMPLETE",
        "meta": {
            **meta,
            "scored_test_rows": int(len(scored)),
            "scored_years": [int(x) for x in TEST_YEARS],
        },
        "folds": folds,
        "pooled": pooled,
        "yearly": yearly,
        "by_state": by_state,
        "age_standardized": age_adjusted,
        "overlap_phases": phases,
        "bootstrap": boot,
        "support": support,
        "decision": decision,
        "ledger": ledger,
        "scored": scored,
        "authority": {
            "signal": False,
            "router": False,
            "trade": False,
            "paper_trading": False,
            "live_trading": False,
            "production": False,
        },
    }
