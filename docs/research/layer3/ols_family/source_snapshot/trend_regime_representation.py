"""M6 product representation for the Layer-2 trend-state component.

The formal product representation is three categorical direction states plus a
continuous strength dimension derived from the already-frozen M2 slope score.
This module is a semantic representation primitive only; it is not the M7
consumer, does not publish snapshots, and has no trading-action authority.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Final

from factor_lab.market_state.trend_regime_baseline import (
    ESTIMATOR_ID,
    ESTIMATOR_VERSION,
    SCHEMA_ID as BASELINE_SCHEMA_ID,
    STATE_DOWN,
    STATE_SIDEWAYS,
    STATE_UP,
    classify_slope_t,
)

REPRESENTATION_SCHEMA_ID: Final[str] = (
    "trend_regime_three_bucket_plus_continuous_strength@1.0"
)
STATE_SCHEME_ID: Final[str] = "trend_regime_three_bucket@1.0"
STRENGTH_DEFINITION_ID: Final[str] = "absolute_log_close_ols_slope_t@1.0"
DIRECTIONAL_SCORE_FIELD: Final[str] = "slope_t"


@dataclass(frozen=True, slots=True)
class TrendRegimeRepresentation:
    """Formal M6 state representation, separate from snapshot lifecycle."""

    state: str
    directional_score: float
    strength: float
    representation_schema_id: str = REPRESENTATION_SCHEMA_ID
    state_scheme_id: str = STATE_SCHEME_ID
    strength_definition_id: str = STRENGTH_DEFINITION_ID
    baseline_schema_id: str = BASELINE_SCHEMA_ID
    estimator_id: str = ESTIMATOR_ID
    estimator_version: str = ESTIMATOR_VERSION
    measurement_authority: bool = True
    production_authority: bool = False
    trading_action_authority: bool = False

    def __post_init__(self) -> None:
        if self.state not in {STATE_DOWN, STATE_SIDEWAYS, STATE_UP}:
            raise ValueError("M6 formal state must be DOWN, SIDEWAYS, or UP")
        if not math.isfinite(self.directional_score):
            raise ValueError("directional_score must be finite")
        if not math.isfinite(self.strength) or self.strength < 0.0:
            raise ValueError("strength must be finite and non-negative")
        if not math.isclose(self.strength, abs(self.directional_score), rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("M6 strength must equal abs(directional_score)")
        if classify_slope_t(self.directional_score) != self.state:
            raise ValueError("state is inconsistent with frozen M2 T1 semantics")
        if self.production_authority or self.trading_action_authority:
            raise ValueError("M6 representation may not grant production/trading authority")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def represent_trend_state(*, state: str, slope_t: float) -> TrendRegimeRepresentation:
    """Wrap a frozen M2/M3 measurement in the formal M6 product representation.

    ``directional_score`` preserves the signed M2 ``slope_t`` exactly. ``strength``
    is its absolute magnitude. No T2 threshold or STRONG_* product state exists.
    """

    score = float(slope_t)
    if not math.isfinite(score):
        raise ValueError("slope_t must be finite")
    return TrendRegimeRepresentation(
        state=state,
        directional_score=score,
        strength=abs(score),
    )


__all__ = [
    "DIRECTIONAL_SCORE_FIELD",
    "REPRESENTATION_SCHEMA_ID",
    "STATE_SCHEME_ID",
    "STRENGTH_DEFINITION_ID",
    "TrendRegimeRepresentation",
    "represent_trend_state",
]
