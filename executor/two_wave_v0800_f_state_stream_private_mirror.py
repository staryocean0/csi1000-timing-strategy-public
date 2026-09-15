"""Mirror only verified V0800-F aggregate text outputs to the private run branch."""
from __future__ import annotations

import base64
import json

import research_broker as base

GateError = base.GateError
PROFILE = "two-wave-v0800-f-state-stream-audit-v1"
TEXT_OUTPUTS = ("SUMMARY.json", "INPUT_RECEIPT.json")
MAX_TEXT_BYTES = 256 * 1024


def validate_summary(raw: bytes) -> None:
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception:
        raise GateError("two_wave_v0800_f_summary_invalid") from None
    if value.get("schema_id") != "csi1000.two_wave_v0800_f_state_stream_summary@1.0":
        raise GateError("two_wave_v0800_f_summary_schema_mismatch")
    if value.get("study") != "V0800-F_OPERATIONAL_STATE_STREAM_AUDIT":
        raise GateError("two_wave_v0800_f_summary_study_mismatch")
    params = value.get("fixed_parameters", {})
    if params.get("rho_symbolic") != "sqrt(2)" or params.get("tau") != 0.20 or params.get("kappa") != 2.00:
        raise GateError("two_wave_v0800_f_fixed_parameter_drift")
    if int(value.get("strict_pair_count", -1)) != 2358 or int(value.get("eligible_same_scale_pair_count", -1)) != 924:
        raise GateError("two_wave_v0800_f_parent_universe_drift")
    if int(value.get("shared_descriptor_mismatch_count", -1)) != 0 or int(value.get("direct_opposite_trend_transition_count", -1)) != 0:
        raise GateError("two_wave_v0800_f_structural_invariant_failed")
    if value.get("structural_integrity_passed") is not True or value.get("state_stream_acceptance") is not None:
        raise GateError("two_wave_v0800_f_premature_acceptance")
    if value.get("automatic_parameter_search_used") is not False or value.get("post_run_semantic_adjudication_required") is not True:
        raise GateError("two_wave_v0800_f_search_or_adjudication_scope_violation")
    for key in (
        "future_outcome_used", "returns_used", "pnl_used", "positions_used", "year_2026_read",
        "direction_acceptance", "state_publication_authority", "trade_authority", "production_authority",
    ):
        if value.get(key) is not False:
            raise GateError("two_wave_v0800_f_summary_scope_violation")


def main() -> None:
    state, root = base.load_state()
    if state.get("profile_name") != PROFILE:
        raise GateError("two_wave_v0800_f_text_mirror_wrong_profile")
    if state.get("compute_success") is not True or state.get("cleanup_complete") is not True:
        raise GateError("two_wave_v0800_f_text_mirror_requires_verified_success")
    api = base.require_private_api()
    study = root / "results" / "study"
    for name in TEXT_OUTPUTS:
        path = study / name
        if path.is_symlink() or not path.is_file():
            raise GateError("two_wave_v0800_f_text_output_missing")
        raw = path.read_bytes()
        if not raw or len(raw) > MAX_TEXT_BYTES:
            raise GateError("two_wave_v0800_f_text_output_size_invalid")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            raise GateError("two_wave_v0800_f_text_output_not_utf8") from None
        if name == "SUMMARY.json":
            validate_summary(raw)
        target = f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-results/{name}"
        api.request(
            target,
            {
                "message": "Record verified Two-Wave V0800-F aggregate result [skip ci]",
                "branch": state["branch"],
                "content": base64.b64encode(raw).decode("ascii"),
            },
            method="PUT",
        )
        returned = api.request(target + "?ref=" + base.urllib.parse.quote(state["branch"], safe=""))
        if base64.b64decode(returned["content"]) != raw:
            raise GateError("two_wave_v0800_f_text_output_readback_failed")
    print("Verified Two-Wave V0800-F aggregate outputs mirrored to the private run branch.")


if __name__ == "__main__":
    try:
        main()
    except GateError as error:
        raise SystemExit("Execution stopped: " + str(error))
