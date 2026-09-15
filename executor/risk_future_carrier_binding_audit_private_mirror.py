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
SCHEMA = "risk_tool_v2_future_carrier_binding_audit_result@2.0"
TASK = "CSI1000-RISK-V2-FUTURE-CARRIER-BINDING-AUDIT-V1-20260915"
AMENDMENT_SHA256 = "7972fbc0a13671cf182cdb0c7c3b4ce6d10588c63cbe34c9e6871f300626f371"


def validate(value: dict) -> None:
    required = {
        "schema_id",
        "task_id",
        "profile",
        "amendment_sha256",
        "original_prereg_sha256",
        "status",
        "source_contract",
        "source_artifact",
        "canonical_1m_parent_dataset_version",
        "parent_dataset_binding_valid",
        "declared_target_symbols_present",
        "target_symbols",
        "matching_view_indexes",
        "view_binding_unique",
        "pair_overlap",
        "future_oos_window",
        "controls",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise GateError("future_binding_mirror_shape_invalid")
    if value.get("schema_id") != SCHEMA or value.get("task_id") != TASK or value.get("profile") != PROFILE:
        raise GateError("future_binding_mirror_identity_invalid")
    if value.get("amendment_sha256") != AMENDMENT_SHA256:
        raise GateError("future_binding_mirror_amendment_invalid")
    if value.get("status") != "SOURCE_FAMILY_BINDING_VALID":
        raise GateError("future_binding_mirror_status_invalid")
    contract = value.get("source_contract")
    if not isinstance(contract, dict) or set(contract) != {"archive_path", "bytes", "sha256"}:
        raise GateError("future_binding_mirror_source_contract_invalid")
    artifact = value.get("source_artifact")
    if not isinstance(artifact, dict) or set(artifact) != {"name", "sha256", "rows", "binding_valid"}:
        raise GateError("future_binding_mirror_artifact_invalid")
    if artifact.get("binding_valid") is not True:
        raise GateError("future_binding_mirror_artifact_binding_invalid")
    targets = value.get("target_symbols")
    if not isinstance(targets, dict) or set(targets) != {"000688.SH", "000852.SH"}:
        raise GateError("future_binding_mirror_targets_invalid")
    safe_target_keys = {
        "rows", "first_trading_day", "last_trading_day",
        "trading_day_count", "expected_trading_day_count", "day_count_ready",
    }
    for row in targets.values():
        if not isinstance(row, dict) or set(row) != safe_target_keys:
            raise GateError("future_binding_mirror_target_shape_invalid")
    if value.get("parent_dataset_binding_valid") is not True or value.get("declared_target_symbols_present") is not True:
        raise GateError("future_binding_mirror_family_binding_invalid")
    indexes = value.get("matching_view_indexes")
    if not isinstance(indexes, list) or len(indexes) != 1 or type(indexes[0]) is not int:
        raise GateError("future_binding_mirror_view_index_invalid")
    if value.get("view_binding_unique") is not True:
        raise GateError("future_binding_mirror_view_binding_invalid")
    future = value.get("future_oos_window")
    if (
        not isinstance(future, dict)
        or future.get("current_snapshot_is_future_oos_evidence") is not False
        or future.get("activation_requires_new_snapshot_covering_full_window_for_both_symbols") is not True
    ):
        raise GateError("future_binding_mirror_future_semantics_invalid")
    controls = value.get("controls")
    if not isinstance(controls, dict) or not controls or any(v is not False for v in controls.values()):
        raise GateError("future_binding_mirror_control_violation")


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
            "message": "Record verified future Risk Tool source-family binding audit [skip ci]",
            "branch": state["branch"],
            "content": base64.b64encode(raw).decode("ascii"),
        },
        method="PUT",
    )
    got = api.request(target + "?ref=" + base.urllib.parse.quote(state["branch"], safe=""))
    if base64.b64decode(got["content"]) != raw:
        raise GateError("future_binding_mirror_readback_failed")
    print("Verified future source-family carrier binding audit mirrored privately.")


if __name__ == "__main__":
    main()
