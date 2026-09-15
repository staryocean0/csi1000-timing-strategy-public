"""Mirror only verified V0800-B1 aggregate text outputs to the private run branch."""
from __future__ import annotations

import base64
import json

import research_broker as base

GateError = base.GateError
PROFILE = "two-wave-v0800-b1-strict-continuity-v1"
TEXT_OUTPUTS = ("SUMMARY.json", "INPUT_RECEIPT.json")
MAX_TEXT_BYTES = 256 * 1024


def validate_summary(raw: bytes) -> None:
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception:
        raise GateError("two_wave_v0800_b1_summary_invalid") from None
    if value.get("schema_id") != "csi1000.two_wave_v0800_b1_strict_continuity_summary@1.0":
        raise GateError("two_wave_v0800_b1_summary_schema_mismatch")
    continuity = value.get("continuity_policy", {})
    if continuity.get("direction_eligible_pair_semantic") != "shared_anchor_strict_L-H-L-H-L":
        raise GateError("two_wave_v0800_b1_continuity_policy_mismatch")
    if continuity.get("same_scale_ledger_nearest_role") != "diagnostic_only" or continuity.get("skip_based_pair_direction_authority") is not False:
        raise GateError("two_wave_v0800_b1_skip_authority_violation")
    for key in (
        "future_outcome_used",
        "pnl_used",
        "morphology_acceptance",
        "direction_authority",
        "trade_authority",
        "production_authority",
        "v0800_c_dispatch_allowed_by_this_result",
    ):
        if value.get(key) is not False:
            raise GateError("two_wave_v0800_b1_summary_scope_violation")
    if value.get("rho_winner") is not None or value.get("legacy_control_can_win") is not False:
        raise GateError("two_wave_v0800_b1_premature_authority")


def main() -> None:
    state, root = base.load_state()
    if state.get("profile_name") != PROFILE:
        raise GateError("two_wave_v0800_b1_text_mirror_wrong_profile")
    if state.get("compute_success") is not True or state.get("cleanup_complete") is not True:
        raise GateError("two_wave_v0800_b1_text_mirror_requires_verified_success")
    api = base.require_private_api()
    study = root / "results" / "study"
    for name in TEXT_OUTPUTS:
        path = study / name
        if path.is_symlink() or not path.is_file():
            raise GateError("two_wave_v0800_b1_text_output_missing")
        raw = path.read_bytes()
        if not raw or len(raw) > MAX_TEXT_BYTES:
            raise GateError("two_wave_v0800_b1_text_output_size_invalid")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            raise GateError("two_wave_v0800_b1_text_output_not_utf8") from None
        if name == "SUMMARY.json":
            validate_summary(raw)
        target = f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-results/{name}"
        api.request(
            target,
            {
                "message": "Record verified Two-Wave V0800-B1 aggregate result [skip ci]",
                "branch": state["branch"],
                "content": base64.b64encode(raw).decode("ascii"),
            },
            method="PUT",
        )
        returned = api.request(target + "?ref=" + base.urllib.parse.quote(state["branch"], safe=""))
        if base64.b64decode(returned["content"]) != raw:
            raise GateError("two_wave_v0800_b1_text_output_readback_failed")
    print("Verified Two-Wave V0800-B1 aggregate outputs mirrored to the private run branch.")


if __name__ == "__main__":
    try:
        main()
    except GateError as error:
        raise SystemExit("Execution stopped: " + str(error))
