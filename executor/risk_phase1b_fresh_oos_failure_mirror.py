"""Mirror only bounded non-semantic fresh-OOS failure metadata to the private run branch."""

from __future__ import annotations

import base64
import json
import re
import sys
import urllib.parse
from pathlib import Path

import research_broker as rb

GateError = rb.GateError
PROFILE_NAME = "risk-v2-phase1b-fresh-oos-v1"
SCHEMA_ID = "risk_tool_v2_phase1b_fresh_oos_failure_code@1.0"
MAX_LOG_BYTES = 8192
SAFE_MESSAGE = re.compile(r"[A-Za-z0-9_.:/-]{1,240}")
SAFE_EXCEPTION_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.]{0,127}")
TRACE_FRAME = re.compile(
    r'File "[^"]*risk_phase1b_fresh_oos_eval\.py", line ([0-9]{1,6}), in ([A-Za-z_][A-Za-z0-9_]*)'
)
EXCEPTION_LINE = re.compile(r"([A-Za-z_][A-Za-z0-9_.]{0,127}):(?:\s*(.*))?")


def _extract(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        return {"status": "LOG_UNAVAILABLE"}
    if path.stat().st_size > MAX_LOG_BYTES:
        return {"status": "LOG_TOO_LARGE"}
    text = path.read_text(errors="replace")

    source_line = None
    source_function = None
    for line in text.splitlines():
        frame = TRACE_FRAME.search(line)
        if frame:
            source_line = int(frame.group(1))
            source_function = frame.group(2)

    found = None
    for line in text.splitlines():
        match = EXCEPTION_LINE.fullmatch(line.strip())
        if not match:
            continue
        exception_type, message = match.groups()
        if not SAFE_EXCEPTION_NAME.fullmatch(exception_type):
            continue
        node = {
            "status": "CLASSIFIED_METADATA_ONLY",
            "exception_type": exception_type,
        }
        if source_line is not None and source_function is not None:
            node["source_file"] = "risk_phase1b_fresh_oos_eval.py"
            node["source_line"] = source_line
            node["source_function"] = source_function
        if message:
            message = message.strip("'\"")
            if SAFE_MESSAGE.fullmatch(message):
                node["status"] = "CLASSIFIED"
                node["code"] = message
            else:
                node["code"] = "REDACTED_MESSAGE"
        found = node
    if found:
        return found
    if source_line is not None and source_function is not None:
        return {
            "status": "TRACE_LOCATION_ONLY",
            "source_file": "risk_phase1b_fresh_oos_eval.py",
            "source_line": source_line,
            "source_function": source_function,
        }
    return {"status": "UNCLASSIFIED"}


def main() -> None:
    state, root = rb.load_state()
    if state.get("profile_name") != PROFILE_NAME:
        raise GateError("fresh_oos_failure_profile_mismatch")
    if state.get("compute_success") is True:
        print("Fresh-OOS compute validated; no failure-code sidecar required.")
        return
    if state.get("compute_success") is not False:
        raise GateError("fresh_oos_failure_state_invalid")

    result = {
        "schema_id": SCHEMA_ID,
        "public_run_id": state["run_id"],
        "profile": PROFILE_NAME,
        "compute_exit_code": state.get("compute_exit_code"),
        "validation_exit_code": state.get("validation_exit_code"),
        "compute_error": _extract(root / "results" / "compute.log"),
        "validation_error": _extract(root / "results" / "controller_validation.log"),
        "market_values_exported": False,
        "row_level_data_exported": False,
        "model_outputs_exported": False,
        "production_authority": False,
    }
    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    api = rb.require_private_api()
    target = (
        f"repos/{rb.PRIVATE_REPO}/contents/research/public-runs/"
        f"{state['run_id']}-fresh-oos-failure-code.json"
    )
    api.request(
        target,
        {
            "message": "Mirror sanitized Risk Phase-1b fresh OOS failure code [skip ci]",
            "branch": state["branch"],
            "content": base64.b64encode(payload).decode(),
        },
        method="PUT",
    )
    returned = api.request(target + "?ref=" + urllib.parse.quote(state["branch"], safe=""))
    if base64.b64decode(returned["content"]) != payload:
        raise GateError("fresh_oos_failure_code_private_readback_failed")
    print("Sanitized fresh-OOS failure code mirrored to the private run branch.")


def run() -> None:
    try:
        main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Execution failed; no unsanitized fresh-OOS failure content was mirrored.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
