from __future__ import annotations

import math
from typing import Any

SCHEMA_ID = "risk_tool_v2_probability_reliability_consumer_payload@1.0"
Q33 = 0.5170330932673238
Q67 = 0.7096666848299501
TEMPORAL_V3_RUN = "34930354449-1"
RELIABILITY_RUN = "34942554638-1"
OUTPUT_CONTRACT_RUN = "34945466654-1"

CAPABILITIES = (
    "ranking",
    "probability_context",
    "probability_research",
    "hard_probability_threshold",
    "strategy_routing",
    "position_sizing",
    "pnl_authority",
    "production_authority",
)

_FORBIDDEN = {
    "hard_probability_threshold": False,
    "strategy_routing": False,
    "position_sizing": False,
    "pnl_authority": False,
    "production_authority": False,
}

_15M_BAND_PERMISSIONS = {
    "UNSCORED": {"ranking": True, "probability_context": False, "probability_research": False},
    "LOW": {"ranking": True, "probability_context": False, "probability_research": False},
    "MID": {"ranking": True, "probability_context": True, "probability_research": False},
    "HIGH": {"ranking": True, "probability_context": True, "probability_research": True},
}


class ConsumerContractError(ValueError):
    pass


def _bounded_number(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConsumerContractError(f"{name}_not_number")
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ConsumerContractError(f"{name}_out_of_range")
    return value


def derive_band(horizon_minutes: int, reliability_score: Any) -> str:
    if horizon_minutes == 30:
        if reliability_score is not None:
            raise ConsumerContractError("30m_reliability_overlay_not_allowed")
        return "NOT_REQUIRED"
    if horizon_minutes != 15:
        raise ConsumerContractError("unsupported_horizon")
    if reliability_score is None:
        return "UNSCORED"
    score = _bounded_number("reliability_score", reliability_score)
    if score < Q33:
        return "LOW"
    if score < Q67:
        return "MID"
    return "HIGH"


def permissions_for(horizon_minutes: int, band: str) -> dict[str, bool]:
    if horizon_minutes == 30:
        if band != "NOT_REQUIRED":
            raise ConsumerContractError("30m_band_must_be_not_required")
        base = {"ranking": True, "probability_context": True, "probability_research": True}
    elif horizon_minutes == 15:
        if band not in _15M_BAND_PERMISSIONS:
            raise ConsumerContractError("invalid_15m_reliability_band")
        base = dict(_15M_BAND_PERMISSIONS[band])
    else:
        raise ConsumerContractError("unsupported_horizon")
    return {**base, **_FORBIDDEN}


def _authority_for(horizon_minutes: int) -> dict[str, Any]:
    return {
        "temporal_v3_run": TEMPORAL_V3_RUN,
        "reliability_run": RELIABILITY_RUN if horizon_minutes == 15 else None,
        "output_contract_run": OUTPUT_CONTRACT_RUN,
        "year_2026_read": False,
        "production_authority": False,
    }


def build_payload(
    *,
    horizon_minutes: int,
    ordering_score: Any,
    recovery_probability: Any,
    reliability_score: Any = None,
) -> dict[str, Any]:
    ordering = _bounded_number("ordering_score", ordering_score)
    probability = _bounded_number("recovery_probability", recovery_probability)
    band = derive_band(horizon_minutes, reliability_score)
    payload = {
        "schema_id": SCHEMA_ID,
        "horizon_minutes": horizon_minutes,
        "ordering_score": ordering,
        "recovery_probability": probability,
        "reliability_score": None if reliability_score is None else float(reliability_score),
        "reliability_band": band,
        "permissions": permissions_for(horizon_minutes, band),
        "authority": _authority_for(horizon_minutes),
    }
    return validate_payload(payload)


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ConsumerContractError("payload_not_object")
    required = {
        "schema_id",
        "horizon_minutes",
        "ordering_score",
        "recovery_probability",
        "reliability_score",
        "reliability_band",
        "permissions",
        "authority",
    }
    if set(payload) != required:
        raise ConsumerContractError("payload_shape_invalid")
    if payload["schema_id"] != SCHEMA_ID:
        raise ConsumerContractError("schema_id_invalid")
    horizon = payload["horizon_minutes"]
    if horizon not in (15, 30):
        raise ConsumerContractError("unsupported_horizon")
    _bounded_number("ordering_score", payload["ordering_score"])
    _bounded_number("recovery_probability", payload["recovery_probability"])
    expected_band = derive_band(horizon, payload["reliability_score"])
    if payload["reliability_band"] != expected_band:
        raise ConsumerContractError("reliability_band_forged_or_stale")
    expected_permissions = permissions_for(horizon, expected_band)
    if payload["permissions"] != expected_permissions:
        raise ConsumerContractError("permission_matrix_tampered")
    if payload["authority"] != _authority_for(horizon):
        raise ConsumerContractError("authority_identity_invalid")
    return payload


def consume(payload: Any, capability: str) -> dict[str, Any]:
    valid = validate_payload(payload)
    if capability not in CAPABILITIES:
        raise ConsumerContractError("unknown_capability")
    if not valid["permissions"][capability]:
        raise ConsumerContractError("capability_not_authorized")
    base = {
        "schema_id": "risk_tool_v2_probability_reliability_consumer_view@1.0",
        "horizon_minutes": valid["horizon_minutes"],
        "capability": capability,
        "reliability_band": valid["reliability_band"],
    }
    if capability == "ranking":
        return {**base, "ordering_score": valid["ordering_score"]}
    if capability == "probability_context":
        return {
            **base,
            "recovery_probability": valid["recovery_probability"],
            "reliability_score": valid["reliability_score"],
            "interpretation": "guarded_context_only" if valid["reliability_band"] == "MID" else "allowed_with_reliability_label",
        }
    if capability == "probability_research":
        return {
            **base,
            "recovery_probability": valid["recovery_probability"],
            "reliability_score": valid["reliability_score"],
            "interpretation": "research_probability_allowed",
        }
    raise ConsumerContractError("capability_not_authorized")
