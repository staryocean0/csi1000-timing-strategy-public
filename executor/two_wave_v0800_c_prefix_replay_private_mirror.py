"""Mirror verified V0800-C aggregate text outputs to the private run branch."""
from __future__ import annotations

import base64
import json
import research_broker as base

GateError = base.GateError
PROFILE = "two-wave-v0800-c-causal-prefix-replay-v1"
TEXT_OUTPUTS = ("SUMMARY.json", "INPUT_RECEIPT.json")
MAX_TEXT_BYTES = 256 * 1024


def validate_summary(raw: bytes) -> None:
    try: value = json.loads(raw.decode("utf-8"))
    except Exception: raise GateError("two_wave_v0800_c_summary_invalid") from None
    if value.get("schema_id") != "csi1000.two_wave_v0800_c_causal_prefix_replay_summary@1.0": raise GateError("two_wave_v0800_c_summary_schema_mismatch")
    producer = value.get("producer", {})
    if producer.get("implementation") != "independent_incremental_state_machine" or producer.get("event_visibility") != "confirmation_bar_only": raise GateError("two_wave_v0800_c_producer_identity_mismatch")
    if producer.get("append_only_event_ledgers") is not True or producer.get("prefix_replay_complete") is not True or producer.get("independent_verifier_required") is not True: raise GateError("two_wave_v0800_c_replay_incomplete")
    if value.get("legacy_rho_2_evaluated") is not False or value.get("rho_winner") is not None: raise GateError("two_wave_v0800_c_rho_scope_violation")
    for key in ("rho_winner_selection", "direction_thresholds_used", "pair_state_publication", "future_outcome_used", "pnl_used", "positions_used", "year_2026_read", "trade_authority", "production_authority", "v0800_d_authorized"):
        if value.get(key) is not False: raise GateError("two_wave_v0800_c_scope_violation")


def main() -> None:
    state, root = base.load_state()
    if state.get("profile_name") != PROFILE: raise GateError("two_wave_v0800_c_text_mirror_wrong_profile")
    if state.get("compute_success") is not True or state.get("cleanup_complete") is not True: raise GateError("two_wave_v0800_c_text_mirror_requires_verified_success")
    api = base.require_private_api(); study = root / "results" / "study"
    for name in TEXT_OUTPUTS:
        path = study / name
        if path.is_symlink() or not path.is_file(): raise GateError("two_wave_v0800_c_text_output_missing")
        raw = path.read_bytes()
        if not raw or len(raw) > MAX_TEXT_BYTES: raise GateError("two_wave_v0800_c_text_output_size_invalid")
        try: raw.decode("utf-8")
        except UnicodeDecodeError: raise GateError("two_wave_v0800_c_text_output_not_utf8") from None
        if name == "SUMMARY.json": validate_summary(raw)
        target = f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-results/{name}"
        api.request(target, {"message": "Record verified Two-Wave V0800-C aggregate result [skip ci]", "branch": state["branch"], "content": base64.b64encode(raw).decode("ascii")}, method="PUT")
        returned = api.request(target + "?ref=" + base.urllib.parse.quote(state["branch"], safe=""))
        if base64.b64decode(returned["content"]) != raw: raise GateError("two_wave_v0800_c_text_output_readback_failed")
    print("Verified Two-Wave V0800-C aggregate outputs mirrored to the private run branch.")


if __name__ == "__main__":
    try: main()
    except GateError as error: raise SystemExit("Execution stopped: " + str(error))
