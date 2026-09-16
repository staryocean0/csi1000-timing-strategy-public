"""Mirror only verified V0800-G aggregate text outputs to the private run branch.

BAR_CARRIER.csv is deliberately excluded.  The mirror exists for source review
but is not wired into the standard workflow in this phase.
"""
from __future__ import annotations

import base64
import json

import research_broker as base

GateError = base.GateError
PROFILE = "two-wave-v0800-g-bar-time-carrier-semantics-v1"
TEXT_OUTPUTS = ("SUMMARY.json", "INPUT_RECEIPT.json")
MAX_TEXT_BYTES = 256 * 1024
DATA_BYTES = 3351411
DATA_SHA256 = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"
ROWS = 70114


def parse_json(raw: bytes, reason: str) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception:
        raise GateError(reason) from None
    if not isinstance(value, dict):
        raise GateError(reason)
    return value


def validate_summary(raw: bytes) -> None:
    value = parse_json(raw, "two_wave_v0800_g_summary_invalid")
    if value.get("schema_id") != "csi1000.two_wave_v0800_g_bar_time_carrier_summary@1.0":
        raise GateError("two_wave_v0800_g_summary_schema_mismatch")
    if value.get("study") != "V0800-G_BAR_TIME_CARRIER_EXPIRY_SEMANTICS":
        raise GateError("two_wave_v0800_g_summary_study_mismatch")
    if int(value.get("bars_read", -1)) != ROWS:
        raise GateError("two_wave_v0800_g_bar_universe_mismatch")
    if int(value.get("strict_event_count", -1)) != 2358 or int(value.get("eligible_event_count", -1)) != 924:
        raise GateError("two_wave_v0800_g_event_universe_mismatch")
    if int(value.get("reset_count", -1)) != 164:
        raise GateError("two_wave_v0800_g_reset_universe_mismatch")
    if value.get("carrier_semantics") != "state_known_before_bar_begins":
        raise GateError("two_wave_v0800_g_carrier_semantics_mismatch")
    if value.get("first_carrier_bar_formula") != "confirmation_bar + 1":
        raise GateError("two_wave_v0800_g_knowledge_time_mismatch")
    for key in (
        "strict_event_supersedes_previous_carrier",
        "uncertain_clears_previous_carrier",
        "scale_mismatch_clears_previous_carrier",
        "reset_clears_previous_carrier",
    ):
        if value.get(key) is not True:
            raise GateError("two_wave_v0800_g_invalidation_rule_mismatch")
    for key in (
        "fixed_bar_expiry_used",
        "parameter_search_used",
        "automatic_acceptance",
        "bar_time_publication_authority",
        "direction_acceptance",
        "future_outcome_used",
        "returns_used",
        "pnl_used",
        "positions_used",
        "year_2026_read",
        "trade_authority",
        "production_authority",
    ):
        if value.get(key) is not False:
            raise GateError("two_wave_v0800_g_summary_scope_violation")
    if value.get("post_run_adjudication_required") is not True:
        raise GateError("two_wave_v0800_g_adjudication_gate_missing")
    if int(value.get("minimum_carrier_lag_bars", -1)) != 1:
        raise GateError("two_wave_v0800_g_same_bar_carry_violation")
    anti = value.get("hold_until_next_eligible_anti_control")
    if not isinstance(anti, dict) or anti.get("authority_candidate") is not False:
        raise GateError("two_wave_v0800_g_anti_control_authority_violation")


def validate_receipt(raw: bytes) -> None:
    value = parse_json(raw, "two_wave_v0800_g_input_receipt_invalid")
    if value.get("schema_id") != "csi1000.two_wave_v0800_g_input@1.0":
        raise GateError("two_wave_v0800_g_input_schema_mismatch")
    if int(value.get("rows_read", -1)) != ROWS or int(value.get("bytes", -1)) != DATA_BYTES:
        raise GateError("two_wave_v0800_g_input_shape_mismatch")
    if value.get("sha256") != DATA_SHA256:
        raise GateError("two_wave_v0800_g_input_digest_mismatch")
    if value.get("substitute_data_used") is not False or value.get("year_2026_read") is not False:
        raise GateError("two_wave_v0800_g_input_scope_violation")


def main() -> None:
    state, root = base.load_state()
    if state.get("profile_name") != PROFILE:
        raise GateError("two_wave_v0800_g_text_mirror_wrong_profile")
    if state.get("compute_success") is not True or state.get("cleanup_complete") is not True:
        raise GateError("two_wave_v0800_g_text_mirror_requires_verified_success")
    api = base.require_private_api()
    study = root / "results" / "study"
    for name in TEXT_OUTPUTS:
        path = study / name
        if path.is_symlink() or not path.is_file():
            raise GateError("two_wave_v0800_g_text_output_missing")
        raw = path.read_bytes()
        if not raw or len(raw) > MAX_TEXT_BYTES:
            raise GateError("two_wave_v0800_g_text_output_size_invalid")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            raise GateError("two_wave_v0800_g_text_output_not_utf8") from None
        if name == "SUMMARY.json":
            validate_summary(raw)
        else:
            validate_receipt(raw)
        target = f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-results/{name}"
        api.request(
            target,
            {
                "message": "Record verified Two-Wave V0800-G aggregate result [skip ci]",
                "branch": state["branch"],
                "content": base64.b64encode(raw).decode("ascii"),
            },
            method="PUT",
        )
        returned = api.request(target + "?ref=" + base.urllib.parse.quote(state["branch"], safe=""))
        if base64.b64decode(returned["content"]) != raw:
            raise GateError("two_wave_v0800_g_text_output_readback_failed")
    print("Verified Two-Wave V0800-G aggregate outputs mirrored to the private run branch.")


if __name__ == "__main__":
    try:
        main()
    except GateError as error:
        raise SystemExit("Execution stopped: " + str(error))
