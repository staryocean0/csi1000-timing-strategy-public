"""Mirror the legacy carrier inventory and its bounded reconciliation sidecar.

The original v1 mirror is preserved in
risk_phase1b_carrier_inventory_private_mirror_core_v1.py and is executed first.
The additional write contains only validated manifest identity/provenance fields.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "_carrier_inventory_mirror_core_v1",
    HERE / "risk_phase1b_carrier_inventory_private_mirror_core_v1.py",
)
legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(legacy)

# Preserve the legacy module surface for existing strict unit tests.
GateError = legacy.GateError
RESULT_SCHEMA = legacy.RESULT_SCHEMA
TASK_ID = legacy.TASK_ID
CONTROL_KEYS = legacy.CONTROL_KEYS
validate_inventory = legacy.validate_inventory


def main() -> None:
    # This performs the unchanged v1 validation and v1 private text mirror.
    legacy.main()

    inv = legacy.inv
    state, root = inv.load_state()
    if not state.get("reconciliation_sidecar"):
        raise GateError("reconciliation_sidecar_state_missing")
    result_path = root / "results" / "risk_phase1b_carrier_reconciliation.json"
    try:
        result = inv.validate_reconciliation(json.loads(result_path.read_text()))
    except GateError:
        raise
    except Exception:
        raise GateError("reconciliation_sidecar_unreadable") from None

    api = inv.require_private_api()
    payload = (json.dumps(result, indent=2) + "\n").encode()
    target = (
        f"repos/{inv.PRIVATE_REPO}/contents/research/public-runs/"
        f"{state['run_id']}-carrier-reconciliation.json"
    )
    api.request(
        target,
        {
            "message": "Mirror validated Risk Phase-1b carrier reconciliation [skip ci]",
            "branch": state["branch"],
            "content": base64.b64encode(payload).decode(),
        },
        method="PUT",
    )
    returned = api.request(target + "?ref=" + urllib.parse.quote(state["branch"], safe=""))
    if base64.b64decode(returned["content"]) != payload:
        raise GateError("reconciliation_private_readback_failed")
    print("Validated identity-only carrier reconciliation mirrored to the private run branch.")


def run() -> None:
    try:
        main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("Execution failed; no unvalidated reconciliation content was published.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run()
