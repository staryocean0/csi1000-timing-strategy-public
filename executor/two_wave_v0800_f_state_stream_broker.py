"""Reviewed broker for Two-Wave V0800-F operational state-stream audit."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_research_broker", HERE / "research_broker.py")
rb = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(rb); GateError = rb.GateError
PROFILE_NAME = "two-wave-v0800-f-operational-state-stream-audit-v1"
PRIVATE_REF = "67effb80f51228f6129dca5c4f7971a0bb6c7f15"
SOURCE_REPO = "staryocean0/factorlab-two-wave-strategy-lab"
SOURCE_REF = "152ae1ef11a04bb3b434da25025794db7a706c81"
DATA_PATH = "data/development/5m_offset_0.parquet"
DATA_BYTES = 3351411
DATA_SHA256 = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"
PROTOCOL = HERE.parent / "docs" / "research" / "TWO_WAVE_V0800_F_OPERATIONAL_STATE_STREAM_AUDIT_PROTOCOL.json"
SCRIPT_NAMES = (
    "two_wave_v0800_semantics.py",
    "two_wave_v0800_scale_map.py",
    "two_wave_v0800_c_prefix_replay.py",
    "two_wave_v0800_f_state_stream.py",
    "two_wave_v0800_f_state_stream_verifier.py",
)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def profile() -> dict:
    if not PROTOCOL.is_file():
        raise GateError("two_wave_v0800_f_protocol_missing")
    return {
        "private_ref": PRIVATE_REF,
        "manifest_sha256": sha256(PROTOCOL),
        "command": ["two_wave_f/two_wave_v0800_f_state_stream.py", "--inputs", "/work/inputs", "--out", "/results/study"],
        "verify_command": ["two_wave_f/two_wave_v0800_f_state_stream_verifier.py", "--inputs", "/work/inputs", "--results", "/results/study"],
        "command_timeout_seconds": 900,
        "verification_timeout_seconds": 300,
        "new_training": False,
        "production_authority": False,
    }


def require_context() -> None:
    e = os.environ
    if e.get("GITHUB_ACTIONS") != "true" or e.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO or e.get("GITHUB_EVENT_NAME") != "workflow_dispatch" or e.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1":
        raise GateError("not_approved_two_wave_v0800_f_context")
    if not re.fullmatch(r"[0-9]+", e.get("GITHUB_RUN_ID", "")) or not re.fullmatch(r"[0-9]+", e.get("GITHUB_RUN_ATTEMPT", "")):
        raise GateError("invalid_run_identity")


def download_public_data(target: Path) -> None:
    url = f"https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_REF}/{DATA_PATH}"
    request = urllib.request.Request(url, headers={"User-Agent": "csi1000-reviewed-executor"})
    with urllib.request.urlopen(request, timeout=90) as response:
        final = urllib.parse.urlparse(response.geturl())
        if final.scheme != "https" or final.hostname != "raw.githubusercontent.com":
            raise GateError("two_wave_v0800_f_public_redirect_rejected")
        digest, total = hashlib.sha256(), 0
        with target.open("xb") as output:
            while True:
                chunk = response.read(min(1024 * 1024, DATA_BYTES + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > DATA_BYTES:
                    raise GateError("two_wave_v0800_f_public_data_oversize")
                digest.update(chunk)
                output.write(chunk)
    if total != DATA_BYTES or digest.hexdigest() != DATA_SHA256:
        raise GateError("two_wave_v0800_f_public_data_identity_failed")


def prepare_inputs(api, root: Path, fixed_profile: dict) -> Path:
    del api, fixed_profile
    work = root / "work"; work.mkdir()
    inputs = work / "inputs"; inputs.mkdir()
    scripts = work / "two_wave_f"; scripts.mkdir()
    for name in SCRIPT_NAMES:
        source = HERE / name
        if not source.is_file() or source.is_symlink():
            raise GateError("two_wave_v0800_f_public_source_missing")
        shutil.copy2(source, scripts / name)
    target = scripts / "PROTOCOL.json"
    shutil.copy2(PROTOCOL, target)
    if sha256(target) != profile()["manifest_sha256"]:
        raise GateError("two_wave_v0800_f_protocol_identity_failed")
    download_public_data(inputs / "5m_offset_0.parquet")
    return work


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_two_wave_v0800_f_profile")
    fixed = profile()
    rb.prepare_inputs = prepare_inputs
    if args.phase == "prepare":
        rb.prepare(PROFILE_NAME, fixed)
    elif args.phase == "compute":
        rb.compute()
    elif args.phase == "cleanup":
        rb.cleanup()
    else:
        rb.publish(fixed)


def run() -> None:
    try:
        main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Execution failed; no private Two-Wave F state-stream content was exposed publicly.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
