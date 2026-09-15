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
_spec = importlib.util.spec_from_file_location("_rb_cal_streak", HERE / "research_broker.py")
rb = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(rb); GateError = rb.GateError
_tspec = importlib.util.spec_from_file_location("_t2_cal_streak", HERE / "risk_temporal_stability_2week_v2_broker.py")
t2 = importlib.util.module_from_spec(_tspec); _tspec.loader.exec_module(t2)

PROFILE_NAME = "risk-v2-weekly-calibration-streak-diagnostic-v1"
PARENT_BRANCH = "runs/public-research/34926868278-1"
PARENT_PATH = "research/public-runs/34926868278-1-results/TEMPORAL_METRICS_2W_V2.csv"
PARENT_BLOB = "478f73c1fb9ac9c91d670e67733623e1450da953"
PARENT_BYTES = 170908
PARENT_SHA256 = "455a0f0d61993a933016e111aa1386eaf4ddf3ec6aeb9e28c109f08a559fd060"
V3_BRANCH = "runs/public-research/34930354449-1"
V3_PATH = "research/public-runs/34930354449-1-results/ACCEPTANCE_RESULT_V3.json"
V3_BLOB = "8472220fb8d97256e93a03404e459021badaa14f"
V3_BYTES = 9251
V3_SHA256 = "74df0b6b688d91f8f30c9dcdf3e16f9ddbe77204c9e702fe1d0476601ee3f5ca"
PROFILE = {
    "private_ref": t2.tb.PRIVATE_REF,
    "manifest_sha256": t2.tb.P1[6],
    "command": ["diagnostic/risk_weekly_calibration_streak_diagnostic.py", "--inputs", "/work/inputs", "--out", "/results/study"],
    "verify_command": ["diagnostic/risk_weekly_calibration_streak_diagnostic_verifier.py", "--inputs", "/work/inputs", "--results", "/results/study"],
    "command_timeout_seconds": 900,
    "verification_timeout_seconds": 900,
    "new_training": False,
    "production_authority": False,
}
rb.COMPUTE_HOST_TIMEOUT_SECONDS = 930
rb.VALIDATE_HOST_TIMEOUT_SECONDS = 930


def require_context():
    e = os.environ
    if (
        e.get("GITHUB_ACTIONS") != "true"
        or e.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
        or e.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or e.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
    ):
        raise GateError("not_approved_weekly_calibration_streak_context")
    if not re.fullmatch(r"[0-9]+", e.get("GITHUB_RUN_ID", "") or "") or not re.fullmatch(r"[0-9]+", e.get("GITHUB_RUN_ATTEMPT", "") or ""):
        raise GateError("invalid_run_identity")


def fetch_exact(api, branch: str, path: str, blob: str, size: int, digest: str) -> bytes:
    ref = urllib.parse.quote(branch, safe="")
    item = api.request(f"repos/{rb.PRIVATE_REPO}/contents/{path}?ref={ref}")
    raw = base64.b64decode(item.get("content", "") or "")
    if item.get("sha") != blob or len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
        raise GateError("weekly_calibration_streak_authority_input_identity_failed")
    return raw


def prepare_inputs(api, root: Path, profile: dict):
    work = t2.prepare_inputs(api, root, profile)
    inputs = work / "inputs"
    scripts = work / "diagnostic"
    scripts.mkdir()
    for name in ("risk_weekly_calibration_streak_diagnostic.py", "risk_weekly_calibration_streak_diagnostic_verifier.py"):
        source = HERE / name
        if not source.is_file() or source.is_symlink():
            raise GateError("weekly_calibration_streak_source_missing")
        shutil.copy2(source, scripts / name)
    shutil.copy2(HERE / "risk_temporal_stability_2week_v2.py", inputs / "risk_temporal_stability_2week_v2.py")
    profile_source = HERE.parent / "docs" / "acceptance" / "risk_tool_v2" / "temporal_stability_profile_hierarchical_v3.json"
    if not profile_source.is_file() or profile_source.is_symlink():
        raise GateError("weekly_calibration_streak_v3_profile_missing")
    shutil.copy2(profile_source, inputs / "TEMPORAL_PROFILE_V3.json")
    (inputs / "PARENT_TEMPORAL_METRICS_2W_V2.csv").write_bytes(
        fetch_exact(api, PARENT_BRANCH, PARENT_PATH, PARENT_BLOB, PARENT_BYTES, PARENT_SHA256)
    )
    (inputs / "V3_ACCEPTANCE_RESULT.json").write_bytes(
        fetch_exact(api, V3_BRANCH, V3_PATH, V3_BLOB, V3_BYTES, V3_SHA256)
    )
    return work


def main():
    p = argparse.ArgumentParser()
    p.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    p.add_argument("profile", nargs="?", default=PROFILE_NAME)
    a = p.parse_args()
    require_context()
    if a.profile != PROFILE_NAME:
        raise GateError("unknown_weekly_calibration_streak_profile")
    rb.prepare_inputs = prepare_inputs
    if a.phase == "prepare":
        rb.prepare(PROFILE_NAME, PROFILE)
    elif a.phase == "compute":
        rb.compute()
    elif a.phase == "cleanup":
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
        print("Execution failed; no private weekly-calibration diagnostic content was exposed publicly.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
