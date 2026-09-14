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
import tarfile
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
DIAGNOSTIC_TEXT_FILES = (
    "compute.log",
    "compute_receipt.json",
    "controller_validation.json",
    "bundle_layout.json",
)
DIAGNOSTIC_TEXT_MAX_BYTES = 64 * 1024
ARCHIVE_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".zip", ".gz", ".bz2", ".xz")


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
    content_sha256 = hashlib.sha256(raw).hexdigest()
    if "git_blob_sha1" in expected:
        digest = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        if meta.get("sha") != expected["git_blob_sha1"] or digest != expected["git_blob_sha1"]:
            raise GateError("source_blob_digest_mismatch")
        expected["sha256"] = content_sha256
    elif content_sha256 != expected["sha256"]:
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


def _row(name, meta):
    if not isinstance(meta, dict) or set(meta) != {"bytes", "sha256"}:
        raise GateError("bundle_layout_manifest_metadata_invalid")
    return {"path": name, "bytes": meta["bytes"], "sha256": meta["sha256"]}


def _write_bundle_layout():
    state, root = base.load_state()
    bundle = root / "work" / "inputs" / "bundle.tar"
    with tarfile.open(bundle, "r:") as archive:
        member = archive.getmember("BUNDLE_MANIFEST.json")
        stream = archive.extractfile(member)
        if stream is None:
            raise GateError("bundle_layout_manifest_unreadable")
        manifest = json.load(stream)
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if manifest.get("schema") != "csi1000_handoff_bundle@1" or not isinstance(files, dict):
        raise GateError("bundle_layout_manifest_invalid")
    names = sorted(files)
    archive_like = [name for name in names if name.lower().endswith(ARCHIVE_SUFFIXES)]
    canonical_5m_like = [name for name in names if "data/market/5m/" in name.lower()]
    five_minute_like = [name for name in names if "5m" in name.lower()][:100]
    layer_like = [name for name in names if "layer" in name.lower()][:100]
    bundle_like = [name for name in names if "bundle" in name.lower()][:100]
    value = {
        "schema_id": "risk_tool_v2_bundle_layout@1.0",
        "public_run_id": state["run_id"],
        "manifest_schema": manifest.get("schema"),
        "file_count": len(files),
        "archive_like": [_row(name, files[name]) for name in archive_like[:100]],
        "archive_like_total": len(archive_like),
        "canonical_5m_like": [_row(name, files[name]) for name in canonical_5m_like],
        "canonical_5m_like_total": len(canonical_5m_like),
        "five_minute_like": [_row(name, files[name]) for name in five_minute_like],
        "five_minute_like_total": sum("5m" in name.lower() for name in names),
        "layer_like": [_row(name, files[name]) for name in layer_like],
        "layer_like_total": sum("layer" in name.lower() for name in names),
        "bundle_like": [_row(name, files[name]) for name in bundle_like],
        "bundle_like_total": sum("bundle" in name.lower() for name in names),
        "market_rows_read": 0,
    }
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(raw) > DIAGNOSTIC_TEXT_MAX_BYTES:
        raise GateError("bundle_layout_too_large")
    (root / "results" / "bundle_layout.json").write_bytes(raw)


def _publish_failure_diagnostics():
    state, root = base.load_state()
    api = base.require_private_api()
    results = root / "results"
    published = 0
    for name in DIAGNOSTIC_TEXT_FILES:
        path = results / name
        if path.is_symlink():
            raise GateError("diagnostic_text_is_link")
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if len(raw) > DIAGNOSTIC_TEXT_MAX_BYTES:
            raise GateError("diagnostic_text_too_large")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            raise GateError("diagnostic_text_not_utf8") from None
        target = f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-diagnostics/{name}"
        api.request(
            target,
            {
                "message": "Record bounded Risk Tool failure diagnostic [skip ci]",
                "branch": state["branch"],
                "content": base64.b64encode(raw).decode("ascii"),
            },
            method="PUT",
        )
        returned = api.request(target + "?ref=" + base.urllib.parse.quote(state["branch"], safe=""))
        if base64.b64decode(returned["content"]) != raw:
            raise GateError("private_diagnostic_readback_failed")
        published += 1
    if published == 0:
        raise GateError("diagnostic_text_missing")
    print("Bounded Risk Tool failure diagnostics verified on the private run branch.")


_original_prepare = base.prepare
_original_publish = base.publish


def prepare(profile_name, profile):
    _original_prepare(profile_name, profile)
    _write_bundle_layout()


def publish(profile):
    try:
        _original_publish(profile)
    except GateError as error:
        if str(error) == "compute_failed_consult_private_receipt":
            _publish_failure_diagnostics()
        raise


base.PROFILE_NAME = PROFILE_NAME
base.SOURCE_PATHS = SOURCE_PATHS
base.MANIFEST_PATH = MANIFEST_PATH
base.COMMAND = COMMAND
base.VERIFY_COMMAND = VERIFY_COMMAND
base._digest_pair = digest_pair
base.fetch_source_file = fetch_source_file
base.load_profile = load_profile
base.prepare = prepare
base.publish = publish


def run():
    base.run()


if __name__ == "__main__":
    run()
