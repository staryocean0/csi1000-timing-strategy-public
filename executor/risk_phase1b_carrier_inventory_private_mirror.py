"""Mirror the legacy carrier inventory and bounded identity-only sidecars.

The original v1 mirror is preserved in
risk_phase1b_carrier_inventory_private_mirror_core_v1.py and is executed first.
Additional writes contain only validated manifest identity/provenance metadata.
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

_binding_spec = importlib.util.spec_from_file_location(
    "_carrier_symbol_binding",
    HERE / "risk_phase1b_carrier_symbol_binding.py",
)
symbol_binding = importlib.util.module_from_spec(_binding_spec)
_binding_spec.loader.exec_module(symbol_binding)

# Preserve the legacy module surface for existing strict unit tests.
GateError = legacy.GateError
RESULT_SCHEMA = legacy.RESULT_SCHEMA
TASK_ID = legacy.TASK_ID
CONTROL_KEYS = legacy.CONTROL_KEYS
validate_inventory = legacy.validate_inventory


def _put_verified(api, target: str, branch: str, message: str, value: dict) -> None:
    payload = (json.dumps(value, indent=2) + "\n").encode()
    api.request(
        target,
        {
            "message": message,
            "branch": branch,
            "content": base64.b64encode(payload).decode(),
        },
        method="PUT",
    )
    returned = api.request(target + "?ref=" + urllib.parse.quote(branch, safe=""))
    if base64.b64decode(returned["content"]) != payload:
        raise GateError("carrier_identity_sidecar_private_readback_failed")


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
    target = (
        f"repos/{inv.PRIVATE_REPO}/contents/research/public-runs/"
        f"{state['run_id']}-carrier-reconciliation.json"
    )
    _put_verified(
        api,
        target,
        state["branch"],
        "Mirror validated Risk Phase-1b carrier reconciliation [skip ci]",
        result,
    )
    print("Validated identity-only carrier reconciliation mirrored to the private run branch.")

    # A second, even narrower mirror-only sidecar inspects only the fixed JSON
    # source contract. It exports exact index symbols and adjacent identity
    # metadata; it never deserializes the parquet candidate or exposes market
    # values/model outputs.
    try:
        binding = symbol_binding.extract_from_bundle(root / "work" / "inputs" / "bundle.tar", inv)
    except GateError:
        raise
    except Exception:
        raise GateError("symbol_binding_sidecar_failed") from None
    binding_target = (
        f"repos/{inv.PRIVATE_REPO}/contents/research/public-runs/"
        f"{state['run_id']}-carrier-symbol-binding.json"
    )
    _put_verified(
        api,
        binding_target,
        state["branch"],
        "Mirror validated Risk Phase-1b carrier symbol binding [skip ci]",
        binding,
    )
    print("Validated symbol-only carrier binding evidence mirrored to the private run branch.")


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
