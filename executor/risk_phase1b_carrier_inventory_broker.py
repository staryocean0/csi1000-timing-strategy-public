"""Bounded carrier-inventory broker for Risk Tool 2.0 Phase-1b.

This profile may read archive metadata and raw candidate bytes only for identity hashing.
It must never deserialize parquet, inspect prices/returns/labels, fit models, or score 2026.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import sys
import tarfile
import tempfile
import urllib.parse
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_factorlab_broker", HERE / "broker.py")
broker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(broker)

GateError = broker.GateError
PRIVATE_REPO = broker.PRIVATE_REPO
sha = broker.sha
safe_path = broker.safe_path
unpack = broker.unpack
require_context = broker.require_context
collect_result_files = broker.collect_result_files
upload_result = broker.upload_result
require_private_api = broker.require_private_api

PROFILE_NAME = "risk-v2-phase1b-carrier-inventory-v1"
PROFILE_PATH = HERE / "risk_phase1b_carrier_inventory_profile.json"
PROFILE_SCHEMA = "risk_tool_v2_phase1b_carrier_inventory_profile@1.0"
RESULT_SCHEMA = "risk_tool_v2_phase1b_carrier_inventory@1.0"
RECEIPT_SCHEMA = "risk_tool_v2_phase1b_carrier_inventory_runner_receipt@1.0"
TASK_ID = "CSI1000-RISK-V2-PHASE1B-CARRIER-BINDING-20260915"
DATA_RELEASE_TAG = "csi1000-handoff-v1-20260913"
DATA_ASSET_NAME = "csi1000-handoff.tar.gz"
EXPECTED_SUFFIXES = (
    "data/market/5m/000688.SH/2026.parquet",
    "data/market/5m/000852.SH/2026.parquet",
    "bar_receipts.csv",
    "5m_offset_0.parquet",
    "5m_offset_1.parquet",
    "5m_offset_2.parquet",
    "5m_offset_3.parquet",
    "5m_offset_4.parquet",
)
PROFILE_KEYS = {
    "schema_id",
    "task_id",
    "private_ref",
    "data_release_tag",
    "data_asset_name",
    "data_asset_sha256",
    "data_asset_bytes",
    "bundle_member",
    "candidate_suffixes",
    "asset_parts",
    "year_2026_semantic_read",
    "parquet_deserialization",
    "new_training",
    "production_authority",
}
MAX_ARCHIVE_BYTES = 1024**3
MAX_MANIFEST_BYTES = 4 * 1024**2


def _digest(value, max_bytes=MAX_ARCHIVE_BYTES):
    if not isinstance(value, dict) or set(value) != {"bytes", "sha256"}:
        raise GateError("profile_digest_shape_invalid")
    if type(value["bytes"]) is not int or not 1 <= value["bytes"] <= max_bytes:
        raise GateError("profile_file_size_invalid")
    if not isinstance(value["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]):
        raise GateError("profile_digest_invalid")


def validate_profile(value):
    if not isinstance(value, dict) or set(value) != PROFILE_KEYS:
        raise GateError("unknown_profile_field")
    if value.get("schema_id") != PROFILE_SCHEMA or value.get("task_id") != TASK_ID:
        raise GateError("profile_schema_or_task_mismatch")
    if not re.fullmatch(r"[0-9a-f]{40}", value.get("private_ref", "")):
        raise GateError("profile_private_ref_invalid")
    if value.get("data_release_tag") != DATA_RELEASE_TAG or value.get("data_asset_name") != DATA_ASSET_NAME:
        raise GateError("unapproved_data_identity")
    if type(value.get("data_asset_bytes")) is not int or not 1 <= value["data_asset_bytes"] <= MAX_ARCHIVE_BYTES:
        raise GateError("profile_file_size_invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", value.get("data_asset_sha256", "")):
        raise GateError("profile_digest_invalid")
    bundle = value.get("bundle_member")
    if not isinstance(bundle, dict) or set(bundle) != {"name", "bytes", "sha256"} or bundle["name"] != "bundle.tar":
        raise GateError("bundle_identity_invalid")
    _digest({"bytes": bundle["bytes"], "sha256": bundle["sha256"]})
    if tuple(value.get("candidate_suffixes") or ()) != EXPECTED_SUFFIXES:
        raise GateError("candidate_scope_changed")
    if value.get("year_2026_semantic_read") is not False or value.get("parquet_deserialization") is not False:
        raise GateError("semantic_read_not_authorized")
    if value.get("new_training") is not False or value.get("production_authority") is not False:
        raise GateError("scope_not_authorized")
    parts = value.get("asset_parts")
    if not isinstance(parts, list) or not 1 <= len(parts) <= 64:
        raise GateError("invalid_transport_parts")
    for index, part in enumerate(parts):
        if not isinstance(part, dict) or set(part) != {"name", "bytes", "sha256"}:
            raise GateError("invalid_transport_parts")
        if part["name"] != DATA_ASSET_NAME + f".part-{index:03d}":
            raise GateError("unapproved_part_identity")
        _digest({"bytes": part["bytes"], "sha256": part["sha256"]}, max_bytes=32 * 1024**2)
    if sum(part["bytes"] for part in parts) != value["data_asset_bytes"]:
        raise GateError("transport_parts_size_mismatch")
    return value


def load_profile():
    try:
        value = json.loads(PROFILE_PATH.read_text())
    except Exception:
        raise GateError("profile_unreadable") from None
    return validate_profile(value)


def state_path():
    return Path(os.environ["RUNNER_TEMP"]) / "factorlab-carrier-inventory-state.json"


def write_state(state):
    path = state_path()
    if path.is_symlink():
        raise GateError("state_path_is_link")
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(state, indent=2))
    pending.replace(path)


def load_state():
    state = json.loads(state_path().read_text())
    root = Path(state["root"]).resolve()
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    if not root.is_relative_to(runner_temp) or not root.name.startswith("fl-carrier-"):
        raise GateError("invalid_state_root")
    if state.get("run_id") != os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]:
        raise GateError("state_run_identity_mismatch")
    if state.get("profile_sha256") != sha(PROFILE_PATH):
        raise GateError("profile_changed_between_phases")
    if state.get("profile_name") != PROFILE_NAME:
        raise GateError("profile_name_mismatch")
    return state, root


def prepare(profile):
    api = require_private_api()
    if state_path().exists():
        raise GateError("existing_run_state")
    run_id = os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]
    branch = "runs/risk-v2-carrier-inventory/" + run_id
    api.request(
        f"repos/{PRIVATE_REPO}/git/refs",
        {"ref": "refs/heads/" + branch, "sha": profile["private_ref"]},
        method="POST",
    )
    root = Path(tempfile.mkdtemp(prefix="fl-carrier-", dir=os.environ["RUNNER_TEMP"]))
    (root / "results").mkdir()
    work = root / "work"
    inputs = work / "inputs"
    inputs.mkdir(parents=True)

    release = api.request(f"repos/{PRIVATE_REPO}/releases/tags/{profile['data_release_tag']}")
    if release.get("draft") is not False:
        raise GateError("private_data_release_not_published")
    assets = {item["name"]: item for item in release.get("assets") or []}
    compressed = root / profile["data_asset_name"]
    with compressed.open("xb") as combined:
        for index, part in enumerate(profile["asset_parts"]):
            asset = assets.get(part["name"])
            if (
                not asset
                or asset.get("state") != "uploaded"
                or asset.get("size") != part["bytes"]
                or asset.get("digest") != "sha256:" + part["sha256"]
            ):
                raise GateError("remote_asset_identity_failed")
            target = root / f"transport-{index:03d}.bin"
            api.request(
                f"repos/{PRIVATE_REPO}/releases/assets/{asset['id']}",
                binary_path=target,
                max_bytes=part["bytes"],
            )
            if target.stat().st_size != part["bytes"] or sha(target) != part["sha256"]:
                raise GateError("downloaded_part_digest_failed")
            with target.open("rb") as source:
                broker.shutil.copyfileobj(source, combined)
            target.unlink()
    if compressed.stat().st_size != profile["data_asset_bytes"] or sha(compressed) != profile["data_asset_sha256"]:
        raise GateError("downloaded_asset_digest_failed")

    bundle = profile["bundle_member"]
    unpack(
        compressed,
        inputs,
        expected={bundle["name"]: {"bytes": bundle["bytes"], "sha256": bundle["sha256"]}},
    )
    compressed.unlink()
    write_state(
        {
            "run_id": run_id,
            "root": str(root),
            "branch": branch,
            "profile_name": PROFILE_NAME,
            "profile_sha256": sha(PROFILE_PATH),
            "prepare_ready": True,
            "compute_success": False,
        }
    )
    print("Fixed handoff bundle identity verified; carrier inventory prepare complete.")


def _safe_member_name(name):
    path = PurePosixPath(name)
    return bool(path.parts) and not path.is_absolute() and ".." not in path.parts and "\\" not in name


def _role_for(name):
    matched = [suffix for suffix in EXPECTED_SUFFIXES if name == suffix or name.endswith("/" + suffix)]
    if not matched:
        return None, None
    suffix = matched[0]
    if suffix == "data/market/5m/000688.SH/2026.parquet":
        return "canonical_000688_2026_5m", suffix
    if suffix == "data/market/5m/000852.SH/2026.parquet":
        return "canonical_000852_2026_5m", suffix
    if suffix == "bar_receipts.csv":
        return "bar_receipt_metadata", suffix
    return "working_lead_offset", suffix


def _hash_member(stream, size):
    sha256 = hashlib.sha256()
    git_sha1 = hashlib.sha1()
    git_sha1.update(f"blob {size}\0".encode())
    total = 0
    while True:
        block = stream.read(1024 * 1024)
        if not block:
            break
        total += len(block)
        sha256.update(block)
        git_sha1.update(block)
    if total != size:
        raise GateError("candidate_member_size_mismatch")
    return sha256.hexdigest(), git_sha1.hexdigest()


def inventory_bundle(bundle_path, profile):
    if bundle_path.stat().st_size != profile["bundle_member"]["bytes"] or sha(bundle_path) != profile["bundle_member"]["sha256"]:
        raise GateError("bundle_identity_mismatch")
    with tarfile.open(bundle_path, "r:") as archive:
        members = archive.getmembers()
        names = []
        by_name = {}
        total = 0
        for member in members:
            if not member.isfile() or not _safe_member_name(member.name) or member.name in by_name:
                raise GateError("invalid_bundle_member")
            names.append(member.name)
            by_name[member.name] = member
            total += member.size
        if total > MAX_ARCHIVE_BYTES:
            raise GateError("bundle_member_budget_exceeded")
        manifest_member = by_name.get("BUNDLE_MANIFEST.json")
        if manifest_member is None or manifest_member.size > MAX_MANIFEST_BYTES:
            raise GateError("bundle_manifest_missing_or_too_large")
        manifest_stream = archive.extractfile(manifest_member)
        if manifest_stream is None:
            raise GateError("bundle_manifest_unreadable")
        manifest_raw = manifest_stream.read(MAX_MANIFEST_BYTES + 1)
        if len(manifest_raw) != manifest_member.size:
            raise GateError("bundle_manifest_size_mismatch")
        try:
            manifest = json.loads(manifest_raw)
        except Exception:
            raise GateError("bundle_manifest_invalid_json") from None
        if not isinstance(manifest, dict) or manifest.get("schema") != "csi1000_handoff_bundle@1":
            raise GateError("bundle_manifest_schema_mismatch")
        expected = manifest.get("files")
        if not isinstance(expected, dict) or set(names) != set(expected) | {"BUNDLE_MANIFEST.json"}:
            raise GateError("bundle_manifest_member_set_mismatch")

        candidates = []
        for name in sorted(expected):
            role, suffix = _role_for(name)
            if role is None:
                continue
            meta = expected[name]
            if not isinstance(meta, dict) or set(meta) != {"bytes", "sha256"}:
                raise GateError("candidate_manifest_shape_invalid")
            member = by_name[name]
            if member.size != meta["bytes"] or not re.fullmatch(r"[0-9a-f]{64}", str(meta["sha256"])):
                raise GateError("candidate_manifest_identity_invalid")
            stream = archive.extractfile(member)
            if stream is None:
                raise GateError("candidate_member_unreadable")
            actual_sha256, git_blob_sha1 = _hash_member(stream, member.size)
            if actual_sha256 != meta["sha256"]:
                raise GateError("candidate_sha256_mismatch")
            candidates.append(
                {
                    "role": role,
                    "matched_suffix": suffix,
                    "archive_path": name,
                    "bytes": member.size,
                    "sha256": actual_sha256,
                    "git_blob_sha1": git_blob_sha1,
                }
            )

    counts = {
        role: sum(1 for row in candidates if row["role"] == role)
        for role in ("canonical_000688_2026_5m", "canonical_000852_2026_5m", "bar_receipt_metadata", "working_lead_offset")
    }
    exact_pair = counts["canonical_000688_2026_5m"] == 1 and counts["canonical_000852_2026_5m"] == 1
    return {
        "schema_id": RESULT_SCHEMA,
        "task_id": TASK_ID,
        "status": "BYTE_CANDIDATES_IDENTIFIED" if exact_pair else "INVENTORY_COMPLETE_BINDING_UNRESOLVED",
        "source_release": {
            "tag": profile["data_release_tag"],
            "asset": profile["data_asset_name"],
            "asset_sha256": profile["data_asset_sha256"],
            "asset_bytes": profile["data_asset_bytes"],
        },
        "bundle": {
            "bytes": profile["bundle_member"]["bytes"],
            "sha256": profile["bundle_member"]["sha256"],
            "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        },
        "candidate_counts": counts,
        "candidates": candidates,
        "controls": {
            "year_2026_semantic_read": False,
            "parquet_deserialization": False,
            "price_return_label_columns_read": False,
            "model_fit": False,
            "confirmatory_scoring": False,
            "new_training": False,
            "production_authority": False,
        },
    }


def compute(profile):
    if os.environ.get("FACTORLAB_PRIVATE_TOKEN"):
        raise GateError("private_token_must_not_reach_compute_step")
    state, root = load_state()
    result = inventory_bundle(root / "work" / "inputs" / "bundle.tar", profile)
    output = root / "results" / "risk_phase1b_carrier_inventory.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    collect_result_files(root / "results")
    state.update(compute_success=True, inventory_status=result["status"])
    write_state(state)
    print("Carrier byte inventory completed without parquet deserialization; result remains private.")


def cleanup():
    if os.environ.get("FACTORLAB_PRIVATE_TOKEN"):
        raise GateError("cleanup_step_must_not_have_private_token")
    state, _ = load_state()
    state["cleanup_complete"] = True
    write_state(state)
    print("Carrier inventory cleanup complete; no compute container or credential remains active.")


def publish(profile):
    state, root = load_state()
    if not state.get("cleanup_complete"):
        raise GateError("cleanup_must_complete_before_private_publish")
    api = require_private_api()
    results = root / "results"
    files = collect_result_files(results)
    archive_path = root / "carrier-inventory-results.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for name in files:
            archive.add(results / name, arcname=name, recursive=False)
    if archive_path.stat().st_size > 16 * 1024 * 1024:
        raise GateError("private_result_archive_too_large")
    tag = "public-carrier-inventory-run-" + state["run_id"]
    release = api.request(
        f"repos/{PRIVATE_REPO}/releases",
        {
            "tag_name": tag,
            "target_commitish": profile["private_ref"],
            "draft": True,
            "prerelease": True,
            "name": "Risk Phase-1b carrier inventory " + state["run_id"],
            "body": "Non-semantic byte-identity inventory; no 2026 parquet deserialization or scoring.",
        },
        method="POST",
    )
    uploaded = upload_result(api, release["id"], archive_path)
    expected_digest = "sha256:" + sha(archive_path)
    release = api.request(f"repos/{PRIVATE_REPO}/releases/{release['id']}")
    if (
        len(release.get("assets") or []) != 1
        or uploaded.get("digest") != expected_digest
        or release["assets"][0].get("digest") != expected_digest
        or release["assets"][0].get("size") != archive_path.stat().st_size
        or release["assets"][0].get("state") != "uploaded"
    ):
        raise GateError("private_writeback_digest_failed")
    api.request(f"repos/{PRIVATE_REPO}/releases/{release['id']}", {"draft": False}, method="PATCH")

    receipt = {
        "schema_id": RECEIPT_SCHEMA,
        "status": "passed" if state.get("compute_success") else "failed",
        "delivery_status": "archive_uploaded_and_verified",
        "public_run_id": state["run_id"],
        "public_source_sha": os.environ["GITHUB_SHA"],
        "private_source_ref": profile["private_ref"],
        "profile": PROFILE_NAME,
        "profile_sha256": sha(PROFILE_PATH),
        "inventory_status": state.get("inventory_status"),
        "files": files,
        "archive": {
            "release_id": release["id"],
            "tag": tag,
            "sha256": sha(archive_path),
            "bytes": archive_path.stat().st_size,
        },
        "year_2026_semantic_read": False,
        "parquet_deserialization": False,
        "new_training": False,
        "production_authority": False,
    }
    payload = (json.dumps(receipt, indent=2) + "\n").encode()
    target = f"repos/{PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}.json"
    api.request(
        target,
        {
            "message": "Record Risk Phase-1b carrier inventory receipt [skip ci]",
            "branch": state["branch"],
            "content": base64.b64encode(payload).decode(),
        },
        method="PUT",
    )
    returned = api.request(target + "?ref=" + urllib.parse.quote(state["branch"], safe=""))
    if base64.b64decode(returned["content"]) != payload:
        raise GateError("private_receipt_readback_failed")
    print("Private carrier inventory archive and receipt verified for public run " + state["run_id"] + ".")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context(os.environ)
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_profile")
    os.umask(0o077)
    profile = load_profile()
    if args.phase == "prepare":
        prepare(profile)
    elif args.phase == "compute":
        compute(profile)
    elif args.phase == "cleanup":
        cleanup()
    else:
        publish(profile)


def run():
    try:
        main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("Execution failed; no private diagnostic content was published.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run()
