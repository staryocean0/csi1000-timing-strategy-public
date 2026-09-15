from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "docs/acceptance/risk_tool_v2/risk_tool_consumer_contract_v1.json"
SCHEMA_ID = "risk_tool_v2_output_envelope@1.0"
TOOL_ID = "risk-tool-v2-severity-persistence"
OUTPUT_CONTRACT_RUN = "34945466654-1"


class ConsumerContractError(RuntimeError):
    pass


def load_contract(path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_id") != "risk_tool_v2_consumer_contract@1.0":
        raise ConsumerContractError("consumer_contract_identity_drift")
    if value.get("status") != "frozen_before_consumer_adjudication":
        raise ConsumerContractError("consumer_contract_not_frozen")
    return value


def _finite(value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ConsumerContractError("non_finite_output")
    return value


def reliability_band(score: float | None, contract: dict[str, Any]) -> str:
    if score is None:
        return "UNSCORED"
    score = _finite(score)
    if score < 0.0 or score > 1.0:
        raise ConsumerContractError("reliability_out_of_range")
    thresholds = contract["15m"]["band_thresholds"]
    if score < float(thresholds["low_upper_exclusive"]):
        return "LOW"
    if score < float(thresholds["high_lower_inclusive"]):
        return "MID"
    return "HIGH"


def _capabilities_for(horizon_minutes: int, band: str, contract: dict[str, Any]) -> list[str]:
    if horizon_minutes == 15:
        permissions = contract["15m"]["permissions"]
        if band not in permissions:
            raise ConsumerContractError("unknown_reliability_band")
        return list(permissions[band])
    if horizon_minutes == 30:
        if band != "NOT_REQUIRED":
            raise ConsumerContractError("30m_reliability_overlay_forbidden")
        return list(contract["30m"]["permissions"])
    raise ConsumerContractError("unknown_horizon")


def _surface_for(horizon_minutes: int, band: str) -> str:
    if horizon_minutes == 30:
        return "research_probability"
    if band in {"UNSCORED", "LOW"}:
        return "diagnostic_only"
    if band == "MID":
        return "guarded_research"
    if band == "HIGH":
        return "research_probability"
    raise ConsumerContractError("unknown_reliability_band")


def build_envelope(
    horizon_minutes: int,
    ordering_value: float,
    probability_value: float,
    reliability_score: float | None = None,
    contract_path: Path = DEFAULT_CONTRACT,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    ordering_value = _finite(ordering_value)
    probability_value = _finite(probability_value)
    if probability_value < 0.0 or probability_value > 1.0:
        raise ConsumerContractError("probability_out_of_range")

    if horizon_minutes == 15:
        band = reliability_band(reliability_score, contract)
        score = None if reliability_score is None else _finite(reliability_score)
    elif horizon_minutes == 30:
        if reliability_score is not None:
            raise ConsumerContractError("30m_reliability_overlay_forbidden")
        band = "NOT_REQUIRED"
        score = None
    else:
        raise ConsumerContractError("unknown_horizon")

    allowed = _capabilities_for(horizon_minutes, band, contract)
    return {
        "schema_id": SCHEMA_ID,
        "tool_id": TOOL_ID,
        "horizon_minutes": horizon_minutes,
        "ordering": {"value": ordering_value, "authorized": True},
        "probability": {
            "value": probability_value,
            "surface": _surface_for(horizon_minutes, band),
        },
        "reliability": {"score": score, "band": band},
        "allowed_capabilities": allowed,
        "authority": {
            "output_contract_run": OUTPUT_CONTRACT_RUN,
            "production_authority": False,
            "year_2026_read": False,
        },
    }


def validate_envelope(envelope: dict[str, Any], contract_path: Path = DEFAULT_CONTRACT) -> None:
    contract = load_contract(contract_path)
    if set(envelope) != {
        "schema_id",
        "tool_id",
        "horizon_minutes",
        "ordering",
        "probability",
        "reliability",
        "allowed_capabilities",
        "authority",
    }:
        raise ConsumerContractError("envelope_shape_drift")
    if envelope["schema_id"] != SCHEMA_ID or envelope["tool_id"] != TOOL_ID:
        raise ConsumerContractError("envelope_identity_drift")

    horizon = int(envelope["horizon_minutes"])
    ordering = envelope["ordering"]
    probability = envelope["probability"]
    reliability = envelope["reliability"]
    authority = envelope["authority"]
    if set(ordering) != {"value", "authorized"} or ordering["authorized"] is not True:
        raise ConsumerContractError("ordering_surface_invalid")
    _finite(ordering["value"])
    if set(probability) != {"value", "surface"}:
        raise ConsumerContractError("probability_surface_invalid")
    p = _finite(probability["value"])
    if p < 0.0 or p > 1.0:
        raise ConsumerContractError("probability_out_of_range")
    if set(reliability) != {"score", "band"}:
        raise ConsumerContractError("reliability_surface_invalid")

    if horizon == 15:
        expected_band = reliability_band(reliability["score"], contract)
    elif horizon == 30:
        if reliability["score"] is not None:
            raise ConsumerContractError("30m_reliability_overlay_forbidden")
        expected_band = "NOT_REQUIRED"
    else:
        raise ConsumerContractError("unknown_horizon")
    if reliability["band"] != expected_band:
        raise ConsumerContractError("reliability_band_mismatch")

    expected_caps = _capabilities_for(horizon, expected_band, contract)
    if envelope["allowed_capabilities"] != expected_caps:
        raise ConsumerContractError("capability_surface_drift")
    if probability["surface"] != _surface_for(horizon, expected_band):
        raise ConsumerContractError("probability_surface_drift")
    forbidden = set(contract["forbidden_capabilities"])
    if forbidden.intersection(expected_caps):
        raise ConsumerContractError("forbidden_capability_leak")
    if authority != {
        "output_contract_run": OUTPUT_CONTRACT_RUN,
        "production_authority": False,
        "year_2026_read": False,
    }:
        raise ConsumerContractError("authority_surface_drift")


def require_capability(
    envelope: dict[str, Any], capability: str, contract_path: Path = DEFAULT_CONTRACT
) -> None:
    validate_envelope(envelope, contract_path)
    contract = load_contract(contract_path)
    if capability in set(contract["forbidden_capabilities"]):
        raise ConsumerContractError("forbidden_capability_requested")
    if capability not in set(contract["capabilities"]):
        raise ConsumerContractError("unknown_capability_requested")
    if capability not in set(envelope["allowed_capabilities"]):
        raise ConsumerContractError("capability_not_authorized")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and validate one Risk Tool consumer envelope.")
    parser.add_argument("--horizon", type=int, required=True, choices=(15, 30))
    parser.add_argument("--ordering", type=float, required=True)
    parser.add_argument("--probability", type=float, required=True)
    parser.add_argument("--reliability", type=float)
    args = parser.parse_args()
    envelope = build_envelope(args.horizon, args.ordering, args.probability, args.reliability)
    validate_envelope(envelope)
    print(json.dumps(envelope, sort_keys=True))


if __name__ == "__main__":
    main()
