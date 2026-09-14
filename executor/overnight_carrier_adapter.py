"""Policy adapter for fixed Overnight carrier materialization."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load("_carrier_base", HERE / "research_broker.py")
policy = _load("_carrier_policy", HERE / "overnight_carrier_materialization_policy.py")
GateError = base.GateError

PROFILE_NAME = "overnight-carrier-materialization-v1"
TRANSPORT_PROFILE_NAME = "handoff-verify-v1"
PROFILE_SCHEMA = "factorlab.public_overnight_carrier_materialization_profile@1.0"
SOURCE_PATHS = ("handoff/INPUT_MANIFEST.json",)
MANIFEST_PATH = "handoff/INPUT_MANIFEST.json"
COMMAND = [
    "overnight_carrier_materialization/run_study.py",
    "--inputs",
    "/work/overnight_carrier",
    "--out",
    "/results/study",
]
VERIFY_COMMAND = [
    "overnight_carrier_materialization/verify_study.py",
    "--inputs",
    "/work/overnight_carrier",
    "--results",
    "/results/study",
]
PROFILE_KEYS = {
    "schema_id",
    "profile_name",
    "transport_profile",
    "private_ref",
    "private_source_files",
    "public_source_files",
    "source_manifest_path",
    "command",
    "verify_command",
    "command_timeout_seconds",
    "verification_timeout_seconds",
    "new_training",
    "production_authority",
}

legacy_prepare_inputs = base.prepare_inputs


def _private_digest(value):
    if not isinstance(value, dict) or set(value) != {"bytes", "sha256"}:
        raise GateError("profile_catalog_invalid")
    if type(value["bytes"]) is not int or not 1 <= value["bytes"] <= base.SOURCE_BYTES_MAX:
        raise GateError("profile_file_size_invalid")
    if not isinstance(value["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]):
        raise GateError("profile_not_immutable")


def _public_digest(value):
    if not isinstance(value, dict) or set(value) != {"git_blob_sha1"}:
        raise GateError("profile_catalog_invalid")
    digest = value["git_blob_sha1"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{40}", digest):
        raise GateError("profile_not_immutable")


def _read_config():
    try:
        value = json.loads((HERE / "overnight_carrier_materialization_profile.json").read_text())
    except Exception:
        raise GateError("profile_catalog_unavailable") from None
    if not isinstance(value, dict) or set(value) != PROFILE_KEYS:
        raise GateError("profile_catalog_invalid")
    if value.get("schema_id") != PROFILE_SCHEMA or value.get("profile_name") != PROFILE_NAME:
        raise GateError("profile_catalog_invalid")
    if value.get("transport_profile") != TRANSPORT_PROFILE_NAME:
        raise GateError("profile_catalog_invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", value.get("private_ref", "")):
        raise GateError("profile_not_immutable")
    if value.get("source_manifest_path") != policy.SOURCE_FILE:
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
        _private_digest(item)
    public_files = value.get("public_source_files")
    if not isinstance(public_files, dict) or set(public_files) != set(policy.PUBLIC_SOURCE_MAP):
        raise GateError("unapproved_public_source_set")
    for item in public_files.values():
        _public_digest(item)
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
        "manifest_path": MANIFEST_PATH,
        **inherited,
        "command": cfg["command"],
        "verify_command": cfg["verify_command"],
        "command_timeout_seconds": cfg["command_timeout_seconds"],
        "verification_timeout_seconds": cfg["verification_timeout_seconds"],
        "new_training": cfg["new_training"],
        "production_authority": cfg["production_authority"],
    }
    return base.validate_profile(merged)


def _source_manifest(public_raw, cfg):
    raw = public_raw[policy.SOURCE_FILE]
    try:
        source = json.loads(raw)
    except Exception:
        raise GateError("carrier_source_manifest_invalid") from None
    if source.get("schema_id") != "csi1000.overnight_carrier_source_manifest@1.0":
        raise GateError("carrier_source_manifest_invalid")
    authority = source.get("private_authority", {})
    if authority.get("private_ref") != cfg["private_ref"]:
        raise GateError("carrier_private_ref_mismatch")
    if source.get("external_repository") != "staryocean0/factorlab-overnight-open-lab":
        raise GateError("carrier_external_source_mismatch")
    if source.get("external_ref") != "9905c2f8942ad0a2faf106d42c1b62fd6127e646":
        raise GateError("carrier_external_ref_mismatch")
    if source.get("required_years") != list(range(2015, 2021)):
        raise GateError("carrier_year_boundary")
    if source.get("withheld_years") != [2021, 2022, 2023, 2024, 2025]:
        raise GateError("carrier_year_boundary")
    if source.get("scientific_change") is not False or source.get("new_training") is not False:
        raise GateError("carrier_scope_violation")
    if source.get("production_authority") is not False:
        raise GateError("carrier_scope_violation")
    return source, raw


def _verify_stage_receipt(runner_temp: Path, source_raw: bytes):
    path = runner_temp / policy.STAGE_DIR / "stage_receipt.json"
    try:
        receipt = json.loads(path.read_text())
    except Exception:
        raise GateError("carrier_public_stage_invalid") from None
    expected = hashlib.sha256(source_raw).hexdigest()
    if receipt.get("source_manifest_sha256") != expected:
        raise GateError("carrier_public_stage_manifest_mismatch")


def prepare_inputs(api, root, profile):
    cfg = _read_config()
    try:
        public_raw = policy.verify_local_public_sources(HERE, cfg["public_source_files"], base.SOURCE_BYTES_MAX)
        source, source_raw = _source_manifest(public_raw, cfg)
        runner_temp = Path(os.environ["RUNNER_TEMP"])
        external_stage, rows = policy.verify_stage(runner_temp, source)
        _verify_stage_receipt(runner_temp, source_raw)
    except GateError:
        raise
    except Exception:
        raise GateError("carrier_public_stage_invalid") from None

    work = legacy_prepare_inputs(api, root, profile)
    try:
        policy.install_overlay(work, HERE, public_raw, external_stage, rows, source, base.SOURCE_BYTES_MAX)
    except Exception:
        raise GateError("carrier_overlay_install_failed") from None
    return work


base.PROFILE_NAME = PROFILE_NAME
base.SOURCE_PATHS = SOURCE_PATHS
base.MANIFEST_PATH = MANIFEST_PATH
base.COMMAND = COMMAND
base.VERIFY_COMMAND = VERIFY_COMMAND
base.COMMAND_TIMEOUT_SECONDS = 120
base.VERIFICATION_TIMEOUT_SECONDS = 60
base.load_profile = load_profile
base.prepare_inputs = prepare_inputs


def run():
    base.run()
