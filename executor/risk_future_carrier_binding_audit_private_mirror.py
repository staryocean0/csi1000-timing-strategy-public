from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_rb_future_binding_mirror", HERE / "research_broker.py")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

GateError = base.GateError
PROFILE = "risk-v2-future-carrier-binding-audit-v1"
SCHEMA = "risk_tool_v2_future_carrier_binding_audit_result@1.0"
TASK = "CSI1000-RISK-V2-FUTURE-CARRIER-BINDING-AUDIT-V1-20260915"
ALLOWED_STATUSES = {"PAIR_BINDING_VALID_FOR_SOURCE_FAMILY", "PAIR_BINDING_INVALID"}


def validate(value: dict) -> None:
    if not isinstance(value, dict):
        raise GateError("future_binding_mirror_not_object")
    required = {
        "schema_id", "task_id", "profile", "prereg_sha256", "status", "source",
        "members", "pair_overlap", "future_oos_window", "controls",
    }
    if set(value) != required:
        raise GateError("future_binding_mirror_shape_invalid")
    if value.get("schema_id") != SCHEMA or value.get("task_id") != TASK or value.get("profile") != PROFILE:
        raise GateError("future_binding_mirror_identity_invalid")
    if value.get("status") not in ALLOWED_STATUSES:
        raise GateError("future_binding_mirror_status_invalid")
    members = value.get("members")
    if not isinstance(members, dict) or set(members) != {"000688.SH", "000852.SH"}:
        raise GateError("future_binding_mirror_members_invalid")
    for symbol, row in members.items():
        if not isinstance(row, dict) or row.get("expected_symbol") != symbol:
            raise GateError("future_binding_mirror_member_shape_invalid")
        if row.get("market_value_columns_read") is not False or row.get("row_level_data_exported") is not False:
            raise GateError("future_binding_mirror_export_violation")
        if not isinstance(row.get("distinct_symbols"), list) or len(row["distinct_symbols"]) > 4:
            raise GateError("future_binding_mirror_symbols_invalid")
        if not isinstance(row.get("physical_fields"), list) or len(row["physical_fields"]) > 64:
            raise GateError("future_binding_mirror_schema_too_large")
    controls = value.get("controls")
    if not isinstance(controls, dict) or not controls or any(v is not False for v in controls.values()):
        raise GateError("future_binding_mirror_control_violation")
    future = value.get("future_oos_window")
    if not isinstance(future, dict) or future.get("current_snapshot_is_future_oos_evidence") is not False:
        raise GateError("future_binding_mirror_future_semantics_invalid")


def main() -> None:
    state, root = base.load_state()
    if (
        state.get("profile_name") != PROFILE
        or state.get("compute_success") is not True
        or state.get("cleanup_complete") is not True
    ):
        raise GateError("future_binding_state_not_mirrorable")
    path = root / "results" / "study" / "BINDING_AUDIT.json"
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 256 * 1024:
        raise GateError("future_binding_mirror_file_invalid")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception:
        raise GateError("future_binding_mirror_json_invalid") from None
    validate(value)
    api = base.require_private_api()
    target = f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-future-carrier-binding.json"
    api.request(
        target,
        {
            "message": "Record verified future Risk Tool carrier binding audit [skip ci]",
            "branch": state["branch"],
            "content": base64.b64encode(raw).decode("ascii"),
        },
        method="PUT",
    )
    got = api.request(target + "?ref=" + base.urllib.parse.quote(state["branch"], safe=""))
    if base64.b64decode(got["content"]) != raw:
        raise GateError("future_binding_mirror_readback_failed")
    print("Verified future carrier-binding audit mirrored privately.")


if __name__ == "__main__":
    main()
