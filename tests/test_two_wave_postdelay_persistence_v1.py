import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))

import two_wave_postdelay_persistence_v1 as p


def test_parent_phase_monotone_and_flat():
    up = np.exp(np.linspace(0.0, 0.3, 128))
    down = up[::-1]
    flat = np.full(128, 100.0)
    assert p.parent_phase(up)[0] == "PARENT_UP"
    assert p.parent_phase(down)[0] == "PARENT_DOWN"
    assert p.parent_phase(flat)[0] == "PARENT_RANGE"


def test_directional_relation_mapping():
    assert p.directional_relation("CURRENT_UP", "PARENT_UP") == "ALIGNED"
    assert p.directional_relation("CURRENT_UP", "PARENT_RANGE") == "NEUTRAL"
    assert p.directional_relation("CURRENT_UP", "PARENT_DOWN") == "OPPOSED"
    assert p.directional_relation("CURRENT_DOWN", "PARENT_DOWN") == "ALIGNED"
    assert p.directional_relation("CURRENT_DOWN", "PARENT_UP") == "OPPOSED"
    assert p.directional_relation("CURRENT_RANGE", "PARENT_UP") is None


def test_outcomes_start_at_k_plus_one_and_face_slap_is_cumulative():
    k = 100
    states = {i: "CURRENT_UP" for i in range(k - 10, k + 40)}
    # Information before and at k must not affect future outcome logic.
    states[k - 8] = "CURRENT_DOWN"
    states[k - 1] = "CURRENT_DOWN"
    states[k] = "CURRENT_UP"
    # Soft decay first, then a later opposite state.
    states[k + 3] = "CURRENT_RANGE"
    states[k + 7] = "CURRENT_DOWN"

    out = p.delayed_state_outcomes(
        states, known_index=k, state="CURRENT_UP"
    )
    assert out["first_change_delay"] == 3
    assert out["first_exit_state"] == "CURRENT_RANGE"
    assert out["first_slap_delay"] == 7
    assert out["survive_2"] == 1
    assert out["survive_4"] == 0
    assert out["slap_4"] == 0
    assert out["slap_8"] == 1
def _synthetic_directional_events():
    rows = []
    rng = np.random.default_rng(7)
    for day in range(60):
        day_name = f"2020-01-{day % 28 + 1:02d}-{day:02d}"
        for relation, survive_prob, slap_prob in (
            ("ALIGNED", 0.75, 0.08),
            ("OPPOSED", 0.55, 0.18),
        ):
            for _ in range(10):
                rows.append(
                    {
                        "knowledge_day": day_name,
                        "state": "CURRENT_UP",
                        "relation_128": relation,
                        "relation_256": relation,
                        "survive_8": int(rng.random() < survive_prob),
                        "survive_16": int(rng.random() < survive_prob - 0.08),
                        "slap_8": int(rng.random() < slap_prob),
                        "slap_16": int(rng.random() < slap_prob + 0.05),
                        "end_same_dir_8": int(rng.random() < survive_prob + 0.05),
                        "end_same_dir_16": int(rng.random() < survive_prob),
                    }
                )
    return pd.DataFrame(rows)


def test_cluster_bootstrap_is_deterministic():
    events = _synthetic_directional_events()
    a = p.cluster_bootstrap_effect(
        events,
        period=128,
        horizon=8,
        metric="survive",
        replicates=200,
        seed=123,
    )
    b = p.cluster_bootstrap_effect(
        events,
        period=128,
        horizon=8,
        metric="survive",
        replicates=200,
        seed=123,
    )
    assert a == b
    assert a["effect"] > 0
    assert a["aligned_support"] == 600
    assert a["opposed_support"] == 600
def test_consensus_mapping():
    assert p.consensus_phase("PARENT_UP", "PARENT_UP") == "CONSENSUS_UP"
    assert p.consensus_phase("PARENT_UP", "PARENT_DOWN") == "MIXED"
    assert (
        p.consensus_relation("CURRENT_UP", "ALIGNED", "ALIGNED")
        == "CONSENSUS_ALIGNED"
    )
    assert (
        p.consensus_relation("CURRENT_DOWN", "OPPOSED", "OPPOSED")
        == "CONSENSUS_OPPOSED"
    )


def test_supported_conditioner_gate_logic():
    rows = []
    for period in (128, 256):
        for h, surv, slap in ((8, 0.08, -0.05), (16, 0.05, -0.03)):
            rows.append(
                {
                    "period": period,
                    "horizon": h,
                    "metric": "survive",
                    "effect": surv,
                    "ci_low": surv - 0.02,
                    "ci_high": surv + 0.02,
                    "aligned_support": 2000,
                    "opposed_support": 1800,
                }
            )
            rows.append(
                {
                    "period": period,
                    "horizon": h,
                    "metric": "slap",
                    "effect": slap,
                    "ci_low": slap - 0.01,
                    "ci_high": slap + 0.01,
                    "aligned_support": 2000,
                    "opposed_support": 1800,
                }
            )
    bootstrap = pd.DataFrame(rows)

    years = []
    for period in (128, 256):
        for year in range(2015, 2021):
            for h in (8, 16):
                years.append(
                    {
                        "period": period,
                        "year": year,
                        "horizon": h,
                        "metric": "survive",
                        "effect": 0.06,
                    }
                )
                years.append(
                    {
                        "period": period,
                        "year": year,
                        "horizon": h,
                        "metric": "slap",
                        "effect": -0.04,
                    }
                )
    yearly = pd.DataFrame(years)

    detail, verdicts = p.conditioner_verdicts(bootstrap, yearly)
    assert verdicts[128] == "SUPPORTED_PERSISTENCE_CONDITIONER"
    assert verdicts[256] == "SUPPORTED_PERSISTENCE_CONDITIONER"
    assert detail["passed"].all()
