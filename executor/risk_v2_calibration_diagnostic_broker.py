"""Fixed read-only broker for one Risk Tool v2 Phase-1 diagnostic release."""
from __future__ import annotations

import argparse
import base64
import importlib.util
import os
import re
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_research_broker", HERE / "research_broker.py")
rb = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(rb)
GateError = rb.GateError
PROFILE_NAME = "risk-v2-phase1-calibration-diagnostic-20260914"
PRIVATE_REF = "8a374ab60c7fd1db9ee5ab1debade01afc077027"
RELEASE_ID = 388319643
ASSET_ID = 563182909
ASSET_NAME = "results.tar.gz"
ASSET_BYTES = 8115479
ASSET_SHA256 = "c201cd1b2ab18442ca49d60209b181557335595efdb6a4da5d78549b5c32b21b"
SOURCE = {
    "runtime/research/risk_tool_v2_phase1_calibration_diagnostic_20260914/run_diagnostic.py": {"bytes": 12936, "blob": "d0314febf8e8b029a9bec2b13508f47eee61a728"},
    "runtime/research/risk_tool_v2_phase1_calibration_diagnostic_20260914/verify_diagnostic.py": {"bytes": 1884, "blob": "5b5c9dce003a2f60c18c0826b6742ad8616248fc"},
}
INPUTS = {
    "study/cohort_rows.parquet": {"bytes": 776877, "sha256": "53276c7f25861b8a064288f8662c1a391c0c5af75758376df60e98ab180c4234"},
    "study/HORIZON_METRICS.csv": {"bytes": 978, "sha256": "952693dfc25960fcd780d22d2088b404f2237f5cce969685b97da38dcdf847b0"},
    "study/MODEL_FREEZE.json": {"bytes": 15921, "sha256": "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551"},
    "study/SUMMARY.json": {"bytes": 40351, "sha256": "264589242fb849d9354e1c6be40804715329452f1dbe644b8f5b3c4c1efcf18a"},
}
PROFILE = {
    "private_ref": PRIVATE_REF,
    "manifest_sha256": INPUTS["study/cohort_rows.parquet"]["sha256"],
    "command": ["diagnostic/run_diagnostic.py", "--inputs", "/work/inputs", "--out", "/results/study"],
    "verify_command": ["diagnostic/verify_diagnostic.py", "--inputs", "/work/inputs", "--results", "/results/study", "--runner", "/work/diagnostic/run_diagnostic.py"],
    "command_timeout_seconds": 180,
    "verification_timeout_seconds": 180,
    "new_training": False,
    "production_authority": False,
}


def require_context() -> None:
    env = os.environ
    if (env.get("GITHUB_ACTIONS") != "true" or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
            or env.get("GITHUB_EVENT_NAME") != "push" or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"):
        raise GateError("not_approved_diagnostic_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")) or not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "")):
        raise GateError("invalid_run_identity")


def fetch_source(api, work: Path) -> None:
    root = work / "diagnostic"; root.mkdir()
    for path, expected in SOURCE.items():
        meta = api.request(f"repos/{rb.PRIVATE_REPO}/contents/{path}?ref={PRIVATE_REF}")
        if meta.get("type") != "file" or meta.get("encoding") != "base64" or meta.get("size") != expected["bytes"] or meta.get("sha") != expected["blob"]:
            raise GateError("diagnostic_source_identity_failed")
        raw = base64.b64decode(meta["content"])
        if len(raw) != expected["bytes"]:
            raise GateError("diagnostic_source_size_failed")
        (root / Path(path).name).write_bytes(raw)


def extract_inputs(archive: Path, work: Path) -> None:
    target = work / "inputs"; target.mkdir(); seen = set()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            name = str(PurePosixPath(member.name))
            if name not in INPUTS:
                continue
            if not member.isfile() or name in seen or member.size != INPUTS[name]["bytes"]:
                raise GateError("diagnostic_input_member_invalid")
            seen.add(name); dest = target / PurePosixPath(name).name
            with dest.open("xb") as f: shutil.copyfileobj(tar.extractfile(member), f)
            if rb.sha(dest) != INPUTS[name]["sha256"]: raise GateError("diagnostic_input_digest_failed")
    if seen != set(INPUTS): raise GateError("diagnostic_input_set_incomplete")


def prepare_inputs(api, root: Path, profile: dict):
    work = root / "work"; work.mkdir(); fetch_source(api, work)
    release = api.request(f"repos/{rb.PRIVATE_REPO}/releases/{RELEASE_ID}")
    if release.get("draft") is not False: raise GateError("diagnostic_release_not_published")
    asset = next((x for x in release.get("assets") or [] if x.get("id") == ASSET_ID), None)
    if (not asset or asset.get("name") != ASSET_NAME or asset.get("state") != "uploaded"
            or asset.get("size") != ASSET_BYTES or asset.get("digest") != "sha256:" + ASSET_SHA256):
        raise GateError("diagnostic_release_asset_identity_failed")
    archive = root / ASSET_NAME
    api.request(f"repos/{rb.PRIVATE_REPO}/releases/assets/{ASSET_ID}", binary_path=archive, max_bytes=ASSET_BYTES)
    if archive.stat().st_size != ASSET_BYTES or rb.sha(archive) != ASSET_SHA256: raise GateError("diagnostic_release_download_failed")
    extract_inputs(archive, work); return work


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME); args = parser.parse_args(); require_context()
    if args.profile != PROFILE_NAME: raise GateError("unknown_diagnostic_profile")
    rb.prepare_inputs = prepare_inputs
    if args.phase == "prepare": rb.prepare(PROFILE_NAME, PROFILE)
    elif args.phase == "compute": rb.compute()
    elif args.phase == "cleanup": rb.cleanup()
    else: rb.publish(PROFILE)


def run() -> None:
    try: main()
    except GateError as e: print("Execution stopped: " + str(e), file=sys.stderr); sys.exit(1)
    except Exception: print("Execution failed; no private diagnostic content was published.", file=sys.stderr); sys.exit(1)


if __name__ == "__main__": run()
