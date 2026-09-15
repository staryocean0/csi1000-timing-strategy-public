from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_research_broker", HERE / "research_broker.py")
rb = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(rb); GateError = rb.GateError
_tspec = importlib.util.spec_from_file_location("_temporal_broker", HERE / "risk_temporal_stability_2015_2025_broker.py")
tb = importlib.util.module_from_spec(_tspec); _tspec.loader.exec_module(tb)

PROFILE_NAME = "risk-v2-15m-tail-robust-calibration-v2"
PROFILE = {
    "private_ref": tb.PRIVATE_REF,
    "manifest_sha256": tb.P1[6],
    "command": ["optimization/risk_annual_calibration_tail_robust_v2.py", "--inputs", "/work/inputs", "--out", "/results/study"],
    "verify_command": ["optimization/risk_annual_calibration_tail_robust_v2_verifier.py", "--inputs", "/work/inputs", "--results", "/results/study"],
    "command_timeout_seconds": 900,
    "verification_timeout_seconds": 900,
    "new_training": False,
    "production_authority": False,
}
rb.COMPUTE_HOST_TIMEOUT_SECONDS = 930
rb.VALIDATE_HOST_TIMEOUT_SECONDS = 930


def require_context():
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
        or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
    ):
        raise GateError("not_approved_tail_robust_calibration_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "") or "") or not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "") or ""):
        raise GateError("invalid_run_identity")


def prepare_inputs(api, root: Path, profile: dict):
    work = tb.prepare_inputs(api, root, profile)
    inputs = work / "inputs"
    optimization = work / "optimization"
    optimization.mkdir()
    temporal_source = HERE / "risk_temporal_stability_2015_2025.py"
    if not temporal_source.is_file() or temporal_source.is_symlink():
        raise GateError("tail_robust_temporal_base_missing")
    shutil.copy2(temporal_source, inputs / "temporal_base.py")
    for name in ("risk_annual_calibration_tail_robust_v2.py", "risk_annual_calibration_tail_robust_v2_verifier.py"):
        source = HERE / name
        if not source.is_file() or source.is_symlink():
            raise GateError("tail_robust_source_missing")
        shutil.copy2(source, optimization / name)
    return work


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_tail_robust_calibration_profile")
    rb.prepare_inputs = prepare_inputs
    if args.phase == "prepare":
        rb.prepare(PROFILE_NAME, PROFILE)
    elif args.phase == "compute":
        rb.compute()
    elif args.phase == "cleanup":
        rb.cleanup()
    else:
        rb.publish(PROFILE)


def run():
    try:
        main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Execution failed; no private tail-robust calibration content was exposed publicly.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
