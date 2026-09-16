from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_rb_native15_c1_attr", HERE / "research_broker.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
GateError = base.GateError

PROFILE = "risk-v3-native15-c1-gate-attribution-v1"
TASK = "CSI1000-RISK-V3-NATIVE15-C1-GATE-ATTRIBUTION-V1-20260916"
SCHEMA = "risk_tool_v3_native15_c1_gate_attribution_result@1.0"
STATUS = "NATIVE15_C1_GATE_ATTRIBUTION_COMPLETE"


def validate(value: dict) -> None:
    if value.get("schema_id") != SCHEMA or value.get("task_id") != TASK or value.get("profile") != PROFILE:
        raise GateError("native15_c1_attr_mirror_identity_invalid")
    if value.get("status") != STATUS or value.get("next_phase_authorized") is not False or value.get("next_phase") is not None:
        raise GateError("native15_c1_attr_mirror_status_invalid")
    parent = value.get("parent_c1") or {}
    if parent.get("public_run_id") != "35041411237-1" or parent.get("candidate_count") != 576 or parent.get("passing_count") != 0 or parent.get("shortlist_count") != 0:
        raise GateError("native15_c1_attr_mirror_parent_invalid")
    controls = value.get("controls")
    if not isinstance(controls, dict) or any(item is not False for item in controls.values()):
        raise GateError("native15_c1_attr_mirror_control_violation")
    if value.get("candidate_count") != 576 or not isinstance(value.get("per_gate"), dict):
        raise GateError("native15_c1_attr_mirror_aggregate_invalid")
    nearest = value.get("nearest_candidates")
    if not isinstance(nearest, list) or len(nearest) > 12:
        raise GateError("native15_c1_attr_mirror_nearest_invalid")
    forbidden = {"candidates", "state_support", "event_capture", "episodes", "prices", "returns", "timestamps", "raw_rows"}
    if forbidden.intersection(value):
        raise GateError("native15_c1_attr_mirror_private_surface_violation")


def main() -> None:
    state, root = base.load_state()
    if state.get("profile_name") != PROFILE or state.get("compute_success") is not True or state.get("cleanup_complete") is not True:
        raise GateError("native15_c1_attr_state_not_mirrorable")
    path = root / "results" / "study" / "NATIVE15_C1_GATE_ATTRIBUTION.json"
    if not path.is_file() or path.is_symlink() or not 0 < path.stat().st_size <= 512 * 1024:
        raise GateError("native15_c1_attr_mirror_file_invalid")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode())
    except Exception as exc:
        raise GateError("native15_c1_attr_mirror_decode_failed") from exc
    validate(value)
    api = base.require_private_api()
    target = f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-native15-c1-gate-attribution.json"
    api.request(target, {"message": "Record verified Native-15m C1 gate attribution [skip ci]", "branch": state["branch"], "content": base64.b64encode(raw).decode()}, method="PUT")
    got = api.request(target + "?ref=" + base.urllib.parse.quote(state["branch"], safe=""))
    if base64.b64decode(got["content"]) != raw:
        raise GateError("native15_c1_attr_mirror_readback_failed")
    print("Verified Native-15m C1 gate attribution mirrored privately.")


if __name__ == "__main__":
    main()
