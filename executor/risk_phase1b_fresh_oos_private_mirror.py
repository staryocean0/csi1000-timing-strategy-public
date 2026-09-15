"""Mirror the validated fresh-OOS aggregate summary to the private run branch."""

from __future__ import annotations

import base64
import json
import sys
import urllib.parse

import research_broker as rb

GateError = rb.GateError

SCHEMA_ID = "risk_tool_v2_phase1b_fresh_oos_result@2.0"
TASK_ID = "CSI1000-RISK-V2-2026-FRESH-OOS-V1-20260914"
PREREG_SHA256 = "c05bdf09c54626861f2a86abbcadb514fa90918320e2ab4be45e1e3217b7c9d7"
CARRIER_SHA256 = "211448c914b547232bc536da7df94dc5ae279b8265a5cafe58409238485217d7"
MODEL_FREEZE_SHA256 = "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551"
CALIBRATION_FREEZE_SHA256 = "74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909"


def validate_summary(value: object) -> dict:
    if not isinstance(value, dict):
        raise GateError("fresh_oos_summary_not_object")
    if value.get("schema_id") != SCHEMA_ID or value.get("task_id") != TASK_ID:
        raise GateError("fresh_oos_summary_schema_or_task_mismatch")
    if value.get("prereg_sha256") != PREREG_SHA256:
        raise GateError("fresh_oos_summary_prereg_mismatch")
    if value.get("carrier_identity_sha256") != CARRIER_SHA256:
        raise GateError("fresh_oos_summary_carrier_mismatch")
    if value.get("model_freeze_sha256") != MODEL_FREEZE_SHA256:
        raise GateError("fresh_oos_summary_model_mismatch")
    if value.get("calibration_freeze_sha256") != CALIBRATION_FREEZE_SHA256:
        raise GateError("fresh_oos_summary_calibration_mismatch")
    if value.get("year_2026_semantic_read") is not True:
        raise GateError("fresh_oos_summary_not_revealed")
    if value.get("overall_status") not in {
        "FRESH_OOS_SUPPORTED",
        "FRESH_OOS_NOT_SUPPORTED",
        "INSUFFICIENT_2026_SUPPORT",
        "MIXED_BY_HORIZON",
    }:
        raise GateError("fresh_oos_summary_status_invalid")
    horizons = value.get("horizons")
    if not isinstance(horizons, dict) or set(horizons) != {"15", "30"}:
        raise GateError("fresh_oos_summary_horizons_invalid")
    for key in (
        "parent_model_refit",
        "calibrator_refit",
        "sensor_retuning",
        "cohort_retuning",
        "substitute_data_used",
        "production_authority",
    ):
        if value.get(key) is not False:
            raise GateError("fresh_oos_summary_forbidden_scope")
    return value


def main() -> None:
    state, root = rb.load_state()
    if state.get("profile_name") != "risk-v2-phase1b-fresh-oos-v1":
        raise GateError("fresh_oos_profile_state_mismatch")
    if not state.get("compute_success"):
        raise GateError("fresh_oos_compute_not_validated")
    path = root / "results" / "study" / "SUMMARY.json"
    try:
        summary = validate_summary(json.loads(path.read_text()))
    except GateError:
        raise
    except Exception:
        raise GateError("fresh_oos_summary_unreadable") from None

    payload = (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode()
    api = rb.require_private_api()
    target = (
        f"repos/{rb.PRIVATE_REPO}/contents/research/public-runs/"
        f"{state['run_id']}-fresh-oos-summary.json"
    )
    api.request(
        target,
        {
            "message": "Mirror validated Risk Phase-1b fresh OOS summary [skip ci]",
            "branch": state["branch"],
            "content": base64.b64encode(payload).decode(),
        },
        method="PUT",
    )
    returned = api.request(target + "?ref=" + urllib.parse.quote(state["branch"], safe=""))
    if base64.b64decode(returned["content"]) != payload:
        raise GateError("fresh_oos_summary_private_readback_failed")
    print("Validated fresh-OOS aggregate summary mirrored to the private run branch.")


def run() -> None:
    try:
        main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Execution failed; no unvalidated fresh-OOS summary was mirrored.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
