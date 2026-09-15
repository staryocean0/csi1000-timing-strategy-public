"""Mirror the validated non-semantic carrier inventory into the private run branch.

This runs only after the carrier-inventory broker has published its verified archive.
It mirrors identity metadata only; parquet values are never deserialized or inspected.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "_carrier_inventory_broker", HERE / "risk_phase1b_carrier_inventory_broker.py"
)
inv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(inv)

GateError = inv.GateError
PRIVATE_REPO = inv.PRIVATE_REPO
PROFILE_NAME = inv.PROFILE_NAME
RESULT_SCHEMA = inv.RESULT_SCHEMA
TASK_ID = inv.TASK_ID
SAFE_ROLES = {
    "canonical_000688_2026_5m",
    "canonical_000852_2026_5m",
    "bar_receipt_metadata",
    "working_lead_offset",
}
RESULT_KEYS = {
    "schema_id",
    "task_id",
    "status",
    "source_release",
    "bundle",
    "candidate_counts",
    "candidates",
    "controls",
}
CONTROL_KEYS = {
    "year_2026_semantic_read",
    "parquet_deserialization",
    "price_return_label_columns_read",
    "model_fit",
    "confirmatory_scoring",
    "new_training",
    "production_authority",
}
CANDIDATE_KEYS = {
    "role",
    "matched_suffix",
    "archive_path",
    "bytes",
    "sha256",
    "git_blob_sha1",
}


def _safe_path(value: str) -> bool:
    p = PurePosixPath(value)
    return bool(p.parts) and not p.is_absolute() and ".." not in p.parts and "\\" not in value


def validate_inventory(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != RESULT_KEYS:
        raise GateError("inventory_mirror_result_shape_invalid")
    if value.get("schema_id") != RESULT_SCHEMA or value.get("task_id") != TASK_ID:
        raise GateError("inventory_mirror_schema_or_task_mismatch")
    if value.get("status") not in {"BYTE_CANDIDATES_IDENTIFIED", "INVENTORY_COMPLETE_BINDING_UNRESOLVED"}:
        raise GateError("inventory_mirror_status_invalid")

    controls = value.get("controls")
    if not isinstance(controls, dict) or set(controls) != CONTROL_KEYS:
        raise GateError("inventory_mirror_controls_invalid")
    if any(controls[key] is not False for key in CONTROL_KEYS):
        raise GateError("inventory_mirror_semantic_or_authority_flag")

    candidates = value.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > 32:
        raise GateError("inventory_mirror_candidate_set_invalid")
    for row in candidates:
        if not isinstance(row, dict) or set(row) != CANDIDATE_KEYS:
            raise GateError("inventory_mirror_candidate_shape_invalid")
        if row.get("role") not in SAFE_ROLES or row.get("matched_suffix") not in inv.EXPECTED_SUFFIXES:
            raise GateError("inventory_mirror_candidate_scope_invalid")
        if not isinstance(row.get("archive_path"), str) or not _safe_path(row["archive_path"]):
            raise GateError("inventory_mirror_candidate_path_invalid")
        if type(row.get("bytes")) is not int or row["bytes"] <= 0:
            raise GateError("inventory_mirror_candidate_bytes_invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256", ""))):
            raise GateError("inventory_mirror_candidate_sha256_invalid")
        if not re.fullmatch(r"[0-9a-f]{40}", str(row.get("git_blob_sha1", ""))):
            raise GateError("inventory_mirror_candidate_git_sha1_invalid")

    counts = value.get("candidate_counts")
    if not isinstance(counts, dict) or set(counts) != SAFE_ROLES:
        raise GateError("inventory_mirror_counts_invalid")
    for role in SAFE_ROLES:
        if type(counts[role]) is not int or counts[role] < 0:
            raise GateError("inventory_mirror_counts_invalid")
        if counts[role] != sum(1 for row in candidates if row["role"] == role):
            raise GateError("inventory_mirror_count_mismatch")
    return value


def main() -> None:
    inv.require_context(os.environ)
    state, root = inv.load_state()
    if state.get("profile_name") != PROFILE_NAME or not state.get("cleanup_complete"):
        raise GateError("inventory_mirror_state_invalid")
    result_path = root / "results" / "risk_phase1b_carrier_inventory.json"
    try:
        result = validate_inventory(json.loads(result_path.read_text()))
    except GateError:
        raise
    except Exception:
        raise GateError("inventory_mirror_result_unreadable") from None

    profile = inv.load_profile()
    source = result.get("source_release")
    if source != {
        "tag": profile["data_release_tag"],
        "asset": profile["data_asset_name"],
        "asset_sha256": profile["data_asset_sha256"],
        "asset_bytes": profile["data_asset_bytes"],
    }:
        raise GateError("inventory_mirror_source_identity_mismatch")
    bundle = result.get("bundle")
    if not isinstance(bundle, dict) or bundle.get("bytes") != profile["bundle_member"]["bytes"] or bundle.get("sha256") != profile["bundle_member"]["sha256"]:
        raise GateError("inventory_mirror_bundle_identity_mismatch")

    api = inv.require_private_api()
    payload = (json.dumps(result, indent=2) + "\n").encode()
    target = f"repos/{PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-carrier-inventory.json"
    api.request(
        target,
        {
            "message": "Mirror validated Risk Phase-1b carrier inventory [skip ci]",
            "branch": state["branch"],
            "content": base64.b64encode(payload).decode(),
        },
        method="PUT",
    )
    returned = api.request(target + "?ref=" + urllib.parse.quote(state["branch"], safe=""))
    if base64.b64decode(returned["content"]) != payload:
        raise GateError("inventory_mirror_private_readback_failed")
    print("Validated non-semantic carrier inventory mirrored to the private run branch.")


def run() -> None:
    try:
        main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("Execution failed; no private diagnostic content was published.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run()
