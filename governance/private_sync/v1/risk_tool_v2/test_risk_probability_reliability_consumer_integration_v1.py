from __future__ import annotations

import pytest

from factor_lab.market_state.risk_probability_reliability_consumer_v1 import (
    ConsumerContractError,
    build_payload,
    consume,
)


def test_layer3_consumer_import_and_capability_boundary() -> None:
    high = build_payload(
        horizon_minutes=15,
        ordering_score=0.73,
        recovery_probability=0.61,
        reliability_score=0.80,
    )
    ranking = consume(high, "ranking")
    probability = consume(high, "probability_research")
    assert ranking == {
        "schema_id": "risk_tool_v2_probability_reliability_consumer_view@1.0",
        "horizon_minutes": 15,
        "capability": "ranking",
        "reliability_band": "HIGH",
        "ordering_score": 0.73,
    }
    assert probability["recovery_probability"] == 0.61
    assert probability["reliability_score"] == 0.80
    assert probability["interpretation"] == "research_probability_allowed"

    low = build_payload(
        horizon_minutes=15,
        ordering_score=0.42,
        recovery_probability=0.35,
        reliability_score=0.40,
    )
    assert consume(low, "ranking")["ordering_score"] == 0.42
    with pytest.raises(ConsumerContractError, match="capability_not_authorized"):
        consume(low, "probability_context")

    thirty = build_payload(
        horizon_minutes=30,
        ordering_score=0.64,
        recovery_probability=0.58,
        reliability_score=None,
    )
    assert consume(thirty, "probability_research")["recovery_probability"] == 0.58
    with pytest.raises(ConsumerContractError, match="capability_not_authorized"):
        consume(thirty, "strategy_routing")
