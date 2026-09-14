"""Fixed standard broker for the frozen Risk Tool v2 Phase-1b study."""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_research_broker", HERE / "research_broker.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("research broker unavailable")
rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rb)
GateError = rb.GateError

# Phase-1b independently recomputes two 5000-draw bootstrap families in the
# validator. Its frozen in-container validator timeout is 300s, so the host
# watchdog must exceed that budget. This override is execution-only and does
# not alter data, models, bootstrap repetitions, seeds, or acceptance gates.
PHASE1B_VALIDATE_HOST_TIMEOUT_SECONDS = 330
rb.VALIDATE_HOST_TIMEOUT_SECONDS = PHASE1B_VALIDATE_HOST_TIMEOUT_SECONDS

PROFILE_NAME = "risk-v2-phase1b-ordering-calibration-v1"
PRIVATE_REF = "c45c0f991d9d6872bf312bbf0e1f220b98958d75"
RELEASE_ID = 388319643
ASSET_ID = 563182909
ASSET_NAME = "results.tar.gz"
ASSET_BYTES = 8115479
ASSET_SHA256 = "c201cd1b2ab18442ca49d60209b181557335595efdb6a4da5d78549b5c32b21b"
INPUTS = {
    "study/state_rows.parquet": {
        "bytes": 8159191,
        "sha256": "e74e497ddf075f7b1519ab3afd96dddfeafbeafce7e4bab86a77d9037e23e30d",
    },
    "study/cohort_rows.parquet": {
        "bytes": 776877,
        "sha256": "53276c7f25861b8a064288f8662c1a391c0c5af75758376df60e98ab180c4234",
    },
}
PROFILE = {
    "private_ref": PRIVATE_REF,
    "manifest_sha256": INPUTS["study/cohort_rows.parquet"]["sha256"],
    "command": ["phase1b/risk_phase1b_release.py", "--inputs", "/work/inputs", "--out", "/results/study"],
    "verify_command": ["phase1b/risk_phase1b_release_verifier.py", "--results", "/results/study"],
    "command_timeout_seconds": 900,
    "verification_timeout_seconds": 300,
    "new_training": False,
    "production_authority": False,
}


def require_context() -> None:
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
        or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
    ):
        raise GateError("not_approved_phase1b_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")):
        raise GateError("invalid_run_identity")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "")):
        raise GateError("invalid_run_identity")


def extract_inputs(archive: Path, work: Path) -> None:
    target = work / "inputs"
    target.mkdir()
    seen = set()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            name = str(PurePosixPath(member.name))
            if name not in INPUTS:
                continue
            expected = INPUTS[name]
            if not member.isfile() or name in seen or member.size != expected["bytes"]:
                raise GateError("phase1b_parent_member_invalid")
            stream = tar.extractfile(member)
            if stream is None:
                raise GateError("phase1b_parent_member_unreadable")
            destination = target / PurePosixPath(name).name
            with destination.open("xb") as output:
                shutil.copyfileobj(stream, output)
            if rb.sha(destination) != expected["sha256"]:
                raise GateError("phase1b_parent_digest_failed")
            seen.add(name)
    if seen != set(INPUTS):
        raise GateError("phase1b_parent_set_incomplete")


def prepare_inputs(api, root: Path, profile: dict):
    work = root / "work"
    work.mkdir()
    scripts = work / "phase1b"
    scripts.mkdir()
    for name in ("risk_phase1b_release.py", "risk_phase1b_release_verifier.py"):
        source = HERE / name
        if not source.is_file() or source.is_symlink():
            raise GateError("phase1b_public_source_missing")
        shutil.copy2(source, scripts / name)

    release = api.request(f"repos/{rb.PRIVATE_REPO}/releases/{RELEASE_ID}")
    if release.get("draft") is not False or release.get("prerelease") is not True:
        raise GateError("phase1b_parent_release_not_published")
    asset = next((item for item in release.get("assets") or [] if item.get("id") == ASSET_ID), None)
    if (
        not asset
        or asset.get("name") != ASSET_NAME
        or asset.get("state") != "uploaded"
        or asset.get("size") != ASSET_BYTES
        or asset.get("digest") != "sha256:" + ASSET_SHA256
    ):
        raise GateError("phase1b_parent_release_identity_failed")
    archive = root / ASSET_NAME
    api.request(
        f"repos/{rb.PRIVATE_REPO}/releases/assets/{ASSET_ID}",
        binary_path=archive,
        max_bytes=ASSET_BYTES,
    )
    if archive.stat().st_size != ASSET_BYTES or rb.sha(archive) != ASSET_SHA256:
        raise GateError("phase1b_parent_download_failed")
    extract_inputs(archive, work)
    return work


def main() -> None:
    parser = argparse.ArgumentParser()
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
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Execution failed; no private Phase-1b content was exposed publicly.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
