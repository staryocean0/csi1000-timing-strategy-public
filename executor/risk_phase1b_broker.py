"""Fixed broker for Risk Tool v2 Phase-1b ordering/calibration study.

Only the authoritative Phase-1 result release is admitted. Compute receives the
stored parent state/cohort rows plus the frozen public Phase-1b sources, no
GitHub credential, no network, no market-source data and no 2026 data.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import re
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_research_broker", HERE / "research_broker.py")
rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rb)
GateError = rb.GateError

PROFILE_NAME = "risk-v2-phase1b-ordering-calibration-v1"
PRIVATE_REF = "46e818ef51618e225be2d79a516424ff16231a1d"
RELEASE_ID = 388319643
ASSET_ID = 563182909
ASSET_NAME = "results.tar.gz"
ASSET_BYTES = 8115479
ASSET_SHA256 = "c201cd1b2ab18442ca49d60209b181557335595efdb6a4da5d78549b5c32b21b"

PUBLIC_SOURCES = {
    "risk_phase1b_run.py": {
        "repo_path": "executor/risk_phase1b_run.py",
        "git_blob_sha1": "243b43f5f8201efb9a420672af5a8c0916821d66",
        "target": "phase1b/run.py",
    },
    "risk_phase1b_verify.py": {
        "repo_path": "executor/risk_phase1b_verify.py",
        "git_blob_sha1": "9c587eafff0110730de3e6d288b9739c3e16436d",
        "target": "phase1b/verify.py",
    },
    "protocol": {
        "repo_path": "docs/research/RISK_TOOL_V2_PHASE1B_ORDERING_CALIBRATION_PROTOCOL_20260914.json",
        "git_blob_sha1": "78528896dbe424af9396e478f114d66b68e7f786",
        "target": "phase1b/PROTOCOL.json",
    },
}

INPUTS = {
    "study/state_rows.parquet": {
        "bytes": 8159191,
        "sha256": "e74e497ddf075f7b1519ab3afd96dddfeafbeafce7e4bab86a77d9037e23e30d",
        "target": "state_rows.parquet",
    },
    "study/cohort_rows.parquet": {
        "bytes": 776877,
        "sha256": "53276c7f25861b8a064288f8662c1a391c0c5af75758376df60e98ab180c4234",
        "target": "cohort_rows.parquet",
    },
}

PROFILE = {
    "private_ref": PRIVATE_REF,
    "manifest_sha256": INPUTS["study/cohort_rows.parquet"]["sha256"],
    "command": ["phase1b/run.py", "--inputs", "/work/inputs", "--out", "/results/study"],
    "verify_command": ["phase1b/verify.py", "--results", "/results/study"],
    "command_timeout_seconds": 900,
    "verification_timeout_seconds": 600,
    "new_training": False,
    "production_authority": False,
}


def git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def require_context() -> None:
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
        or env.get("GITHUB_EVENT_NAME") != "push"
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
    ):
        raise GateError("not_approved_phase1b_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")) or not re.fullmatch(
        r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "")
    ):
        raise GateError("invalid_run_identity")


def stage_public_sources(work: Path) -> None:
    repo_root = HERE.parent
    for meta in PUBLIC_SOURCES.values():
        source = repo_root / meta["repo_path"]
        if source.is_symlink() or not source.is_file() or source.stat().st_size <= 0 or source.stat().st_size > 200000:
            raise GateError("phase1b_public_source_identity_failed")
        raw = source.read_bytes()
        if git_blob_sha1(raw) != meta["git_blob_sha1"]:
            raise GateError("phase1b_public_source_digest_failed")
        target = work / meta["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        if git_blob_sha1(target.read_bytes()) != meta["git_blob_sha1"]:
            raise GateError("phase1b_public_source_copy_failed")


def extract_parent_inputs(archive: Path, work: Path) -> None:
    target_root = work / "inputs"
    target_root.mkdir()
    seen = set()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            name = str(PurePosixPath(member.name))
            if name not in INPUTS:
                continue
            expected = INPUTS[name]
            if not member.isfile() or name in seen or member.size != expected["bytes"]:
                raise GateError("phase1b_parent_member_identity_failed")
            stream = tar.extractfile(member)
            if stream is None:
                raise GateError("phase1b_parent_member_identity_failed")
            target = target_root / expected["target"]
            with target.open("xb") as out:
                shutil.copyfileobj(stream, out)
            if rb.sha(target) != expected["sha256"]:
                raise GateError("phase1b_parent_member_digest_failed")
            seen.add(name)
    if seen != set(INPUTS):
        raise GateError("phase1b_parent_input_set_incomplete")


def prepare_inputs(api, root: Path, profile: dict):
    work = root / "work"
    work.mkdir()
    stage_public_sources(work)

    release = api.request(f"repos/{rb.PRIVATE_REPO}/releases/{RELEASE_ID}")
    if release.get("id") != RELEASE_ID or release.get("draft") is not False:
        raise GateError("phase1b_parent_release_identity_failed")
    asset = next((row for row in release.get("assets") or [] if row.get("id") == ASSET_ID), None)
    if (
        not asset
        or asset.get("name") != ASSET_NAME
        or asset.get("state") != "uploaded"
        or asset.get("size") != ASSET_BYTES
        or asset.get("digest") != "sha256:" + ASSET_SHA256
    ):
        raise GateError("phase1b_parent_asset_identity_failed")

    archive = root / ASSET_NAME
    api.request(
        f"repos/{rb.PRIVATE_REPO}/releases/assets/{ASSET_ID}",
        binary_path=archive,
        max_bytes=ASSET_BYTES,
    )
    if archive.stat().st_size != ASSET_BYTES or rb.sha(archive) != ASSET_SHA256:
        raise GateError("phase1b_parent_asset_download_failed")
    extract_parent_inputs(archive, work)
    return work


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_phase1b_profile")
    rb.prepare_inputs = prepare_inputs
    if args.phase == "prepare":
        rb.prepare(PROFILE_NAME, PROFILE)
    elif args.phase == "compute":
        rb.compute()
    elif args.phase == "cleanup":
        rb.cleanup()
    else:
        rb.publish(PROFILE)


def run() -> None:
    try:
        main()
    except GateError as exc:
        print("Execution stopped: " + str(exc), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("Execution failed; no private Phase-1b content was exposed publicly.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run()
