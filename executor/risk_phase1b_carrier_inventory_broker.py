"""Append-only reconciliation wrapper for the Phase-1b carrier inventory.

The legacy v1 inventory implementation is preserved byte-for-byte in
risk_phase1b_carrier_inventory_core_v1.py.  This wrapper leaves the v1 result
unchanged and adds a second, identity-only sidecar by reading the fixed
DataHub SOURCE_MANIFEST.json from the already frozen handoff bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tarfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "_carrier_inventory_core_v1", HERE / "risk_phase1b_carrier_inventory_core_v1.py"
)
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)

# Re-export the legacy public surface so existing tests and the strict mirror
# continue to validate the original v1 result without reinterpretation.
GateError = core.GateError
PRIVATE_REPO = core.PRIVATE_REPO
PROFILE_NAME = core.PROFILE_NAME
PROFILE_PATH = core.PROFILE_PATH
PROFILE_SCHEMA = core.PROFILE_SCHEMA
RESULT_SCHEMA = core.RESULT_SCHEMA
RECEIPT_SCHEMA = core.RECEIPT_SCHEMA
TASK_ID = core.TASK_ID
DATA_RELEASE_TAG = core.DATA_RELEASE_TAG
DATA_ASSET_NAME = core.DATA_ASSET_NAME
EXPECTED_SUFFIXES = core.EXPECTED_SUFFIXES
MAX_ARCHIVE_BYTES = core.MAX_ARCHIVE_BYTES
MAX_MANIFEST_BYTES = core.MAX_MANIFEST_BYTES
sha = core.sha
safe_path = core.safe_path
unpack = core.unpack
require_context = core.require_context
collect_result_files = core.collect_result_files
upload_result = core.upload_result
require_private_api = core.require_private_api
validate_profile = core.validate_profile
load_profile = core.load_profile
state_path = core.state_path
write_state = core.write_state
load_state = core.load_state
prepare = core.prepare
cleanup = core.cleanup
publish = core.publish
inventory_bundle = core.inventory_bundle

RECONCILIATION_SCHEMA = "risk_tool_v2_phase1b_carrier_reconciliation@1.0"
SOURCE_CONTRACT_SUFFIX = "data/index/SOURCE_MANIFEST.json"
SOURCE_CONTRACT_BYTES = 52711
SOURCE_CONTRACT_SHA256 = "c46f2da6c3df016ca054e183e37267dc472097450fcdd6644c22aa0084c15749"
FROZEN_CANDIDATE = {
    "path": "data/index/5m_offset_0.parquet",
    "bytes": 3615731,
    "sha256": "211448c914b547232bc536da7df94dc5ae279b8265a5cafe58409238485217d7",
    "git_blob_sha1": "1005a95563795ff836d21efa29e417adfa9b3f65",
    "source_sha256": "d3101e6adf7a3e85b11f7c3503a6161f3ab363f7edd90ac8cba451ffe409c46a",
    "frozen_rows": 135682,
    "frozen_min_day": "2015-01-05",
    "frozen_max_day": "2026-08-21",
    "transformation": "symbol filter only; original fields and legacy wallclock labels preserved",
}
RECEIPT_CONSTRAINTS = {
    "000688.SH": {
        "scale_min": 5,
        "rows": 70848,
        "valid": 66373,
        "first_day": "2020-07-23",
        "last_day": "2026-08-21",
    },
    "000852.SH": {
        "scale_min": 5,
        "rows": 77232,
        "valid": 72358,
        "first_day": "2020-01-02",
        "last_day": "2026-08-21",
    },
    "rows_total": 148080,
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
FORBIDDEN_KEY_TOKENS = {
    "open", "high", "low", "close", "price", "return", "label", "volume",
    "amount", "turnover", "vwap", "pnl", "prediction", "probability", "score",
}
SAFE_KEY_TOKENS = {
    "name", "path", "file", "source", "target", "dataset", "symbol", "universe",
    "scale", "frequency", "freq", "interval", "timeframe", "row", "count", "valid",
    "first", "last", "min_day", "max_day", "start", "end", "date", "day", "bytes",
    "size", "sha", "hash", "schema", "timezone", "clock", "timestamp", "session",
    "duplicate", "dedup", "transform", "fresh", "offset", "identity", "provenance",
    "metadata", "stats", "coverage", "range", "contract", "format", "version",
}
TARGET_MARKERS = (
    "5m_offset_0.parquet",
    FROZEN_CANDIDATE["path"],
    FROZEN_CANDIDATE["sha256"],
    FROZEN_CANDIDATE["source_sha256"],
)


def _safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(path.parts) and not path.is_absolute() and ".." not in path.parts and "\\" not in name


def _safe_key(key: object) -> bool:
    if not isinstance(key, str) or not key or len(key) > 160:
        return False
    lowered = key.lower()
    if any(token in lowered for token in FORBIDDEN_KEY_TOKENS):
        return False
    if re.fullmatch(r"\d{6}\.(?:SH|SZ)", key):
        return True
    return any(token in lowered for token in SAFE_KEY_TOKENS)


def _contains_marker(value: object) -> bool:
    if isinstance(value, str):
        return any(marker in value for marker in TARGET_MARKERS)
    if isinstance(value, dict):
        return any(_contains_marker(key) or _contains_marker(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_marker(child) for child in value)
    return False


def _sanitize(value: object, depth: int = 0) -> object:
    if depth > 8:
        return None
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, list):
        output = []
        for child in value[:128]:
            clean = _sanitize(child, depth + 1)
            if clean not in (None, {}, []):
                output.append(clean)
        return output
    if isinstance(value, dict):
        output = {}
        for key, child in value.items():
            if not _safe_key(key):
                continue
            clean = _sanitize(child, depth + 1)
            if clean not in (None, {}, []):
                output[key] = clean
        return output
    return None


def _pointer(parts: list[object]) -> str:
    def escape(piece: object) -> str:
        return str(piece).replace("~", "~0").replace("/", "~1")
    return "/" + "/".join(escape(part) for part in parts)


def _collect_evidence(value: object, parts: list[object] | None = None, output: list[dict] | None = None) -> list[dict]:
    parts = [] if parts is None else parts
    output = [] if output is None else output
    if len(output) >= 64:
        return output
    if isinstance(value, dict):
        if _contains_marker(value):
            clean = _sanitize(value)
            if isinstance(clean, dict) and clean:
                output.append({"json_pointer": _pointer(parts), "fields": clean})
        for key, child in value.items():
            _collect_evidence(child, parts + [key], output)
            if len(output) >= 64:
                break
    elif isinstance(value, list):
        for index, child in enumerate(value[:256]):
            _collect_evidence(child, parts + [index], output)
            if len(output) >= 64:
                break
    return output


def _git_blob_sha1(raw: bytes) -> str:
    digest = hashlib.sha1()
    digest.update(f"blob {len(raw)}\0".encode())
    digest.update(raw)
    return digest.hexdigest()


def extract_source_contract(
    bundle_path: Path,
    profile: dict,
    *,
    expected_bytes: int = SOURCE_CONTRACT_BYTES,
    expected_sha256: str = SOURCE_CONTRACT_SHA256,
) -> dict:
    if bundle_path.stat().st_size != profile["bundle_member"]["bytes"] or sha(bundle_path) != profile["bundle_member"]["sha256"]:
        raise GateError("reconciliation_bundle_identity_mismatch")
    with tarfile.open(bundle_path, "r:") as archive:
        members = [member for member in archive.getmembers() if member.isfile()]
        for member in members:
            if not _safe_member_name(member.name):
                raise GateError("reconciliation_invalid_bundle_member")
        by_name = {member.name: member for member in members}
        if len(by_name) != len(members):
            raise GateError("reconciliation_duplicate_bundle_member")
        contract_names = [
            name for name in by_name
            if name == SOURCE_CONTRACT_SUFFIX or name.endswith("/" + SOURCE_CONTRACT_SUFFIX)
        ]
        if len(contract_names) != 1:
            raise GateError("source_contract_not_unique")
        contract_name = contract_names[0]
        contract_member = by_name[contract_name]
        if contract_member.size != expected_bytes:
            raise GateError("source_contract_size_mismatch")

        manifest_member = by_name.get("BUNDLE_MANIFEST.json")
        if manifest_member is None or manifest_member.size > MAX_MANIFEST_BYTES:
            raise GateError("reconciliation_bundle_manifest_missing")
        manifest_stream = archive.extractfile(manifest_member)
        if manifest_stream is None:
            raise GateError("reconciliation_bundle_manifest_unreadable")
        manifest_raw = manifest_stream.read(MAX_MANIFEST_BYTES + 1)
        if len(manifest_raw) != manifest_member.size:
            raise GateError("reconciliation_bundle_manifest_size_mismatch")
        try:
            bundle_manifest = json.loads(manifest_raw)
        except Exception:
            raise GateError("reconciliation_bundle_manifest_invalid") from None
        expected = bundle_manifest.get("files") if isinstance(bundle_manifest, dict) else None
        meta = expected.get(contract_name) if isinstance(expected, dict) else None
        if not isinstance(meta, dict) or set(meta) != {"bytes", "sha256"}:
            raise GateError("source_contract_manifest_identity_missing")
        if meta.get("bytes") != expected_bytes or meta.get("sha256") != expected_sha256:
            raise GateError("source_contract_manifest_identity_mismatch")

        stream = archive.extractfile(contract_member)
        if stream is None:
            raise GateError("source_contract_unreadable")
        raw = stream.read(expected_bytes + 1)
        if len(raw) != expected_bytes or hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise GateError("source_contract_digest_mismatch")
    try:
        contract = json.loads(raw)
    except Exception:
        raise GateError("source_contract_invalid_json") from None
    if not isinstance(contract, (dict, list)):
        raise GateError("source_contract_root_invalid")

    raw_text = raw.decode("utf-8")
    result = {
        "schema_id": RECONCILIATION_SCHEMA,
        "task_id": TASK_ID,
        "status": "SOURCE_CONTRACT_EVIDENCE_EXTRACTED",
        "source_contract": {
            "archive_path": contract_name,
            "bytes": expected_bytes,
            "sha256": expected_sha256,
            "git_blob_sha1": _git_blob_sha1(raw),
        },
        "frozen_candidate": dict(FROZEN_CANDIDATE),
        "user_receipt_constraints": json.loads(json.dumps(RECEIPT_CONSTRAINTS)),
        "match_flags": {
            "target_path_present": FROZEN_CANDIDATE["path"] in raw_text or "5m_offset_0.parquet" in raw_text,
            "target_sha256_present": FROZEN_CANDIDATE["sha256"] in raw_text,
            "source_sha256_present": FROZEN_CANDIDATE["source_sha256"] in raw_text,
        },
        "evidence": _collect_evidence(contract),
        "controls": {key: False for key in CONTROL_KEYS},
    }
    return validate_reconciliation(result)


def _validate_sanitized(value: object, depth: int = 0) -> None:
    if depth > 8:
        raise GateError("reconciliation_evidence_too_deep")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, list):
        if len(value) > 128:
            raise GateError("reconciliation_evidence_list_too_large")
        for child in value:
            _validate_sanitized(child, depth + 1)
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if not _safe_key(key):
                raise GateError("reconciliation_unsafe_evidence_key")
            _validate_sanitized(child, depth + 1)
        return
    raise GateError("reconciliation_unsafe_evidence_value")


def validate_reconciliation(value: dict) -> dict:
    keys = {
        "schema_id", "task_id", "status", "source_contract", "frozen_candidate",
        "user_receipt_constraints", "match_flags", "evidence", "controls",
    }
    if not isinstance(value, dict) or set(value) != keys:
        raise GateError("reconciliation_result_shape_invalid")
    if value.get("schema_id") != RECONCILIATION_SCHEMA or value.get("task_id") != TASK_ID:
        raise GateError("reconciliation_schema_or_task_mismatch")
    if value.get("status") != "SOURCE_CONTRACT_EVIDENCE_EXTRACTED":
        raise GateError("reconciliation_status_invalid")
    source = value.get("source_contract")
    if not isinstance(source, dict) or set(source) != {"archive_path", "bytes", "sha256", "git_blob_sha1"}:
        raise GateError("reconciliation_source_contract_shape_invalid")
    if not isinstance(source["archive_path"], str) or not (
        source["archive_path"] == SOURCE_CONTRACT_SUFFIX or source["archive_path"].endswith("/" + SOURCE_CONTRACT_SUFFIX)
    ):
        raise GateError("reconciliation_source_contract_path_invalid")
    if source["bytes"] != SOURCE_CONTRACT_BYTES or source["sha256"] != SOURCE_CONTRACT_SHA256:
        # Synthetic unit tests can validate extraction separately, but anything
        # eligible for private mirroring must match the frozen source contract.
        raise GateError("reconciliation_source_contract_identity_invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", str(source.get("git_blob_sha1", ""))):
        raise GateError("reconciliation_source_contract_git_sha1_invalid")
    if value.get("frozen_candidate") != FROZEN_CANDIDATE:
        raise GateError("reconciliation_candidate_identity_changed")
    if value.get("user_receipt_constraints") != RECEIPT_CONSTRAINTS:
        raise GateError("reconciliation_receipt_constraints_changed")
    flags = value.get("match_flags")
    if not isinstance(flags, dict) or set(flags) != {"target_path_present", "target_sha256_present", "source_sha256_present"}:
        raise GateError("reconciliation_match_flags_invalid")
    if any(type(flag) is not bool for flag in flags.values()):
        raise GateError("reconciliation_match_flags_invalid")
    controls = value.get("controls")
    if not isinstance(controls, dict) or set(controls) != CONTROL_KEYS or any(controls[key] is not False for key in CONTROL_KEYS):
        raise GateError("reconciliation_semantic_or_authority_flag")
    evidence = value.get("evidence")
    if not isinstance(evidence, list) or len(evidence) > 64:
        raise GateError("reconciliation_evidence_shape_invalid")
    for row in evidence:
        if not isinstance(row, dict) or set(row) != {"json_pointer", "fields"}:
            raise GateError("reconciliation_evidence_row_invalid")
        if not isinstance(row["json_pointer"], str) or not row["json_pointer"].startswith("/"):
            raise GateError("reconciliation_evidence_pointer_invalid")
        if not isinstance(row["fields"], dict) or not row["fields"]:
            raise GateError("reconciliation_evidence_fields_invalid")
        _validate_sanitized(row["fields"])
    return value


def compute(profile: dict) -> None:
    core.compute(profile)
    state, root = load_state()
    result = extract_source_contract(root / "work" / "inputs" / "bundle.tar", profile)
    output = root / "results" / "risk_phase1b_carrier_reconciliation.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    collect_result_files(root / "results")
    state["reconciliation_sidecar"] = True
    write_state(state)
    print("Frozen DataHub source contract reconciled as identity metadata only; no evaluator was activated.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context(os.environ)
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_profile")
    os.umask(0o077)
    profile = load_profile()
    if args.phase == "prepare":
        prepare(profile)
    elif args.phase == "compute":
        compute(profile)
    elif args.phase == "cleanup":
        cleanup()
    else:
        publish(profile)


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
