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
_rspec = importlib.util.spec_from_file_location("_research_broker", HERE / "research_broker.py")
rb = importlib.util.module_from_spec(_rspec); _rspec.loader.exec_module(rb); GateError = rb.GateError
_tspec = importlib.util.spec_from_file_location("_temporal_broker", HERE / "risk_temporal_stability_2015_2025_broker.py")
tb = importlib.util.module_from_spec(_tspec); _tspec.loader.exec_module(tb)

PROFILE_NAME = "risk-v2-temporal-two-week-v2"
PARENT_CAL_BRANCH = "runs/public-research/34920654435-1"
PARENT_CAL_PATH = "research/public-runs/34920654435-1-results/SUMMARY.json"
PARENT_CAL_BLOB = "51e4d3714c9ec58ba444fcaa44eaffa9277c8162"
PARENT_CAL_BYTES = 806
PARENT_CAL_SHA256 = "9a6693bcfa919f36706878a75cdba8877a6fc016a82546c26513204b388d6270"
PROFILE = {
    "private_ref": tb.PRIVATE_REF,
    "manifest_sha256": tb.P1[6],
    "command": ["temporal_v2/risk_temporal_stability_two_week_v2.py", "--inputs", "/work/inputs", "--out", "/results/study"],
    "verify_command": ["temporal_v2/risk_temporal_stability_two_week_v2_verifier.py", "--inputs", "/work/inputs", "--results", "/results/study"],
    "command_timeout_seconds": 900,
    "verification_timeout_seconds": 900,
    "new_training": False,
    "production_authority": False,
}
rb.COMPUTE_HOST_TIMEOUT_SECONDS = 930
rb.VALIDATE_HOST_TIMEOUT_SECONDS = 930


def blobsha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require_context():
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
        or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
    ):
        raise GateError("not_approved_temporal_two_week_v2_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "") or "") or not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "") or ""):
        raise GateError("invalid_run_identity")


def fetch_parent_calibration_summary(api, destination: Path):
    ref = urllib.parse.quote(PARENT_CAL_BRANCH, safe="")
    item = api.request(f"repos/{rb.PRIVATE_REPO}/contents/{PARENT_CAL_PATH}?ref={ref}")
    raw = base64.b64decode(item.get("content", "") or "")
    if (
        item.get("sha") != PARENT_CAL_BLOB
        or blobsha(raw) != PARENT_CAL_BLOB
        or len(raw) != PARENT_CAL_BYTES
        or sha256(raw) != PARENT_CAL_SHA256
    ):
        raise GateError("temporal_two_week_parent_calibration_identity_failed")
    destination.write_bytes(raw)


def prepare_inputs(api, root: Path, profile: dict):
    work = tb.prepare_inputs(api, root, profile)
    inputs = work / "inputs"
    scripts = work / "temporal_v2"
    scripts.mkdir()
    for name in ("risk_temporal_stability_two_week_v2.py", "risk_temporal_stability_two_week_v2_verifier.py"):
        source = HERE / name
        if not source.is_file() or source.is_symlink():
            raise GateError("temporal_two_week_public_source_missing")
        shutil.copy2(source, scripts / name)
    base_source = HERE / "risk_temporal_stability_2015_2025.py"
    if not base_source.is_file() or base_source.is_symlink():
        raise GateError("temporal_two_week_base_source_missing")
    shutil.copy2(base_source, inputs / "temporal_base.py")
    for name in ("risk_temporal_stability_acceptance.py", "risk_temporal_stability_hierarchical_acceptance_v2.py"):
        source = HERE / name
        if not source.is_file() or source.is_symlink():
            raise GateError("temporal_two_week_acceptance_source_missing")
        shutil.copy2(source, inputs / name)
    profile_source = HERE.parent / "docs/acceptance/risk_tool_v2/temporal_stability_profile_hierarchical_v2.json"
    if not profile_source.is_file() or profile_source.is_symlink():
        raise GateError("temporal_two_week_profile_missing")
    shutil.copy2(profile_source, inputs / "TEMPORAL_PROFILE_V2.json")
    fetch_parent_calibration_summary(api, inputs / "PARENT_CALIBRATION_V2_SUMMARY.json")
    return work


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_temporal_two_week_v2_profile")
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
        print("Execution failed; no private temporal-v2 content was exposed publicly.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
