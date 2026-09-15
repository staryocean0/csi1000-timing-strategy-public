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
CARRIER_SCHEMA_ID = "risk_tool_v2_phase1b_carrier_schema_diagnostic@1.0"
CARRIER_SCHEMA_FILE = "CARRIER_SCHEMA_DIAGNOSTIC.json"
MAX_LOG_BYTES = 8192
MAX_SCHEMA_BYTES = 16384
SAFE_MESSAGE = re.compile(r"[A-Za-z0-9_.:/-]{1,240}")
SAFE_EXCEPTION_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.]{0,127}")
SAFE_SCHEMA_TEXT = re.compile(r"[ -~]{1,240}")
TRACE_FRAME = re.compile(
    r'File "[^"]*risk_phase1b_fresh_oos_eval\.py", line ([0-9]{1,6}), in ([A-Za-z_][A-Za-z0-9_]*)'
)
EXCEPTION_LINE = re.compile(r"([A-Za-z_][A-Za-z0-9_.]{0,127}):(?:\s*(.*))?")
REQUIRED_COLUMNS = ["datetime", "symbol", "close"]
PANDAS_COLUMN_KEYS = {"name", "field_name", "pandas_type", "numpy_type"}


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


def _safe_schema_scalar(value) -> bool:
    return value is None or (isinstance(value, str) and SAFE_SCHEMA_TEXT.fullmatch(value) is not None)


def _load_carrier_schema(path: Path) -> dict | None:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_SCHEMA_BYTES:
        return None
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    expected_keys = {
        "schema_id",
        "carrier_basename",
        "required_logical_columns",
        "missing_required_physical_columns",
        "physical_fields",
        "pandas_index_columns",
        "pandas_columns",
        "market_values_exported",
        "row_level_data_exported",
        "model_outputs_exported",
        "production_authority",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        return None
    if value.get("schema_id") != CARRIER_SCHEMA_ID or value.get("carrier_basename") != "5m_offset_0.parquet":
        return None
    if value.get("required_logical_columns") != REQUIRED_COLUMNS:
        return None
    missing = value.get("missing_required_physical_columns")
    if not isinstance(missing, list) or not missing or any(item not in REQUIRED_COLUMNS for item in missing):
        return None

    fields = value.get("physical_fields")
    if not isinstance(fields, list) or not 1 <= len(fields) <= 64:
        return None
    for field in fields:
        if not isinstance(field, dict) or set(field) != {"name", "type"}:
            return None
        if not _safe_schema_scalar(field.get("name")) or not _safe_schema_scalar(field.get("type")):
            return None
        if field.get("name") is None or field.get("type") is None:
            return None

    index_columns = value.get("pandas_index_columns")
    if not isinstance(index_columns, list) or len(index_columns) > 16:
        return None
    for item in index_columns:
        if isinstance(item, str):
            if not _safe_schema_scalar(item):
                return None
            continue
        if not isinstance(item, dict) or not set(item).issubset({"kind", "name"}):
            return None
        if any(not _safe_schema_scalar(field_value) for field_value in item.values()):
            return None

    pandas_columns = value.get("pandas_columns")
    if not isinstance(pandas_columns, list) or len(pandas_columns) > 64:
        return None
    for item in pandas_columns:
        if not isinstance(item, dict) or not set(item).issubset(PANDAS_COLUMN_KEYS):
            return None
        if any(not _safe_schema_scalar(field_value) for field_value in item.values()):
            return None

    for key in (
        "market_values_exported",
        "row_level_data_exported",
        "model_outputs_exported",
        "production_authority",
    ):
        if value.get(key) is not False:
            return None
    return value


def _put_private_json(api, target: str, branch: str, message: str, value: dict) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
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
        raise GateError("fresh_oos_private_readback_failed")


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
    api = rb.require_private_api()
    target = (
        f"repos/{rb.PRIVATE_REPO}/contents/research/public-runs/"
        f"{state['run_id']}-fresh-oos-failure-code.json"
    )
    _put_private_json(
        api,
        target,
        state["branch"],
        "Mirror sanitized Risk Phase-1b fresh OOS failure code [skip ci]",
        result,
    )

    carrier_schema = _load_carrier_schema(root / "results" / "study" / CARRIER_SCHEMA_FILE)
    if carrier_schema is not None:
        schema_target = (
            f"repos/{rb.PRIVATE_REPO}/contents/research/public-runs/"
            f"{state['run_id']}-fresh-oos-carrier-schema.json"
        )
        _put_private_json(
            api,
            schema_target,
            state["branch"],
            "Mirror schema-only Risk Phase-1b carrier diagnostic [skip ci]",
            carrier_schema,
        )
        print("Schema-only carrier diagnostic mirrored to the private run branch.")
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
