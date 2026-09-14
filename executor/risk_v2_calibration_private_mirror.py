"""Mirror already-verified calibration diagnostic outputs to the private run branch."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_research_broker", HERE / "research_broker.py")
rb = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(rb)
GateError = rb.GateError
PROFILE = "risk-v2-phase1-calibration-diagnostic-20260914"
FILES = {
    "DIAGNOSTIC_SUMMARY.json": "research/derived/risk_tool_v2_phase1_calibration_diagnostic_20260914/DIAGNOSTIC_SUMMARY.json",
    "DIAGNOSTIC_TABLE.csv": "research/derived/risk_tool_v2_phase1_calibration_diagnostic_20260914/DIAGNOSTIC_TABLE.csv",
}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_context() -> None:
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
            or os.environ.get("GITHUB_EVENT_NAME") != "push"
            or os.environ.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"):
        raise GateError("not_approved_private_mirror_context")


def main() -> None:
    require_context()
    state, root = rb.load_state()
    if state.get("profile_name") != PROFILE or not state.get("compute_success") or not state.get("cleanup_complete"):
        raise GateError("diagnostic_state_not_mirrorable")
    results = root / "results" / "study"
    api = rb.require_private_api()
    receipt = {"schema_id": "risk_tool_v2_phase1_calibration_private_mirror@1.0", "files": {}}
    for name, target_path in FILES.items():
        path = results / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size <= 0 or path.stat().st_size > 200000:
            raise GateError("diagnostic_mirror_file_invalid")
        raw = path.read_bytes()
        api.request(
            f"repos/{rb.PRIVATE_REPO}/contents/{target_path}",
            {"message": "Record verified Risk v2 calibration diagnostic [skip ci]", "branch": state["branch"],
             "content": base64.b64encode(raw).decode()}, method="PUT")
        returned = api.request(f"repos/{rb.PRIVATE_REPO}/contents/{target_path}?ref=" + state["branch"].replace("/", "%2F"))
        if base64.b64decode(returned["content"]) != raw:
            raise GateError("diagnostic_mirror_readback_failed")
        receipt["files"][name] = {"bytes": len(raw), "sha256": sha_bytes(raw)}
    receipt_raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    target = "research/derived/risk_tool_v2_phase1_calibration_diagnostic_20260914/MIRROR_RECEIPT.json"
    api.request(f"repos/{rb.PRIVATE_REPO}/contents/{target}",
                {"message": "Record Risk v2 calibration mirror receipt [skip ci]", "branch": state["branch"],
                 "content": base64.b64encode(receipt_raw).decode()}, method="PUT")
    returned = api.request(f"repos/{rb.PRIVATE_REPO}/contents/{target}?ref=" + state["branch"].replace("/", "%2F"))
    if base64.b64decode(returned["content"]) != receipt_raw:
        raise GateError("diagnostic_mirror_receipt_readback_failed")
    print("Verified diagnostic outputs mirrored privately.")


if __name__ == "__main__":
    try: main()
    except GateError as e: print("Execution stopped: " + str(e), file=sys.stderr); sys.exit(1)
    except Exception: print("Execution failed; no private diagnostic content was exposed publicly.", file=sys.stderr); sys.exit(1)
