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

PROFILE_NAME = "risk-v2-weekly-support-diagnostic-v1"
PROFILE = {
    "private_ref": tb.PRIVATE_REF,
    "manifest_sha256": tb.P1[6],
    "command": ["diagnostic/risk_weekly_support_diagnostic.py", "--inputs", "/work/inputs", "--out", "/results/study"],
    "verify_command": ["diagnostic/risk_weekly_support_diagnostic_verifier.py", "--inputs", "/work/inputs", "--results", "/results/study"],
    "command_timeout_seconds": 600,
    "verification_timeout_seconds": 600,
    "new_training": False,
    "production_authority": False,
}
rb.COMPUTE_HOST_TIMEOUT_SECONDS = 630
rb.VALIDATE_HOST_TIMEOUT_SECONDS = 630


def require_context():
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
        or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
    ):
        raise GateError("not_approved_weekly_support_diagnostic_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "") or "") or not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "") or ""):
        raise GateError("invalid_run_identity")


def prepare_inputs(api, root: Path, profile: dict):
    work = tb.prepare_inputs(api, root, profile)
    inputs = work / "inputs"
    diagnostic = work / "diagnostic"
    diagnostic.mkdir()
    temporal_source = HERE / "risk_temporal_stability_2015_2025.py"
    if not temporal_source.is_file() or temporal_source.is_symlink():
        raise GateError("weekly_support_temporal_base_missing")
    shutil.copy2(temporal_source, inputs / "temporal_base.py")
    for name in ("risk_weekly_support_diagnostic.py", "risk_weekly_support_diagnostic_verifier.py"):
        source = HERE / name
        if not source.is_file() or source.is_symlink():
            raise GateError("weekly_support_source_missing")
        shutil.copy2(source, diagnostic / name)
    return work


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_weekly_support_diagnostic_profile")
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
        print("Execution failed; no private weekly-support diagnostic content was exposed publicly.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
