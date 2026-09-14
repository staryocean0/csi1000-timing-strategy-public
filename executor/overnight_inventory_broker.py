"""Static public broker policy for metadata-only Overnight official bundle inventory.

Reuses the reviewed handoff transport/security flow. The only private source blob is the
fixed handoff INPUT_MANIFEST; inventory/validator programs are reviewed public source.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_legacy_research_broker", HERE / "research_broker.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("research broker unavailable")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

GateError = base.GateError

PROFILE_NAME = "overnight-official-inventory-v1"
TRANSPORT_PROFILE_NAME = "handoff-verify-v1"
PROFILE_SCHEMA = "factorlab.public_overnight_inventory_profile@1.0"
PROFILE_KEYS = {
    "schema_id",
    "profile_name",
    "transport_profile",
    "private_ref",
    "private_source_files",
    "public_source_files",
    "manifest_path",
    "command",
    "verify_command",
    "command_timeout_seconds",
    "verification_timeout_seconds",
    "new_training",
    "production_authority",
}
SOURCE_PATHS = ("handoff/INPUT_MANIFEST.json",)
PUBLIC_SOURCE_MAP = {
    "overnight_inventory.py": "overnight_inventory/run_study.py",
    "verify_overnight_inventory.py": "overnight_inventory/verify_study.py",
}
MANIFEST_PATH = "handoff/INPUT_MANIFEST.json"
COMMAND = [
    "overnight_inventory/run_study.py",
    "--inputs",
    "/work/inputs",
    "--out",
    "/results/study",
]
VERIFY_COMMAND = [
    "overnight_inventory/verify_study.py",
    "--inputs",
    "/work/inputs",
    "--results",
    "/results/study",
]
RESULT_SCHEMA = "csi1000.overnight_official_snapshot_inventory@1.0"
OFFICIAL_SNAPSHOT_ID = "d113b42dca967bb1061c8a6115c5d934e5a41074"
RESULT_TOP_KEYS = {
    "schema_id",
    "official_snapshot_id",
    "status",
    "bundle_file_count",
    "bundle_declared_bytes",
    "matched_files",
    "carrier_family_status",
    "all_required_families_present",
    "outcome_rows_read",
    "market_data_files_opened",
    "training_executed",
    "strategy_replayed",
    "production_authority",
}
CARRIER_KEYS = {
    "csi1000_gap_and_opening_clock",
    "rvol20_source",
    "b1_global_risk_source",
    "b2_china_offshore_source",
    "b4_driver_coherence_source",
}
STATUS_VALUES = {"PRESENT", "ABSENT", "AMBIGUOUS_FROM_NAMES_ONLY"}

legacy_prepare_inputs = base.prepare_inputs
legacy_publish = base.publish


def _digest(value):
    if not isinstance(value, dict) or set(value) not in ({"bytes", "sha256"}, {"bytes", "git_blob_sha1"}):
        raise GateError("unknown_profile_field")
    size = value["bytes"]
    if type(size) is not int or size <= 0 or size > base.SOURCE_BYTES_MAX:
        raise GateError("profile_file_size_invalid")
    if "sha256" in value:
        if not isinstance(value["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]):
            raise GateError("profile_not_immutable")
    elif not isinstance(value["git_blob_sha1"], str) or not re.fullmatch(r"[0-9a-f]{40}", value["git_blob_sha1"]):
        raise GateError("profile_not_immutable")


def _read_config():
    try:
        value = json.loads((HERE / "overnight_inventory_profile.json").read_text())
    except Exception:
        raise GateError("profile_catalog_unavailable") from None
    if not isinstance(value, dict) or set(value) != PROFILE_KEYS:
        raise GateError("profile_catalog_invalid")
    if value.get("schema_id") != PROFILE_SCHEMA or value.get("profile_name") != PROFILE_NAME:
        raise GateError("profile_catalog_invalid")
    if value.get("transport_profile") != TRANSPORT_PROFILE_NAME:
        raise GateError("profile_catalog_invalid")
    if value.get("manifest_path") != MANIFEST_PATH:
        raise GateError("unapproved_manifest_path")
    if value.get("command") != COMMAND or value.get("verify_command") != VERIFY_COMMAND:
        raise GateError("unapproved_command")
    if value.get("command_timeout_seconds") != 120 or value.get("verification_timeout_seconds") != 60:
        raise GateError("profile_timeout_changed")
    if value.get("new_training") is not False or value.get("production_authority") is not False:
        raise GateError("scope_not_authorized")
    private_files = value.get("private_source_files")
    if not isinstance(private_files, dict) or set(private_files) != set(SOURCE_PATHS):
        raise GateError("unapproved_source_set")
    for item in private_files.values():
        _digest(item)
    public_files = value.get("public_source_files")
    if not isinstance(public_files, dict) or set(public_files) != set(PUBLIC_SOURCE_MAP):
        raise GateError("unapproved_public_source_set")
    for item in public_files.values():
        _digest(item)
    return value


def load_profile(name):
    if name != PROFILE_NAME:
        raise GateError("unknown_profile")
    cfg = _read_config()
    try:
        catalog = json.loads((HERE / "research_profiles.json").read_text())
    except Exception:
        raise GateError("profile_catalog_unavailable") from None
    if catalog.get("schema_id") != base.PROFILE_SCHEMA or set(catalog) != {"schema_id", "profiles"}:
        raise GateError("profile_catalog_invalid")
    transport = catalog.get("profiles", {}).get(TRANSPORT_PROFILE_NAME)
    if not isinstance(transport, dict):
        raise GateError("incomplete_profile")
    inherited_keys = (
        "manifest_sha256",
        "data_release_tag",
        "data_asset_name",
        "data_asset_sha256",
        "data_asset_bytes",
        "input_files",
        "asset_parts",
    )
    inherited = {key: transport[key] for key in inherited_keys if key in transport}
    required = {
        "manifest_sha256",
        "data_release_tag",
        "data_asset_name",
        "data_asset_sha256",
        "data_asset_bytes",
        "input_files",
    }
    if not required.issubset(inherited):
        raise GateError("incomplete_profile")
    merged = {
        "private_ref": cfg["private_ref"],
        "source_files": cfg["private_source_files"],
        "manifest_path": cfg["manifest_path"],
        **inherited,
        "command": cfg["command"],
        "verify_command": cfg["verify_command"],
        "command_timeout_seconds": cfg["command_timeout_seconds"],
        "verification_timeout_seconds": cfg["verification_timeout_seconds"],
        "new_training": cfg["new_training"],
        "production_authority": cfg["production_authority"],
    }
    return base.validate_profile(merged)


def prepare_inputs(api, root, profile):
    work = legacy_prepare_inputs(api, root, profile)
    cfg = _read_config()
    target_root = work / "overnight_inventory"
    target_root.mkdir()
    for public_name, relative_target in PUBLIC_SOURCE_MAP.items():
        source = HERE / public_name
        expected = cfg["public_source_files"][public_name]
        if not source.is_file() or source.stat().st_size != expected["bytes"]:
            raise GateError("public_source_digest_mismatch")
        raw = source.read_bytes()
        if "sha256" in expected:
            verified = hashlib.sha256(raw).hexdigest() == expected["sha256"]
        else:
            verified = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() == expected["git_blob_sha1"]
        if not verified:
            raise GateError("public_source_digest_mismatch")
        target = work / relative_target
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise GateError("public_source_target_exists")
        shutil.copyfile(source, target)
        copied = target.read_bytes()
        if copied != raw:
            raise GateError("public_source_copy_mismatch")
    return work


def _safe_inventory_payload(path):
    if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise GateError("inventory_result_missing_or_oversize")
    try:
        value = json.loads(path.read_text())
    except Exception:
        raise GateError("inventory_result_invalid") from None
    if not isinstance(value, dict) or set(value) != RESULT_TOP_KEYS:
        raise GateError("inventory_result_invalid")
    if value.get("schema_id") != RESULT_SCHEMA or value.get("official_snapshot_id") != OFFICIAL_SNAPSHOT_ID:
        raise GateError("inventory_result_invalid")
    if value.get("status") != "passed" or value.get("outcome_rows_read") != 0 or value.get("market_data_files_opened") != 0:
        raise GateError("inventory_scope_violation")
    if value.get("training_executed") is not False or value.get("strategy_replayed") is not False or value.get("production_authority") is not False:
        raise GateError("inventory_scope_violation")
    carriers = value.get("carrier_family_status")
    if not isinstance(carriers, dict) or set(carriers) != CARRIER_KEYS or not set(carriers.values()).issubset(STATUS_VALUES):
        raise GateError("inventory_result_invalid")
    rows = value.get("matched_files")
    if not isinstance(rows, list) or len(rows) > 2000:
        raise GateError("inventory_result_invalid")
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256"}:
            raise GateError("inventory_result_invalid")
        if not isinstance(row["path"], str) or type(row["bytes"]) is not int or row["bytes"] < 0:
            raise GateError("inventory_result_invalid")
        if not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise GateError("inventory_result_invalid")
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def publish(profile):
    state, root = base.load_state()
    safe_payload = None
    if state.get("compute_success"):
        safe_payload = _safe_inventory_payload(root / "results" / "study" / "overnight_inventory.json")
    legacy_publish(profile)
    if safe_payload is None:
        return
    api = base.require_private_api()
    target = f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-overnight-inventory.json"
    api.request(
        target,
        {
            "message": "Record safe Overnight inventory result [skip ci]",
            "branch": state["branch"],
            "content": base64.b64encode(safe_payload).decode(),
        },
        method="PUT",
    )
    returned = api.request(target + "?ref=" + base.urllib.parse.quote(state["branch"], safe=""))
    try:
        readback = base64.b64decode(returned["content"])
    except Exception:
        raise GateError("inventory_private_readback_failed") from None
    if readback != safe_payload:
        raise GateError("inventory_private_readback_failed")
    print("Safe metadata-only Overnight inventory written to the private run branch.")


# Patch only the immutable policy surface of the reviewed broker.
base.PROFILE_NAME = PROFILE_NAME
base.SOURCE_PATHS = SOURCE_PATHS
base.MANIFEST_PATH = MANIFEST_PATH
base.COMMAND = COMMAND
base.VERIFY_COMMAND = VERIFY_COMMAND
base.COMMAND_TIMEOUT_SECONDS = 120
base.VERIFICATION_TIMEOUT_SECONDS = 60
base.load_profile = load_profile
base.prepare_inputs = prepare_inputs
base.publish = publish


def run():
    base.run()


if __name__ == "__main__":
    run()
