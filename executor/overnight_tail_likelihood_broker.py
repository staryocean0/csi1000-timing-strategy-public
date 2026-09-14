"""Bounded broker for the frozen Overnight continuous tail-likelihood DEV identity.

This is the only training-enabled profile in this module. It reads one already-verified
private materialization Release, exposes only 2015-2020 factor/driver carriers, and reuses
the reviewed credential-free/network-none research compute and private result publisher.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import re
import shutil
import tarfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
_spec = importlib.util.spec_from_file_location("_tail_base_broker", HERE / "research_broker.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("research broker unavailable")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

GateError = base.GateError
PROFILE_NAME = "overnight-continuous-tail-likelihood-dev-v1"
PROFILE_SCHEMA = "factorlab.public_overnight_tail_likelihood_training_profile@1.0"
PROFILE_PATH = HERE / "overnight_tail_likelihood_profile.json"
PROTOCOL_SOURCE = ROOT / "docs/research/OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_PREREG_20260914.json"
PRIVATE_REF = "cbe97535403b17cf8c4311bcc6567328b726ce67"
MATERIALIZATION_RUN_ID = "34837972995-1"
MATERIALIZATION_PROFILE = "overnight-carrier-materialization-v1"
MATERIALIZATION_PUBLIC_SHA = "993040be5a4e3274491f1519523d2b0be949759c"
COMMAND = [
    "overnight_tail_likelihood/run_study.py",
    "--carrier-root", "/work/carrier_snapshot/carrier",
    "--protocol", "/work/overnight_tail_likelihood/protocol.json",
    "--out", "/results/study",
]
VERIFY_COMMAND = [
    "overnight_tail_likelihood/verify_study.py",
    "--carrier-root", "/work/carrier_snapshot/carrier",
    "--protocol", "/work/overnight_tail_likelihood/protocol.json",
    "--results", "/results/study",
]
PROFILE_KEYS = {
    "schema_id", "profile_name", "private_ref", "carrier_source",
    "public_source_files", "command", "verify_command",
    "command_timeout_seconds", "verification_timeout_seconds",
    "new_training", "production_authority",
}
CARRIER_KEYS = {
    "receipt_ref", "receipt_path", "receipt_git_blob_sha1",
    "release_tag", "asset_name", "asset_bytes", "asset_sha256",
}
PUBLIC_KEYS = {
    "overnight_tail_likelihood_dev.py",
    "verify_overnight_tail_likelihood_dev.py",
    "docs/research/OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_PREREG_20260914.json",
}
PUBLIC_TARGETS = {
    "overnight_tail_likelihood_dev.py": "overnight_tail_likelihood/run_study.py",
    "verify_overnight_tail_likelihood_dev.py": "overnight_tail_likelihood/verify_study.py",
    "docs/research/OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_PREREG_20260914.json": "overnight_tail_likelihood/protocol.json",
}
REQUIRED_CARRIER_PATHS = {
    "study/carrier/data/runtime_text_2015_2025/manifest.json",
    "study/carrier/data/driver_runtime_text_2015_2020/manifest.json",
    *{f"study/carrier/data/runtime_text_2015_2025/factor_panel_{year}.csv" for year in range(2015, 2021)},
    *{f"study/carrier/data/driver_runtime_text_2015_2020/driver_external_{year}.csv" for year in range(2015, 2021)},
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def _hex(value, size):
    return isinstance(value, str) and bool(re.fullmatch(rf"[0-9a-f]{{{size}}}", value))


def _read_config():
    try:
        value = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except Exception:
        raise GateError("profile_catalog_unavailable") from None
    if not isinstance(value, dict) or set(value) != PROFILE_KEYS:
        raise GateError("profile_catalog_invalid")
    if value.get("schema_id") != PROFILE_SCHEMA or value.get("profile_name") != PROFILE_NAME:
        raise GateError("profile_catalog_invalid")
    if value.get("private_ref") != PRIVATE_REF or not _hex(value.get("private_ref"), 40):
        raise GateError("profile_not_immutable")
    carrier = value.get("carrier_source")
    if not isinstance(carrier, dict) or set(carrier) != CARRIER_KEYS:
        raise GateError("carrier_source_invalid")
    if carrier.get("receipt_ref") != f"runs/public-research/{MATERIALIZATION_RUN_ID}":
        raise GateError("carrier_source_invalid")
    if carrier.get("receipt_path") != f"research/public-runs/{MATERIALIZATION_RUN_ID}.json":
        raise GateError("carrier_source_invalid")
    if not _hex(carrier.get("receipt_git_blob_sha1"), 40):
        raise GateError("carrier_source_invalid")
    if carrier.get("release_tag") != f"public-research-run-{MATERIALIZATION_RUN_ID}":
        raise GateError("carrier_source_invalid")
    if carrier.get("asset_name") != "results.tar.gz" or carrier.get("asset_bytes") != 218006:
        raise GateError("carrier_source_invalid")
    if not _hex(carrier.get("asset_sha256"), 64):
        raise GateError("carrier_source_invalid")
    public = value.get("public_source_files")
    if not isinstance(public, dict) or set(public) != PUBLIC_KEYS:
        raise GateError("public_source_set_invalid")
    for name, meta in public.items():
        if not isinstance(meta, dict) or "git_blob_sha1" not in meta or not _hex(meta["git_blob_sha1"], 40):
            raise GateError("public_source_not_immutable")
        if set(meta) not in ({"git_blob_sha1"}, {"git_blob_sha1", "sha256"}):
            raise GateError("public_source_invalid")
        if "sha256" in meta and not _hex(meta["sha256"], 64):
            raise GateError("public_source_invalid")
    if value.get("command") != COMMAND or value.get("verify_command") != VERIFY_COMMAND:
        raise GateError("unapproved_command")
    if value.get("command_timeout_seconds") != 300 or value.get("verification_timeout_seconds") != 300:
        raise GateError("profile_timeout_changed")
    if value.get("new_training") is not True or value.get("production_authority") is not False:
        raise GateError("training_scope_invalid")
    return value


def load_profile(name):
    if name != PROFILE_NAME:
        raise GateError("unknown_profile")
    cfg = _read_config()
    protocol_sha = cfg["public_source_files"][str(PROTOCOL_SOURCE.relative_to(ROOT)).replace("\\", "/")]["sha256"]
    return {
        "private_ref": cfg["private_ref"],
        "manifest_sha256": protocol_sha,
        "command": cfg["command"],
        "verify_command": cfg["verify_command"],
        "command_timeout_seconds": cfg["command_timeout_seconds"],
        "verification_timeout_seconds": cfg["verification_timeout_seconds"],
        "new_training": True,
        "production_authority": False,
    }


def _fetch_receipt(api, cfg):
    carrier = cfg["carrier_source"]
    quoted = base.urllib.parse.quote(carrier["receipt_path"], safe="/")
    ref = base.urllib.parse.quote(carrier["receipt_ref"], safe="")
    meta = api.request(f"repos/{base.PRIVATE_REPO}/contents/{quoted}?ref={ref}")
    if meta.get("type") != "file" or meta.get("encoding") != "base64":
        raise GateError("carrier_receipt_identity_failed")
    try:
        raw = base64.b64decode(meta["content"])
    except Exception:
        raise GateError("carrier_receipt_identity_failed") from None
    if meta.get("sha") != carrier["receipt_git_blob_sha1"] or git_blob_sha1(raw) != carrier["receipt_git_blob_sha1"]:
        raise GateError("carrier_receipt_digest_mismatch")
    try:
        receipt = json.loads(raw)
    except Exception:
        raise GateError("carrier_receipt_invalid") from None
    if not isinstance(receipt, dict):
        raise GateError("carrier_receipt_invalid")
    required = {
        "schema_id": "factorlab.public_research_runner_receipt@1.0",
        "status": "passed",
        "delivery_status": "archive_uploaded_and_verified",
        "public_run_id": MATERIALIZATION_RUN_ID,
        "public_source_sha": MATERIALIZATION_PUBLIC_SHA,
        "private_source_ref": PRIVATE_REF,
        "profile": MATERIALIZATION_PROFILE,
        "new_training": False,
        "production_authority": False,
    }
    for key, expected in required.items():
        if receipt.get(key) != expected:
            raise GateError("carrier_receipt_invalid")
    archive = receipt.get("archive")
    if not isinstance(archive, dict):
        raise GateError("carrier_receipt_invalid")
    if archive.get("tag") != carrier["release_tag"] or archive.get("bytes") != carrier["asset_bytes"] or archive.get("sha256") != carrier["asset_sha256"]:
        raise GateError("carrier_receipt_archive_drift")
    files = receipt.get("files")
    if not isinstance(files, dict) or not REQUIRED_CARRIER_PATHS.issubset(files):
        raise GateError("carrier_receipt_file_set")
    for path in REQUIRED_CARRIER_PATHS:
        item = files[path]
        if not isinstance(item, dict) or set(item) != {"bytes", "sha256"}:
            raise GateError("carrier_receipt_file_metadata")
        if type(item["bytes"]) is not int or item["bytes"] <= 0 or not _hex(item["sha256"], 64):
            raise GateError("carrier_receipt_file_metadata")
    if any(re.search(r"_(2021|2022|2023|2024|2025)\.csv$", path) for path in files):
        raise GateError("blackbox_row_file_exposed")
    return receipt


def _download_release(api, root, cfg):
    carrier = cfg["carrier_source"]
    release = api.request(f"repos/{base.PRIVATE_REPO}/releases/tags/{carrier['release_tag']}")
    if release.get("draft") is not False:
        raise GateError("carrier_release_not_published")
    matches = [asset for asset in (release.get("assets") or []) if asset.get("name") == carrier["asset_name"]]
    if len(matches) != 1:
        raise GateError("carrier_asset_identity_failed")
    asset = matches[0]
    if asset.get("state") != "uploaded" or asset.get("size") != carrier["asset_bytes"] or asset.get("digest") != "sha256:" + carrier["asset_sha256"]:
        raise GateError("carrier_asset_identity_failed")
    target = root / "carrier-source-results.tar.gz"
    api.request(f"repos/{base.PRIVATE_REPO}/releases/assets/{asset['id']}", binary_path=target, max_bytes=carrier["asset_bytes"])
    if target.stat().st_size != carrier["asset_bytes"] or base.sha(target) != carrier["asset_sha256"]:
        raise GateError("carrier_asset_digest_mismatch")
    return target


def _safe_archive_name(name: str) -> str:
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or ".." in path.parts or "\\" in name or str(path) != name:
        raise GateError("carrier_archive_path_invalid")
    return name


def _extract_carrier(archive_path: Path, work: Path, receipt: dict):
    destination = work / "carrier_snapshot" / "carrier"
    destination.mkdir(parents=True)
    files = receipt["files"]
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        names = [_safe_archive_name(member.name) for member in members]
        if len(names) != len(set(names)):
            raise GateError("carrier_archive_duplicate_member")
        if any(not (member.isfile() or member.isdir()) for member in members):
            raise GateError("carrier_archive_special_member")
        by_name = {member.name: member for member in members}
        if not REQUIRED_CARRIER_PATHS.issubset(by_name):
            raise GateError("carrier_archive_missing_member")
        for source_name in sorted(REQUIRED_CARRIER_PATHS):
            member = by_name[source_name]
            expected = files[source_name]
            if not member.isfile() or member.size != expected["bytes"]:
                raise GateError("carrier_archive_member_identity")
            stream = archive.extractfile(member)
            if stream is None:
                raise GateError("carrier_archive_member_unreadable")
            raw = stream.read(expected["bytes"] + 1)
            if len(raw) != expected["bytes"] or sha256_bytes(raw) != expected["sha256"]:
                raise GateError("carrier_archive_member_digest")
            rel = PurePosixPath(source_name).relative_to("study/carrier")
            target = destination.joinpath(*rel.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(raw)
    return destination


def _source_path(name: str) -> Path:
    if name.startswith("docs/"):
        return ROOT.joinpath(*PurePosixPath(name).parts)
    return HERE / name


def _install_public_sources(work: Path, cfg):
    for name, expected in cfg["public_source_files"].items():
        source = _source_path(name)
        if not source.is_file() or source.is_symlink():
            raise GateError("public_source_identity_failed")
        raw = source.read_bytes()
        if git_blob_sha1(raw) != expected["git_blob_sha1"]:
            raise GateError("public_source_digest_mismatch")
        if "sha256" in expected and sha256_bytes(raw) != expected["sha256"]:
            raise GateError("public_source_digest_mismatch")
        target = work / PUBLIC_TARGETS[name]
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(raw)


def prepare_inputs(api, root, profile):
    cfg = _read_config()
    receipt = _fetch_receipt(api, cfg)
    archive = _download_release(api, root, cfg)
    work = root / "work"
    work.mkdir()
    _extract_carrier(archive, work, receipt)
    archive.unlink()
    _install_public_sources(work, cfg)
    return work


_original_prepare = base.prepare
_original_load_state = base.load_state


def prepare(profile_name, profile):
    _original_prepare(profile_name, profile)
    state, _ = _original_load_state()
    state["tail_training_profile_sha256"] = base.sha(PROFILE_PATH)
    state["tail_training_protocol_sha256"] = profile["manifest_sha256"]
    base.write_state(state)


def load_state():
    state, root = _original_load_state()
    if state.get("tail_training_profile_sha256") != base.sha(PROFILE_PATH):
        raise GateError("tail_training_profile_changed_between_phases")
    cfg = _read_config()
    protocol_sha = cfg["public_source_files"]["docs/research/OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_PREREG_20260914.json"]["sha256"]
    if state.get("tail_training_protocol_sha256") != protocol_sha:
        raise GateError("tail_training_protocol_changed_between_phases")
    return state, root


base.PROFILE_NAME = PROFILE_NAME
base.COMMAND = COMMAND
base.VERIFY_COMMAND = VERIFY_COMMAND
base.COMMAND_TIMEOUT_SECONDS = 300
base.VERIFICATION_TIMEOUT_SECONDS = 300
base.load_profile = load_profile
base.prepare_inputs = prepare_inputs
base.prepare = prepare
base.load_state = load_state


def run():
    base.run()


if __name__ == "__main__":
    run()
