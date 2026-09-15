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
ROOT = HERE.parent
_spec = importlib.util.spec_from_file_location("_rb_consumer_contract", HERE / "research_broker.py")
rb = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(rb)
GateError = rb.GateError

PROFILE_NAME = "risk-v2-consumer-contract-v1"
PRIVATE_REF = "3879de41a5ac7c12246b811f51d16dc8586b9dae"
PARENT_BRANCH = "runs/public-research/34945466654-1"
PARENT_PATH = "research/public-runs/34945466654-1-results/OUTPUT_CONTRACT_RESULT.json"
PARENT_BLOB = "83b19574fef3ef5e46c823f6a9eb067781b85c3e"
PARENT_BYTES = 2759
PARENT_SHA256 = "d7c2cd1106b8025c242ff0486e6a167be3d8669145735e634ea14ddb9977aa96"

PROFILE = {
    "private_ref": PRIVATE_REF,
    "manifest_sha256": "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551",
    "command": [
        "consumer/risk_tool_consumer_contract_v1.py",
        "--parent", "/work/inputs/OUTPUT_CONTRACT_RESULT.json",
        "--contract", "/work/contract/CONSUMER_CONTRACT.json",
        "--out", "/results/study",
    ],
    "verify_command": [
        "consumer/risk_tool_consumer_contract_v1_verifier.py",
        "--parent", "/work/inputs/OUTPUT_CONTRACT_RESULT.json",
        "--contract", "/work/contract/CONSUMER_CONTRACT.json",
        "--results", "/results/study",
    ],
    "command_timeout_seconds": 120,
    "verification_timeout_seconds": 120,
    "new_training": False,
    "production_authority": False,
}
rb.COMPUTE_HOST_TIMEOUT_SECONDS = 150
rb.VALIDATE_HOST_TIMEOUT_SECONDS = 150


def require_context() -> None:
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
        or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
    ):
        raise GateError("not_approved_consumer_contract_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "") or ""):
        raise GateError("invalid_run_identity")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "") or ""):
        raise GateError("invalid_run_identity")


def prepare_inputs(api, root: Path, profile: dict) -> Path:
    work = root / "work"
    work.mkdir()
    inputs = work / "inputs"
    inputs.mkdir()
    scripts = work / "consumer"
    scripts.mkdir()
    contracts = work / "contract"
    contracts.mkdir()

    for name in (
        "risk_tool_consumer_contract_v1.py",
        "risk_tool_consumer_contract_v1_verifier.py",
        "risk_tool_consumer_adapter_v1.py",
    ):
        src = HERE / name
        if not src.is_file() or src.is_symlink():
            raise GateError("consumer_contract_source_missing")
        shutil.copy2(src, scripts / name)

    contract_src = ROOT / "docs" / "acceptance" / "risk_tool_v2" / "risk_tool_consumer_contract_v1.json"
    schema_src = ROOT / "docs" / "acceptance" / "risk_tool_v2" / "risk_tool_output_envelope_v1.schema.json"
    for src in (contract_src, schema_src):
        if not src.is_file() or src.is_symlink():
            raise GateError("consumer_public_contract_missing")
    shutil.copy2(contract_src, contracts / "CONSUMER_CONTRACT.json")
    shutil.copy2(schema_src, contracts / "OUTPUT_SCHEMA.json")

    ref = urllib.parse.quote(PARENT_BRANCH, safe="")
    item = api.request(f"repos/{rb.PRIVATE_REPO}/contents/{PARENT_PATH}?ref={ref}")
    raw = base64.b64decode(item.get("content", "") or "")
    if (
        item.get("sha") != PARENT_BLOB
        or len(raw) != PARENT_BYTES
        or hashlib.sha256(raw).hexdigest() != PARENT_SHA256
    ):
        raise GateError("consumer_parent_authority_identity_failed")
    (inputs / "OUTPUT_CONTRACT_RESULT.json").write_bytes(raw)
    return work


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_consumer_contract_profile")
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
    except GateError as exc:
        print("Execution stopped: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Execution failed; no private consumer-contract content was exposed publicly.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
