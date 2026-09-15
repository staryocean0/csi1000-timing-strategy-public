"""Mirror verifier-approved Phase-1b text outputs into the private run branch."""
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
if _spec is None or _spec.loader is None:
    raise RuntimeError("research broker unavailable")
rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rb)
GateError = rb.GateError
PROFILE = "risk-v2-phase1b-ordering-calibration-v1"
TARGET_ROOT = "research/derived/risk_tool_v2_phase1b_ordering_calibration_20260915"
FILES = (
    "SUMMARY.json",
    "SUPPORT_AUDIT.csv",
    "HORIZON_METRICS.csv",
    "FRESH_OOS_GATE.json",
    "CALIBRATION_FREEZE.json",
    "INPUT_DATA_RECEIPT.json",
)


def require_context() -> None:
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
        or os.environ.get("GITHUB_EVENT_NAME") != "push"
        or os.environ.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
    ):
        raise GateError("not_approved_phase1b_mirror_context")


def put_verified(api, branch: str, target: str, raw: bytes, message: str) -> None:
    api.request(
        f"repos/{rb.PRIVATE_REPO}/contents/{target}",
        {
            "message": message,
            "branch": branch,
            "content": base64.b64encode(raw).decode(),
        },
        method="PUT",
    )
    got = api.request(
        f"repos/{rb.PRIVATE_REPO}/contents/{target}?ref=" + branch.replace("/", "%2F")
    )
    if base64.b64decode(got["content"]) != raw:
        raise GateError("phase1b_mirror_readback_failed")


def main() -> None:
    require_context()
    state, root = rb.load_state()
    if state.get("profile_name") != PROFILE or not state.get("compute_success") or not state.get("cleanup_complete"):
        raise GateError("phase1b_state_not_mirrorable")
    results = root / "results" / "study"
    api = rb.require_private_api()
    receipt = {
        "schema_id": "risk_tool_v2_phase1b_private_mirror@1.0",
        "public_run_id": state["run_id"],
        "profile": PROFILE,
        "year_2026_read": False,
        "production_authority": False,
        "files": {},
    }
    for name in FILES:
        path = results / name
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 500000:
            raise GateError("phase1b_mirror_file_invalid")
        raw = path.read_bytes()
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            raise GateError("phase1b_mirror_file_not_utf8") from None
        target = f"{TARGET_ROOT}/{name}"
        put_verified(api, state["branch"], target, raw, "Record verified Risk v2 Phase-1b output [skip ci]")
        receipt["files"][name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    put_verified(
        api,
        state["branch"],
        f"{TARGET_ROOT}/MIRROR_RECEIPT.json",
        payload,
        "Record Risk v2 Phase-1b mirror receipt [skip ci]",
    )
    print("Verified Phase-1b outputs mirrored privately.")


if __name__ == "__main__":
    try:
        main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Execution failed; no private Phase-1b content was exposed publicly.", file=sys.stderr)
        raise SystemExit(1)
