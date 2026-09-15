from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import os
import re
import shutil
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_research_broker", HERE / "research_broker.py")
rb = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(rb); GateError = rb.GateError

PROFILE_NAME = "risk-v2-weekly-window-feasibility-v1"
PRIVATE_REF = "3879de41a5ac7c12246b811f51d16dc8586b9dae"
PARENT_BRANCH = "runs/public-research/34925285496-1"
PARENT_PATH = "research/public-runs/34925285496-1-results/WEEKLY_SUPPORT_BUCKETS.csv"
PARENT_BLOB = "7a5b3642acf47371c92ea3107a89a3d528cf4ba8"
PARENT_BYTES = 82047
PARENT_SHA256 = "e41f398d289cac851991e5bce3818d834dcdb82ce18dd5120ae3b11dfa6bb2f9"
PROFILE = {
    "private_ref": PRIVATE_REF,
    "manifest_sha256": "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551",
    "command": ["feasibility/risk_weekly_window_feasibility.py", "--input", "/work/inputs/WEEKLY_SUPPORT_BUCKETS.csv", "--out", "/results/study"],
    "verify_command": ["feasibility/risk_weekly_window_feasibility_verifier.py", "--input", "/work/inputs/WEEKLY_SUPPORT_BUCKETS.csv", "--results", "/results/study"],
    "command_timeout_seconds": 120,
    "verification_timeout_seconds": 120,
    "new_training": False,
    "production_authority": False,
}
rb.COMPUTE_HOST_TIMEOUT_SECONDS = 150
rb.VALIDATE_HOST_TIMEOUT_SECONDS = 150


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require_context():
    env = os.environ
    if env.get("GITHUB_ACTIONS") != "true" or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch" or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1":
        raise GateError("not_approved_weekly_window_feasibility_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "") or "") or not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "") or ""):
        raise GateError("invalid_run_identity")


def prepare_inputs(api, root: Path, profile: dict):
    work = root / "work"; work.mkdir()
    inputs = work / "inputs"; inputs.mkdir()
    scripts = work / "feasibility"; scripts.mkdir()
    for name in ("risk_weekly_window_feasibility.py", "risk_weekly_window_feasibility_verifier.py"):
        source = HERE / name
        if not source.is_file() or source.is_symlink():
            raise GateError("weekly_window_feasibility_source_missing")
        shutil.copy2(source, scripts / name)
    ref = urllib.parse.quote(PARENT_BRANCH, safe="")
    item = api.request(f"repos/{rb.PRIVATE_REPO}/contents/{PARENT_PATH}?ref={ref}")
    raw = base64.b64decode(item.get("content", "") or "")
    if item.get("sha") != PARENT_BLOB or len(raw) != PARENT_BYTES or sha256_bytes(raw) != PARENT_SHA256:
        raise GateError("weekly_window_parent_identity_failed")
    (inputs / "WEEKLY_SUPPORT_BUCKETS.csv").write_bytes(raw)
    return work


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"]); parser.add_argument("profile", nargs="?", default=PROFILE_NAME); args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME: raise GateError("unknown_weekly_window_feasibility_profile")
    rb.prepare_inputs = prepare_inputs
    if args.phase == "prepare": rb.prepare(PROFILE_NAME, PROFILE)
    elif args.phase == "compute": rb.compute()
    elif args.phase == "cleanup": rb.cleanup()
    else: rb.publish(PROFILE)


def run():
    try: main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr); raise SystemExit(1)
    except Exception:
        print("Execution failed; no private weekly-window feasibility content was exposed publicly.", file=sys.stderr); raise SystemExit(1)


if __name__ == "__main__": run()
