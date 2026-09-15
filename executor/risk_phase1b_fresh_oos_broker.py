"""Controlled one-time fresh-OOS broker for Risk Tool v2 Phase-1b."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
from pathlib import Path

import research_broker as rb
import risk_phase1b_carrier_inventory_core_v1 as carrier_core
import risk_phase1b_fresh_oos_failure_mirror as failure_mirror

GateError = rb.GateError

PROFILE_NAME = "risk-v2-phase1b-fresh-oos-v1"
TASK_ID = "CSI1000-RISK-V2-2026-FRESH-OOS-V1-20260914"
PREREG_SHA256 = "c05bdf09c54626861f2a86abbcadb514fa90918320e2ab4be45e1e3217b7c9d7"
PRIVATE_REF = "c45c0f991d9d6872bf312bbf0e1f220b98958d75"

CARRIER_MEMBER = "data/index/5m_offset_0.parquet"
CARRIER_BYTES = 3615731
CARRIER_SHA256 = "211448c914b547232bc536da7df94dc5ae279b8265a5cafe58409238485217d7"

MODEL_RELEASE = {
    "release_id": 388319643,
    "asset_id": 563182909,
    "asset_name": "results.tar.gz",
    "asset_bytes": 8115479,
    "asset_sha256": "c201cd1b2ab18442ca49d60209b181557335595efdb6a4da5d78549b5c32b21b",
    "member": "study/MODEL_FREEZE.json",
    "member_bytes": 15921,
    "member_sha256": "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551",
}
CALIBRATION_RELEASE = {
    "release_id": 388398729,
    "asset_id": 563403877,
    "asset_name": "results.tar.gz",
    "asset_bytes": 8090245,
    "asset_sha256": "197c15aaa725a20cbfd7b07ff639e59c400b38eaa49c0141fa6fca9d035dd3fc",
    "member": "study/CALIBRATION_FREEZE.json",
    "member_bytes": 2068,
    "member_sha256": "74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909",
}

PROFILE = {
    "private_ref": PRIVATE_REF,
    "manifest_sha256": PREREG_SHA256,
    "command": [
        "fresh_oos/risk_phase1b_fresh_oos_eval.py",
        "--inputs",
        "/work/inputs",
        "--out",
        "/results/study",
    ],
    "verify_command": [
        "fresh_oos/risk_phase1b_fresh_oos_verifier.py",
        "--inputs",
        "/work/inputs",
        "--results",
        "/results/study",
    ],
    "command_timeout_seconds": 1800,
    "verification_timeout_seconds": 1800,
    "new_training": False,
    "production_authority": False,
}

rb.COMPUTE_HOST_TIMEOUT_SECONDS = 1860
rb.VALIDATE_HOST_TIMEOUT_SECONDS = 1860


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require_context() -> None:
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
        or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
    ):
        raise GateError("not_approved_fresh_oos_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")):
        raise GateError("invalid_run_identity")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "")):
        raise GateError("invalid_run_identity")


def _download_release_member(api, root: Path, spec: dict, destination: Path) -> None:
    release = api.request(f"repos/{rb.PRIVATE_REPO}/releases/{spec['release_id']}")
    if release.get("draft") is not False or release.get("prerelease") is not True:
        raise GateError("frozen_parent_release_not_published")
    asset = next((row for row in release.get("assets") or [] if row.get("id") == spec["asset_id"]), None)
    if (
        not asset
        or asset.get("name") != spec["asset_name"]
        or asset.get("state") != "uploaded"
        or asset.get("size") != spec["asset_bytes"]
        or asset.get("digest") != "sha256:" + spec["asset_sha256"]
    ):
        raise GateError("frozen_parent_release_identity_failed")
    archive = root / f"parent-{spec['release_id']}.tar.gz"
    api.request(
        f"repos/{rb.PRIVATE_REPO}/releases/assets/{spec['asset_id']}",
        binary_path=archive,
        max_bytes=spec["asset_bytes"],
    )
    if archive.stat().st_size != spec["asset_bytes"] or sha256_file(archive) != spec["asset_sha256"]:
        raise GateError("frozen_parent_download_failed")
    with tarfile.open(archive, "r:gz") as tar:
        try:
            member = tar.getmember(spec["member"])
        except KeyError:
            raise GateError("frozen_parent_member_missing") from None
        if not member.isfile() or member.size != spec["member_bytes"]:
            raise GateError("frozen_parent_member_identity_failed")
        stream = tar.extractfile(member)
        if stream is None:
            raise GateError("frozen_parent_member_unreadable")
        with destination.open("xb") as output:
            shutil.copyfileobj(stream, output)
    archive.unlink()
    if destination.stat().st_size != spec["member_bytes"] or sha256_file(destination) != spec["member_sha256"]:
        raise GateError("frozen_parent_member_digest_failed")


def _stage_carrier(api, root: Path, inputs: Path) -> dict:
    profile = carrier_core.load_profile()
    release = api.request(f"repos/{rb.PRIVATE_REPO}/releases/tags/{profile['data_release_tag']}")
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
                raise GateError("carrier_transport_asset_identity_failed")
            target = root / f"carrier-part-{index:03d}.bin"
            api.request(
                f"repos/{rb.PRIVATE_REPO}/releases/assets/{asset['id']}",
                binary_path=target,
                max_bytes=part["bytes"],
            )
            if target.stat().st_size != part["bytes"] or sha256_file(target) != part["sha256"]:
                raise GateError("carrier_transport_part_digest_failed")
            with target.open("rb") as source:
                shutil.copyfileobj(source, combined)
            target.unlink()
    if compressed.stat().st_size != profile["data_asset_bytes"] or sha256_file(compressed) != profile["data_asset_sha256"]:
        raise GateError("carrier_transport_archive_digest_failed")

    unpacked = root / "handoff-unpacked"
    unpacked.mkdir()
    bundle = profile["bundle_member"]
    carrier_core.unpack(
        compressed,
        unpacked,
        expected={bundle["name"]: {"bytes": bundle["bytes"], "sha256": bundle["sha256"]}},
    )
    compressed.unlink()

    bundle_path = unpacked / bundle["name"]
    matching = []
    with tarfile.open(bundle_path, "r:") as tar:
        for member in tar.getmembers():
            if member.isfile() and (member.name == CARRIER_MEMBER or member.name.endswith("/" + CARRIER_MEMBER)):
                matching.append(member)
        if len(matching) != 1:
            raise GateError("accepted_carrier_member_not_unique")
        member = matching[0]
        if member.size != CARRIER_BYTES:
            raise GateError("accepted_carrier_member_size_mismatch")
        stream = tar.extractfile(member)
        if stream is None:
            raise GateError("accepted_carrier_member_unreadable")
        market = inputs / "market"
        market.mkdir()
        destination = market / "5m_offset_0.parquet"
        with destination.open("xb") as output:
            shutil.copyfileobj(stream, output)
    if destination.stat().st_size != CARRIER_BYTES or sha256_file(destination) != CARRIER_SHA256:
        raise GateError("accepted_carrier_member_digest_failed")
    bundle_path.unlink()

    return {
        "source_release_tag": profile["data_release_tag"],
        "source_asset": profile["data_asset_name"],
        "source_asset_sha256": profile["data_asset_sha256"],
        "source_bundle_sha256": bundle["sha256"],
    }


def prepare_inputs(api, root: Path, profile: dict):
    work = root / "work"
    work.mkdir()
    scripts = work / "fresh_oos"
    scripts.mkdir()
    for name in ("risk_phase1b_fresh_oos_eval.py", "risk_phase1b_fresh_oos_verifier.py"):
        source = Path(__file__).resolve().parent / name
        if not source.is_file() or source.is_symlink():
            raise GateError("fresh_oos_public_source_missing")
        shutil.copy2(source, scripts / name)

    inputs = work / "inputs"
    inputs.mkdir()
    _download_release_member(api, root, MODEL_RELEASE, inputs / "MODEL_FREEZE.json")
    _download_release_member(api, root, CALIBRATION_RELEASE, inputs / "CALIBRATION_FREEZE.json")
    carrier_source = _stage_carrier(api, root, inputs)

    identity = {
        "schema_id": "risk_tool_v2_phase1b_accepted_carrier@1.0",
        "task_id": TASK_ID,
        "accepted_on": "2026-09-15",
        "user_authorized_same_source_and_valid": True,
        "provenance_recheck_required": False,
        "year_2026_semantic_read_before_compute": False,
        "prereg": {
            "path": "docs/research/RISK_TOOL_V2_2026_FRESH_OOS_PREREG_20260914.json",
            "sha256": PREREG_SHA256,
            "scientific_contract_changed": False,
        },
        "carrier": {
            "path": CARRIER_MEMBER,
            "bytes": CARRIER_BYTES,
            "sha256": CARRIER_SHA256,
            **carrier_source,
        },
        "frozen_inputs": {
            "model_freeze_sha256": MODEL_RELEASE["member_sha256"],
            "calibration_freeze_sha256": CALIBRATION_RELEASE["member_sha256"],
        },
        "fresh_oos_cutoff_trading_day_inclusive": "2026-09-11",
        "new_training": False,
        "production_authority": False,
    }
    (inputs / "DATA_IDENTITY.json").write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n")
    return work


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_fresh_oos_profile")
    os.umask(0o077)
    rb.prepare_inputs = prepare_inputs
    if args.phase == "prepare":
        rb.prepare(PROFILE_NAME, PROFILE)
    elif args.phase == "compute":
        rb.compute()
    elif args.phase == "cleanup":
        rb.cleanup()
    else:
        # The failure mirror exports only a sanitized exception code and is a
        # no-op after validated success. Generic publish then archives the full
        # bounded evidence and records the ordinary runner receipt.
        failure_mirror.main()
        rb.publish(PROFILE)


def run() -> None:
    try:
        main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Execution failed; no private fresh-OOS content was exposed publicly.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
