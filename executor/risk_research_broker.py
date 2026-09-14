"""Static public broker policy for the frozen Risk Tool 2.0 severity-persistence study.

This module deliberately reuses the reviewed research broker transport/security flow while
replacing only its exact profile allowlist. It does not permit arbitrary private source or
commands. The legacy handoff broker remains unchanged.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_legacy_research_broker", HERE / "research_broker.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("research broker unavailable")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

GateError = base.GateError

PROFILE_NAME = "risk-v2-severity-persistence-v1"
TRANSPORT_PROFILE_NAME = "handoff-verify-v1"
RISK_PROFILE_SCHEMA = "factorlab.public_risk_research_profile@1.0"
RISK_PROFILE_KEYS = {
    "schema_id",
    "profile_name",
    "transport_profile",
    "private_ref",
    "source_files",
    "manifest_path",
    "command",
    "verify_command",
    "command_timeout_seconds",
    "verification_timeout_seconds",
    "new_training",
    "production_authority",
}
SOURCE_PATHS = (
    "runtime/research/risk_tool_v2_severity_persistence_v1/run_study.py",
    "runtime/research/risk_tool_v2_severity_persistence_v1/run_study_v2.py",
    "runtime/research/risk_tool_v2_severity_persistence_v1/run_study_v3.py",
    "runtime/research/risk_tool_v2_severity_persistence_v1/verify_study.py",
    "runtime/research/risk_tool_v2_severity_persistence_v1/verify_study_v2.py",
    "docs/research/RISK_TOOL_V2_SEVERITY_PERSISTENCE_PROTOCOL_20260914.json",
    "handoff/INPUT_MANIFEST.json",
)
MANIFEST_PATH = "handoff/INPUT_MANIFEST.json"
COMMAND = [
    "runtime/research/risk_tool_v2_severity_persistence_v1/run_study_v3.py",
    "--inputs",
    "/work/inputs",
    "--out",
    "/results/study",
]
VERIFY_COMMAND = [
    "runtime/research/risk_tool_v2_severity_persistence_v1/verify_study_v2.py",
    "--inputs",
    "/work/inputs",
    "--results",
    "/results/study",
]


def digest_pair(value, min_bytes=1, max_bytes=base.SOURCE_BYTES_MAX):
    """Accept legacy SHA-256 pairs or immutable Git blob SHA-1 pairs."""
    if not isinstance(value, dict):
        raise GateError("unknown_profile_field")
    keys = set(value)
    if keys not in ({"bytes", "sha256"}, {"bytes", "git_blob_sha1"}):
        raise GateError("unknown_profile_field")
    size = value["bytes"]
    if type(size) is not int or size < min_bytes or size > max_bytes:
        raise GateError("profile_file_size_invalid")
    if "sha256" in value:
        if not isinstance(value["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]):
            raise GateError("profile_not_immutable")
    elif not isinstance(value["git_blob_sha1"], str) or not re.fullmatch(r"[0-9a-f]{40}", value["git_blob_sha1"]):
        raise GateError("profile_not_immutable")


def fetch_source_file(api, path, ref, expected):
    quoted = base.urllib.parse.quote(path, safe="/")
    meta = api.request(f"repos/{base.PRIVATE_REPO}/contents/{quoted}?ref={ref}")
    if meta.get("type") != "file" or meta.get("encoding") != "base64" or meta.get("size") != expected["bytes"]:
        raise GateError("source_blob_identity_failed")
    try:
        raw = base64.b64decode(meta["content"])
    except Exception:
        raise GateError("source_blob_identity_failed") from None
    if len(raw) != expected["bytes"]:
        raise GateError("source_blob_identity_failed")
    if "git_blob_sha1" in expected:
        digest = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        if meta.get("sha") != expected["git_blob_sha1"] or digest != expected["git_blob_sha1"]:
            raise GateError("source_blob_digest_mismatch")
    elif hashlib.sha256(raw).hexdigest() != expected["sha256"]:
        raise GateError("source_blob_digest_mismatch")
    return raw


def load_profile(name):
    if name != PROFILE_NAME:
        raise GateError("unknown_profile")
    try:
        risk_cfg = json.loads((HERE / "risk_profile.json").read_text())
        catalog = json.loads((HERE / "research_profiles.json").read_text())
    except Exception:
        raise GateError("profile_catalog_unavailable") from None
    if set(risk_cfg) != RISK_PROFILE_KEYS or risk_cfg.get("schema_id") != RISK_PROFILE_SCHEMA:
        raise GateError("profile_catalog_invalid")
    if risk_cfg.get("profile_name") != PROFILE_NAME or risk_cfg.get("transport_profile") != TRANSPORT_PROFILE_NAME:
        raise GateError("profile_catalog_invalid")
    if catalog.get("schema_id") != base.PROFILE_SCHEMA or set(catalog) != {"schema_id", "profiles"}:
        raise GateError("profile_catalog_invalid")
    transport = catalog.get("profiles", {}).get(TRANSPORT_PROFILE_NAME)
    if not isinstance(transport, dict):
        raise GateError("incomplete_profile")
    inherited = {
        key: transport[key]
        for key in (
            "manifest_sha256",
            "data_release_tag",
            "data_asset_name",
            "data_asset_sha256",
            "data_asset_bytes",
            "input_files",
            "asset_parts",
        )
        if key in transport
    }
    required_inherited = {
        "manifest_sha256",
        "data_release_tag",
        "data_asset_name",
        "data_asset_sha256",
        "data_asset_bytes",
        "input_files",
    }
    if not required_inherited.issubset(inherited):
        raise GateError("incomplete_profile")
    merged = {
        "private_ref": risk_cfg["private_ref"],
        "source_files": risk_cfg["source_files"],
        "manifest_path": risk_cfg["manifest_path"],
        **inherited,
        "command": risk_cfg["command"],
        "verify_command": risk_cfg["verify_command"],
        "command_timeout_seconds": risk_cfg["command_timeout_seconds"],
        "verification_timeout_seconds": risk_cfg["verification_timeout_seconds"],
        "new_training": risk_cfg["new_training"],
        "production_authority": risk_cfg["production_authority"],
    }
    return base.validate_profile(merged)


# Patch only the immutable policy surface of the reviewed broker. Transport, isolation,
# result collection, cleanup and private writeback code are reused unchanged.
base.PROFILE_NAME = PROFILE_NAME
base.SOURCE_PATHS = SOURCE_PATHS
base.MANIFEST_PATH = MANIFEST_PATH
base.COMMAND = COMMAND
base.VERIFY_COMMAND = VERIFY_COMMAND
base._digest_pair = digest_pair
base.fetch_source_file = fetch_source_file
base.load_profile = load_profile


def run():
    base.run()


if __name__ == "__main__":
    run()
