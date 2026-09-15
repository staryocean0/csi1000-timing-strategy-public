from __future__ import annotations

import base64
import json
import urllib.parse
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_rb_attrition_mirror", HERE / "research_broker.py")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
GateError = base.GateError

PROFILE = "risk-v2-phase1b-fresh-oos-attrition-v1"
FILE = "ATTRITION.json"
MAX_BYTES = 256 * 1024


def main() -> None:
    state, root = base.load_state()
    if (
        state.get("profile_name") != PROFILE
        or state.get("compute_success") is not True
        or state.get("cleanup_complete") is not True
    ):
        raise GateError("attrition_state_not_mirrorable")
    path = root / "results" / "study" / FILE
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
        raise GateError("attrition_mirror_file_invalid")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
        value = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise GateError("attrition_mirror_not_valid_json") from None
    required_false = (
        "parent_verdict_changed",
        "model_execution",
        "calibration_execution",
        "new_training",
        "row_level_market_data_exported",
        "market_values_exported",
        "timestamps_exported",
        "model_outputs_exported",
        "production_authority",
    )
    if (
        not isinstance(value, dict)
        or value.get("status") != "DIAGNOSTIC_COMPLETE"
        or value.get("diagnostic_only") is not True
        or any(value.get(key) is not False for key in required_false)
    ):
        raise GateError("attrition_mirror_boundary_invalid")
    api = base.require_private_api()
    target = f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-attrition.json"
    api.request(
        target,
        {
            "message": "Record verified Risk Tool fresh-OOS attrition diagnostic [skip ci]",
            "branch": state["branch"],
            "content": base64.b64encode(raw).decode("ascii"),
        },
        method="PUT",
    )
    got = api.request(target + "?ref=" + urllib.parse.quote(state["branch"], safe=""))
    if base64.b64decode(got["content"]) != raw:
        raise GateError("attrition_mirror_readback_failed")
    print("Verified fresh-OOS attrition diagnostic mirrored privately.")


if __name__ == "__main__":
    main()
