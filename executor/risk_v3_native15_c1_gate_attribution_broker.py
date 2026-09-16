"""Bounded broker for read-only Native-15m C1 gate attribution."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import urllib.parse
from pathlib import Path, PurePosixPath

import research_broker as rb

GateError = rb.GateError
PROFILE_NAME = "risk-v3-native15-c1-gate-attribution-v1"
TASK_ID = "CSI1000-RISK-V3-NATIVE15-C1-GATE-ATTRIBUTION-V1-20260916"
PREREG_SHA256 = "ab7f6e207caf876abdc57a4da64cc1b89a63768bb551cad8c5df08b7ac0b5f32"
PREREG_NAME = "RISK_TOOL_V3_NATIVE15_C1_GATE_ATTRIBUTION_PREREG_20260916.json"
PRIVATE_REF = "6f41091f1d29c5d6a3aaf74c49f538526c567eef"
PARENT_REF = "runs/public-research/35041411237-1"
SUMMARY_PATH = "research/public-runs/35041411237-1-native15-phase-c1.json"
SUMMARY_BLOB_SHA = "1e62642f03747dd51811c8909f82ae69de356cd9"
PARENT_STATUS = "NATIVE15_STATE_MACHINE_CANDIDATE_MAP_INSUFFICIENT"
RELEASE_TAG = "public-research-run-35041411237-1"
ASSET_NAME = "results.tar.gz"
ASSET_BYTES = 214802
ASSET_SHA256 = "a0388daa1ff62f92951354c4b6c026db6f8357c2e85b668d471983716c87e352"
FULL_MEMBER = "study/NATIVE15_STATE_MACHINE_CANDIDATE_MAP.json"
FULL_BYTES = 3416644
FULL_SHA256 = "ba7a3e6447077c9583ba6d89501e58acfb57f9cff4bb02d9e5e05954909e1749"

PROFILE = {
    "private_ref": PRIVATE_REF,
    "manifest_sha256": PREREG_SHA256,
    "command": ["native15c1attr/risk_v3_native15_c1_gate_attribution.py", "--inputs", "/work/inputs", "--out", "/results/study"],
    "verify_command": ["native15c1attr/risk_v3_native15_c1_gate_attribution_verifier.py", "--inputs", "/work/inputs", "--results", "/results/study"],
    "command_timeout_seconds": 180,
    "verification_timeout_seconds": 180,
    "new_training": False,
    "production_authority": False,
}
rb.COMPUTE_HOST_TIMEOUT_SECONDS = 210
rb.VALIDATE_HOST_TIMEOUT_SECONDS = 210


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(path.parts) and not path.is_absolute() and ".." not in path.parts and "\\" not in name


def require_context() -> None:
    env = os.environ
    if env.get("GITHUB_ACTIONS") != "true" or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch" or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1":
        raise GateError("not_approved_native15_c1_attribution_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")) or not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "")):
        raise GateError("invalid_run_identity")


def load_summary(api) -> bytes:
    route = f"repos/{rb.PRIVATE_REPO}/contents/{SUMMARY_PATH}?ref={urllib.parse.quote(PARENT_REF, safe='')}"
    got = api.request(route)
    if got.get("sha") != SUMMARY_BLOB_SHA:
        raise GateError("native15_c1_summary_blob_mismatch")
    try:
        raw = base64.b64decode(got["content"])
        value = json.loads(raw.decode())
    except Exception as exc:
        raise GateError("native15_c1_summary_decode_failed") from exc
    if value.get("status") != PARENT_STATUS or value.get("candidate_count") != 576 or value.get("passing_count") != 0 or value.get("shortlist_count") != 0:
        raise GateError("native15_c1_summary_identity_mismatch")
    if value.get("next_phase_authorized") is not False or value.get("shortlist") != []:
        raise GateError("native15_c1_summary_authority_mismatch")
    return raw


def stage_full_result(api, root: Path) -> bytes:
    release = api.request(f"repos/{rb.PRIVATE_REPO}/releases/tags/{urllib.parse.quote(RELEASE_TAG, safe='')}")
    assets = {item.get("name"): item for item in release.get("assets") or []}
    asset = assets.get(ASSET_NAME)
    if not asset or asset.get("state") != "uploaded" or asset.get("size") != ASSET_BYTES or asset.get("digest") != "sha256:" + ASSET_SHA256:
        raise GateError("native15_c1_release_asset_identity_mismatch")
    archive = root / ASSET_NAME
    api.request(f"repos/{rb.PRIVATE_REPO}/releases/assets/{asset['id']}", binary_path=archive, max_bytes=ASSET_BYTES)
    if not archive.is_file() or archive.is_symlink() or archive.stat().st_size != ASSET_BYTES or sha256_file(archive) != ASSET_SHA256:
        raise GateError("native15_c1_release_asset_download_mismatch")
    try:
        with tarfile.open(archive, "r:gz") as tar:
            files = [member for member in tar.getmembers() if member.isfile()]
            if any(not safe_member(member.name) for member in files):
                raise GateError("native15_c1_archive_member_unsafe")
            matches = [member for member in files if member.name == FULL_MEMBER]
            if len(matches) != 1:
                raise GateError("native15_c1_full_result_member_not_unique")
            member = matches[0]
            if member.size != FULL_BYTES:
                raise GateError("native15_c1_full_result_size_mismatch")
            stream = tar.extractfile(member)
            if stream is None:
                raise GateError("native15_c1_full_result_extract_failed")
            raw = stream.read(FULL_BYTES + 1)
    finally:
        archive.unlink(missing_ok=True)
    if len(raw) != FULL_BYTES or hashlib.sha256(raw).hexdigest() != FULL_SHA256:
        raise GateError("native15_c1_full_result_digest_mismatch")
    try:
        value = json.loads(raw.decode())
    except Exception as exc:
        raise GateError("native15_c1_full_result_decode_failed") from exc
    if value.get("status") != PARENT_STATUS or value.get("candidate_count") != 576 or value.get("passing_count") != 0 or value.get("shortlist_count") != 0:
        raise GateError("native15_c1_full_result_identity_mismatch")
    if not isinstance(value.get("candidates"), list) or len(value["candidates"]) != 576:
        raise GateError("native15_c1_candidate_surface_missing")
    return raw


def prepare_inputs(api, root: Path, profile: dict):
    work = root / "work"
    work.mkdir()
    scripts = work / "native15c1attr"
    scripts.mkdir()
    here = Path(__file__).resolve().parent
    for name in ("risk_v3_native15_c1_gate_attribution.py", "risk_v3_native15_c1_gate_attribution_verifier.py"):
        source = here / name
        if not source.is_file() or source.is_symlink():
            raise GateError("native15_c1_attribution_public_source_missing")
        shutil.copy2(source, scripts / name)
    inputs = work / "inputs"
    inputs.mkdir()
    prereg = Path(__file__).resolve().parents[1] / "docs" / "research" / PREREG_NAME
    if not prereg.is_file() or prereg.is_symlink() or sha256_file(prereg) != PREREG_SHA256:
        raise GateError("native15_c1_attribution_prereg_identity_failed")
    shutil.copy2(prereg, inputs / "PREREG.json")
    summary = load_summary(api)
    full = stage_full_result(api, root)
    (inputs / "C1_SUMMARY.json").write_bytes(summary)
    (inputs / "C1_FULL_RESULT.json").write_bytes(full)
    return work


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_native15_c1_attribution_profile")
    os.umask(0o077)
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
        raise SystemExit(1)
    except Exception:
        print("Execution failed; C1 attribution did not expose private candidate-map contents publicly.", file=sys.stderr)
        raise


if __name__ == "__main__":
    run()
