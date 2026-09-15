"""Bounded diagnostic-only broker for Risk Tool V2 2026 fresh-OOS cohort attrition."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

import research_broker as rb
import risk_phase1b_fresh_oos_broker as fresh

GateError = rb.GateError

PROFILE_NAME = "risk-v2-phase1b-fresh-oos-attrition-v1"
TASK_ID = "CSI1000-RISK-V2-2026-FRESH-OOS-ATTRITION-V1-20260915"
PREREG_SHA256 = "98b5e0f22958986ad77529b260895a849f24054f23fefbc7e71bdd061affd53a"
PARENT_RUN = "34956326542-1"
PARENT_STATUS = "INSUFFICIENT_2026_SUPPORT"

PROFILE = {
    "private_ref": fresh.PRIVATE_REF,
    "manifest_sha256": PREREG_SHA256,
    "command": [
        "attrition/risk_phase1b_fresh_oos_attrition.py",
        "--inputs",
        "/work/inputs",
        "--out",
        "/results/study",
    ],
    "verify_command": [
        "attrition/risk_phase1b_fresh_oos_attrition_verifier.py",
        "--inputs",
        "/work/inputs",
        "--results",
        "/results/study",
    ],
    "command_timeout_seconds": 900,
    "verification_timeout_seconds": 900,
    "new_training": False,
    "production_authority": False,
}

rb.COMPUTE_HOST_TIMEOUT_SECONDS = 960
rb.VALIDATE_HOST_TIMEOUT_SECONDS = 960


def require_context() -> None:
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
        or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
    ):
        raise GateError("not_approved_attrition_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")) or not re.fullmatch(
        r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "")
    ):
        raise GateError("invalid_run_identity")


def prepare_inputs(api, root: Path, profile: dict):
    work = root / "work"
    work.mkdir()
    scripts = work / "attrition"
    scripts.mkdir()
    for name in (
        "risk_phase1b_fresh_oos_attrition.py",
        "risk_phase1b_fresh_oos_attrition_verifier.py",
        "risk_phase1b_fresh_oos_eval.py",
    ):
        source = Path(__file__).resolve().parent / name
        if not source.is_file() or source.is_symlink():
            raise GateError("attrition_public_source_missing")
        shutil.copy2(source, scripts / name)

    inputs = work / "inputs"
    inputs.mkdir()
    carrier_source = fresh._stage_carrier(api, root, inputs)
    identity = {
        "schema_id": "risk_tool_v2_phase1b_fresh_oos_attrition_identity@1.0",
        "profile": PROFILE_NAME,
        "task_id": TASK_ID,
        "prereg_sha256": PREREG_SHA256,
        "parent_fresh_oos": {
            "run_id": PARENT_RUN,
            "overall_status": PARENT_STATUS,
            "verdict_immutable": True,
        },
        "carrier": {
            "path": fresh.CARRIER_MEMBER,
            "bytes": fresh.CARRIER_BYTES,
            "sha256": fresh.CARRIER_SHA256,
            **carrier_source,
        },
        "fresh_oos_cutoff_trading_day_inclusive": "2026-09-11",
        "user_authorized_same_source_and_valid": True,
        "diagnostic_only": True,
        "parent_verdict_changed": False,
        "model_execution": False,
        "calibration_execution": False,
        "new_training": False,
        "production_authority": False,
    }
    (inputs / "DIAGNOSTIC_IDENTITY.json").write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n")
    return work


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_attrition_profile")
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
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Execution failed; no private attrition content was exposed publicly.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
