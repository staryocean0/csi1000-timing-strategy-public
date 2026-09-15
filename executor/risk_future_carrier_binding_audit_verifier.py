from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

TASK_ID = "CSI1000-RISK-V2-FUTURE-CARRIER-BINDING-AUDIT-V1-20260915"
PROFILE = "risk-v2-future-carrier-binding-audit-v1"
SCHEMA_ID = "risk_tool_v2_future_carrier_binding_audit_result@2.0"
AMENDMENT_SCHEMA = "risk_tool_v2_future_carrier_binding_audit_amendment@1.0"
AMENDMENT_SHA256 = "7972fbc0a13671cf182cdb0c7c3b4ce6d10588c63cbe34c9e6871f300626f371"
SOURCE_CONTRACT_SHA256 = "c46f2da6c3df016ca054e183e37267dc472097450fcdd6644c22aa0084c15749"
SOURCE_CONTRACT_BYTES = 52711
FUTURE_START = "2026-09-14"
FUTURE_END = "2027-03-31"


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("verifier_input_missing")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError("verifier_json_object_required")
    return value


def subset(row: object) -> dict | None:
    if not isinstance(row, dict):
        return None
    keys = (
        "rows",
        "first_trading_day",
        "last_trading_day",
        "trading_day_count",
        "expected_trading_day_count",
        "day_count_ready",
    )
    if any(key not in row for key in keys):
        return None
    return {key: row[key] for key in keys}


def matching_view_indexes(manifest: dict, expected: dict) -> list[int]:
    views = manifest.get("views")
    if not isinstance(views, list):
        return []
    indexes: list[int] = []
    for index, view in enumerate(views):
        if not isinstance(view, dict):
            continue
        audit = view.get("audit")
        symbols = audit.get("symbols") if isinstance(audit, dict) else None
        if not isinstance(symbols, dict):
            continue
        if all(subset(symbols.get(symbol)) == row for symbol, row in expected.items()):
            indexes.append(index)
    return indexes


def independently_build(inputs: Path) -> dict:
    amendment_path = inputs / "BINDING_AMENDMENT.json"
    source_path = inputs / "SOURCE_MANIFEST.json"
    identity = load(inputs / "SOURCE_CONTRACT_IDENTITY.json")
    amendment = load(amendment_path)
    if sha256_file(amendment_path) != AMENDMENT_SHA256:
        raise RuntimeError("verifier_amendment_digest_mismatch")
    if amendment.get("schema_id") != AMENDMENT_SCHEMA or amendment.get("task_id") != TASK_ID:
        raise RuntimeError("verifier_amendment_identity_mismatch")
    if source_path.stat().st_size != SOURCE_CONTRACT_BYTES or sha256_file(source_path) != SOURCE_CONTRACT_SHA256:
        raise RuntimeError("verifier_source_contract_identity_mismatch")
    if identity.get("source_contract", {}).get("sha256") != SOURCE_CONTRACT_SHA256:
        raise RuntimeError("verifier_broker_source_identity_mismatch")
    if identity.get("amendment_sha256") != AMENDMENT_SHA256:
        raise RuntimeError("verifier_broker_amendment_identity_mismatch")

    manifest = load(source_path)
    corrected = amendment["corrected_binding"]
    artifact = corrected["source_artifact"]
    targets = corrected["target_symbols"]
    target_names = sorted(targets)
    declared = manifest.get("symbols")
    root_ok = isinstance(declared, list) and all(symbol in declared for symbol in target_names)
    artifacts = manifest.get("artifacts")
    got_artifact = artifacts.get(artifact["name"]) if isinstance(artifacts, dict) else None
    artifact_ok = (
        isinstance(got_artifact, dict)
        and got_artifact.get("sha256") == artifact["sha256"]
        and got_artifact.get("rows") == artifact["rows"]
    )
    parent_ok = manifest.get("canonical_1m_parent_dataset_version") == corrected["canonical_1m_parent_dataset_version"]
    indexes = matching_view_indexes(manifest, targets)
    view_ok = len(indexes) == 1
    valid = bool(root_ok and artifact_ok and parent_ok and view_ok)
    overlap_start = max(row["first_trading_day"] for row in targets.values()) if valid else None
    overlap_end = min(row["last_trading_day"] for row in targets.values()) if valid else None
    covers = bool(valid and overlap_start and overlap_end and overlap_start <= FUTURE_START and overlap_end >= FUTURE_END)
    return {
        "schema_id": SCHEMA_ID,
        "task_id": TASK_ID,
        "profile": PROFILE,
        "amendment_sha256": AMENDMENT_SHA256,
        "original_prereg_sha256": amendment["original_preregistration"]["sha256"],
        "status": "SOURCE_FAMILY_BINDING_VALID" if valid else "SOURCE_FAMILY_BINDING_INVALID",
        "source_contract": identity["source_contract"],
        "source_artifact": {
            "name": artifact["name"],
            "sha256": artifact["sha256"],
            "rows": artifact["rows"],
            "binding_valid": bool(artifact_ok),
        },
        "canonical_1m_parent_dataset_version": corrected["canonical_1m_parent_dataset_version"],
        "parent_dataset_binding_valid": bool(parent_ok),
        "declared_target_symbols_present": bool(root_ok),
        "target_symbols": targets,
        "matching_view_indexes": indexes,
        "view_binding_unique": bool(view_ok),
        "pair_overlap": {"min_trading_day": overlap_start, "max_trading_day": overlap_end},
        "future_oos_window": {
            "start_inclusive": FUTURE_START,
            "end_inclusive": FUTURE_END,
            "current_snapshot_covers_full_window": covers,
            "current_snapshot_is_future_oos_evidence": False,
            "activation_requires_new_snapshot_covering_full_window_for_both_symbols": True,
        },
        "controls": {
            "market_values_read": False,
            "returns_or_labels_read": False,
            "parquet_deserialization": False,
            "model_execution": False,
            "calibration_execution": False,
            "new_training": False,
            "parent_verdict_changed": False,
            "strategy_authority": False,
            "production_authority": False,
        },
    }


def verify(inputs: Path, results: Path) -> dict:
    actual = load(results / "BINDING_AUDIT.json")
    expected = independently_build(inputs)
    if actual != expected:
        raise RuntimeError("future_binding_independent_recompute_mismatch")
    if actual["status"] != "SOURCE_FAMILY_BINDING_VALID":
        raise RuntimeError("future_binding_source_family_invalid")
    return {
        "status": "passed",
        "binding_status": actual["status"],
        "current_snapshot_covers_full_window": actual["future_oos_window"]["current_snapshot_covers_full_window"],
        "production_authority": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.inputs.resolve(), args.results.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()
