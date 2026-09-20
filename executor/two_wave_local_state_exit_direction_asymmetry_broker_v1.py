"""Bounded broker for issue #647 local state-survival direction asymmetry audit."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import re
import shutil
import sys
import tarfile
import urllib.parse
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_research_broker", HERE / "research_broker.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("research broker unavailable")
rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rb)
GateError = rb.GateError

PROFILE_NAME = "two-wave-local-state-exit-direction-asymmetry-v1"
PRIVATE_REF = "ae42b188d878f736c1fa2a2e193a635c5c911596"

PARENT_RELEASE_ID = 392309871
PARENT_ASSET_ID = 576094469
PARENT_ASSET_NAME = "results.tar.gz"
PARENT_ASSET_BYTES = 2_059_472
PARENT_ASSET_SHA256 = "73141f57accfd02aa4607ebcd93843fed0b42905e5c06733671c5a010913f7c8"
PARENT_MEMBER = "study/ISSUE624_SCORED_LEDGER.csv"
PARENT_MEMBER_BYTES = 7_187_315
PARENT_MEMBER_SHA256 = "c1ef13cfc3b2bc5669955ff62a5200b6c56c6868b459421d7e621e5ed189f46f"

PREREG = (
    HERE.parent
    / "docs"
    / "research"
    / "TWO_WAVE_LOCAL_STATE_EXIT_DIRECTION_ASYMMETRY_MECHANISM_PREREG_20260920.json"
)
PREREG_SHA256 = "7cbd46434e36eb9c5390f988a572475bc8e9deed42cd062f8e857f1b0b1bac8e"

SCRIPT_SHA256 = {
    "two_wave_local_state_exit_direction_asymmetry_v1.py":
        "f4f9afc44d649e88f682eaf1ff47f02a2143abae9668f71e906c5b573921021b",
    "two_wave_local_state_exit_direction_asymmetry_verifier_v1.py":
        "ea3fdf89b3fe7f88921699afc1104609fe313f0f8597e64be40ad4f800889611",
}

COMMAND_TIMEOUT_SECONDS = 900
VERIFICATION_TIMEOUT_SECONDS = 900
HOST_TIMEOUT_SECONDS = 960

PROFILE = {
    "private_ref": PRIVATE_REF,
    "manifest_sha256": PREREG_SHA256,
    "command": [
        "two_wave_issue647/two_wave_local_state_exit_direction_asymmetry_v1.py",
        "--ledger",
        "/work/inputs/ISSUE624_SCORED_LEDGER.csv",
        "--out",
        "/results/study/ISSUE647_RESULT.json",
    ],
    "verify_command": [
        "two_wave_issue647/two_wave_local_state_exit_direction_asymmetry_verifier_v1.py",
        "--ledger",
        "/work/inputs/ISSUE624_SCORED_LEDGER.csv",
        "--result",
        "/results/study/ISSUE647_RESULT.json",
        "--prereg",
        "/work/two_wave_issue647/PREREG.json",
    ],
    "command_timeout_seconds": COMMAND_TIMEOUT_SECONDS,
    "verification_timeout_seconds": VERIFICATION_TIMEOUT_SECONDS,
    "new_training": False,
    "production_authority": False,
}


def sha256(path: Path) -> str:
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
        raise GateError("not_approved_issue647_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")):
        raise GateError("invalid_run_identity")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "")):
        raise GateError("invalid_run_identity")


def _verify_public_sources() -> None:
    if not PREREG.is_file() or PREREG.is_symlink() or sha256(PREREG) != PREREG_SHA256:
        raise GateError("issue647_prereg_identity_failed")
    for name, expected in SCRIPT_SHA256.items():
        source = HERE / name
        if not source.is_file() or source.is_symlink() or sha256(source) != expected:
            raise GateError("issue647_public_source_identity_failed")


def _extract_parent_ledger(archive: Path, destination: Path) -> None:
    seen = False
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            name = str(PurePosixPath(member.name))
            if name != PARENT_MEMBER:
                continue
            if seen or not member.isfile() or member.size != PARENT_MEMBER_BYTES:
                raise GateError("issue647_parent_member_identity_failed")
            stream = tar.extractfile(member)
            if stream is None:
                raise GateError("issue647_parent_member_unreadable")
            with destination.open("xb") as output:
                shutil.copyfileobj(stream, output)
            seen = True
    if not seen:
        raise GateError("issue647_parent_member_missing")
    if destination.stat().st_size != PARENT_MEMBER_BYTES or sha256(destination) != PARENT_MEMBER_SHA256:
        raise GateError("issue647_parent_member_digest_failed")


def prepare_inputs(api, root: Path, fixed_profile: dict) -> Path:
    del fixed_profile
    _verify_public_sources()

    work = root / "work"
    work.mkdir()
    inputs = work / "inputs"
    inputs.mkdir()
    scripts = work / "two_wave_issue647"
    scripts.mkdir()

    for name, expected in SCRIPT_SHA256.items():
        source = HERE / name
        staged = scripts / name
        shutil.copy2(source, staged)
        if sha256(staged) != expected:
            raise GateError("issue647_staged_source_identity_failed")
    shutil.copy2(PREREG, scripts / "PREREG.json")
    if sha256(scripts / "PREREG.json") != PREREG_SHA256:
        raise GateError("issue647_staged_prereg_identity_failed")

    release = api.request(f"repos/{rb.PRIVATE_REPO}/releases/{PARENT_RELEASE_ID}")
    if (
        release.get("draft") is not False
        or release.get("prerelease") is not True
        or release.get("tag_name") != "public-research-run-35488698309-1"
    ):
        raise GateError("issue647_parent_release_identity_failed")
    asset = next(
        (item for item in release.get("assets") or [] if item.get("id") == PARENT_ASSET_ID),
        None,
    )
    if (
        not asset
        or asset.get("name") != PARENT_ASSET_NAME
        or asset.get("state") != "uploaded"
        or asset.get("size") != PARENT_ASSET_BYTES
        or asset.get("digest") != "sha256:" + PARENT_ASSET_SHA256
    ):
        raise GateError("issue647_parent_asset_identity_failed")

    archive = root / PARENT_ASSET_NAME
    api.request(
        f"repos/{rb.PRIVATE_REPO}/releases/assets/{PARENT_ASSET_ID}",
        binary_path=archive,
        max_bytes=PARENT_ASSET_BYTES,
    )
    if archive.stat().st_size != PARENT_ASSET_BYTES or sha256(archive) != PARENT_ASSET_SHA256:
        raise GateError("issue647_parent_asset_download_failed")
    _extract_parent_ledger(archive, inputs / "ISSUE624_SCORED_LEDGER.csv")
    return work


def configure_host_timeouts() -> None:
    rb.COMPUTE_HOST_TIMEOUT_SECONDS = HOST_TIMEOUT_SECONDS
    rb.VALIDATE_HOST_TIMEOUT_SECONDS = HOST_TIMEOUT_SECONDS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_issue647_profile")
    _verify_public_sources()
    rb.prepare_inputs = prepare_inputs
    if args.phase == "prepare":
        rb.prepare(PROFILE_NAME, PROFILE)
    elif args.phase == "compute":
        configure_host_timeouts()
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
        print(
            "Execution failed; no private issue-647 research bytes were exposed publicly.",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    run()
