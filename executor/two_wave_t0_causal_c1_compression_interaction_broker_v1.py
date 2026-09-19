"""Reviewed broker for Two-Wave issue #615 causal C1 × compression interaction."""
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
rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rb)
GateError = rb.GateError

PROFILE_NAME = "two-wave-t0-causal-c1-compression-interaction-v1"
PRIVATE_REF = "7688ba57206dd29fbef88d8e57475255718471fe"
SOURCE_REPO = "staryocean0/factorlab-two-wave-strategy-lab"
SOURCE_REF = "152ae1ef11a04bb3b434da25025794db7a706c81"
DATA_PATH = "data/development/5m_offset_0.parquet"
DATA_BYTES = 3351411
DATA_SHA256 = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"
PREREG = (
    HERE.parent
    / "docs"
    / "research"
    / "TWO_WAVE_T0_CAUSAL_C1_COMPRESSION_INTERACTION_PREREG_20260919.json"
)
SCRIPT_NAMES = (
    "run_two_wave_t0_causal_c1_compression_interaction_v1.py",
    "two_wave_t0_causal_c1_compression_interaction_v1.py",
    "two_wave_t0_causal_c1_compression_interaction_verifier_v1.py",
    "two_wave_c1_compression_risk_ranking_v1.py",
    "two_wave_c1_lead8_precursor_v1.py",
    "wave_blindspot_relocation_v1.py",
    "wave_cycle_identifiability_v1.py",
    "wave_dual_gate_hierarchy_v1.py",
    "wave_dual_gate_probe_v1.py",
    "wave_multiscale_dual_gates_v2.py",
    "wave_scale_specific_continuity_v1.py",
)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def profile() -> dict:
    if not PREREG.is_file():
        raise GateError("issue615_prereg_missing")
    return {
        "private_ref": PRIVATE_REF,
        "manifest_sha256": sha256(PREREG),
        "command": [
            "two_wave_issue615/run_two_wave_t0_causal_c1_compression_interaction_v1.py",
            "--data",
            "/work/inputs/5m_offset_0.parquet",
            "--out",
            "/results/study",
        ],
        "verify_command": [
            "two_wave_issue615/two_wave_t0_causal_c1_compression_interaction_verifier_v1.py",
            "--inputs",
            "/work/inputs",
            "--results",
            "/results/study",
        ],
        "command_timeout_seconds": 1200,
        "verification_timeout_seconds": 600,
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
        raise GateError("not_approved_issue615_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")) or not re.fullmatch(
        r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "")
    ):
        raise GateError("invalid_run_identity")


def download_public_data(target: Path) -> None:
    url = f"https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_REF}/{DATA_PATH}"
    request = urllib.request.Request(
        url, headers={"User-Agent": "csi1000-reviewed-executor"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        final = urllib.parse.urlparse(response.geturl())
        if final.scheme != "https" or final.hostname != "raw.githubusercontent.com":
            raise GateError("issue615_public_redirect_rejected")
        digest = hashlib.sha256()
        total = 0
        with target.open("xb") as output:
            while True:
                chunk = response.read(min(1024 * 1024, DATA_BYTES + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > DATA_BYTES:
                    raise GateError("issue615_public_data_oversize")
                digest.update(chunk)
                output.write(chunk)
    if total != DATA_BYTES or digest.hexdigest() != DATA_SHA256:
        raise GateError("issue615_public_data_identity_failed")


def prepare_inputs(api, root: Path, fixed_profile: dict) -> Path:
    del api, fixed_profile
    work = root / "work"
    work.mkdir()
    inputs = work / "inputs"
    inputs.mkdir()
    scripts = work / "two_wave_issue615"
    scripts.mkdir()
    for name in SCRIPT_NAMES:
        source = HERE / name
        if not source.is_file() or source.is_symlink():
            raise GateError("issue615_public_source_missing")
        shutil.copy2(source, scripts / name)

    prereg_target = scripts / "PREREG.json"
    shutil.copy2(PREREG, prereg_target)
    if sha256(prereg_target) != profile()["manifest_sha256"]:
        raise GateError("issue615_prereg_identity_failed")

    download_public_data(inputs / "5m_offset_0.parquet")
    return work


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_issue615_profile")
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
        print(
            "Execution failed; no private issue-615 result content was exposed publicly.",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    run()
