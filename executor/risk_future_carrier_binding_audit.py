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


def load_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("json_input_missing")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError("json_object_required")
    return value


def _target_subset(row: object) -> dict | None:
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


def _matching_views(manifest: dict, expected: dict) -> list[int]:
    views = manifest.get("views")
    if not isinstance(views, list):
        return []
    matches: list[int] = []
    for index, view in enumerate(views):
        if not isinstance(view, dict):
            continue
        audit = view.get("audit")
        symbols = audit.get("symbols") if isinstance(audit, dict) else None
        if not isinstance(symbols, dict):
            continue
        ok = True
        for symbol, expected_row in expected.items():
            if _target_subset(symbols.get(symbol)) != expected_row:
                ok = False
                break
        if ok:
            matches.append(index)
    return matches


def build_result(inputs: Path) -> dict:
    amendment_path = inputs / "BINDING_AMENDMENT.json"
    source_path = inputs / "SOURCE_MANIFEST.json"
    identity = load_json(inputs / "SOURCE_CONTRACT_IDENTITY.json")
    amendment = load_json(amendment_path)

    if sha256_file(amendment_path) != AMENDMENT_SHA256:
        raise RuntimeError("binding_amendment_digest_mismatch")
    if amendment.get("schema_id") != AMENDMENT_SCHEMA or amendment.get("task_id") != TASK_ID:
        raise RuntimeError("binding_amendment_identity_mismatch")
    if source_path.stat().st_size != SOURCE_CONTRACT_BYTES or sha256_file(source_path) != SOURCE_CONTRACT_SHA256:
        raise RuntimeError("source_contract_identity_mismatch")
    if identity.get("source_contract", {}).get("sha256") != SOURCE_CONTRACT_SHA256:
        raise RuntimeError("source_contract_broker_identity_mismatch")
    if identity.get("amendment_sha256") != AMENDMENT_SHA256:
        raise RuntimeError("binding_amendment_broker_identity_mismatch")

    manifest = load_json(source_path)
    corrected = amendment["corrected_binding"]
    expected_artifact = corrected["source_artifact"]
    expected_targets = corrected["target_symbols"]
    target_symbols = sorted(expected_targets)

    declared_symbols = manifest.get("symbols")
    root_symbol_binding = isinstance(declared_symbols, list) and all(symbol in declared_symbols for symbol in target_symbols)

    artifacts = manifest.get("artifacts")
    actual_artifact = artifacts.get(expected_artifact["name"]) if isinstance(artifacts, dict) else None
    source_artifact_binding = (
        isinstance(actual_artifact, dict)
        and actual_artifact.get("sha256") == expected_artifact["sha256"]
        and actual_artifact.get("rows") == expected_artifact["rows"]
    )

    parent_dataset_binding = manifest.get("canonical_1m_parent_dataset_version") == corrected["canonical_1m_parent_dataset_version"]
    matching_views = _matching_views(manifest, expected_targets)
    view_binding_unique = len(matching_views) == 1

    valid = bool(root_symbol_binding and source_artifact_binding and parent_dataset_binding and view_binding_unique)
    overlap_start = max(row["first_trading_day"] for row in expected_targets.values()) if valid else None
    overlap_end = min(row["last_trading_day"] for row in expected_targets.values()) if valid else None
    current_snapshot_covers_full_window = bool(
        valid
        and overlap_start is not None
        and overlap_end is not None
        and overlap_start <= FUTURE_START
        and overlap_end >= FUTURE_END
    )

    return {
        "schema_id": SCHEMA_ID,
        "task_id": TASK_ID,
        "profile": PROFILE,
        "amendment_sha256": AMENDMENT_SHA256,
        "original_prereg_sha256": amendment["original_preregistration"]["sha256"],
        "status": "SOURCE_FAMILY_BINDING_VALID" if valid else "SOURCE_FAMILY_BINDING_INVALID",
        "source_contract": identity["source_contract"],
        "source_artifact": {
            "name": expected_artifact["name"],
            "sha256": expected_artifact["sha256"],
            "rows": expected_artifact["rows"],
            "binding_valid": bool(source_artifact_binding),
        },
        "canonical_1m_parent_dataset_version": corrected["canonical_1m_parent_dataset_version"],
        "parent_dataset_binding_valid": bool(parent_dataset_binding),
        "declared_target_symbols_present": bool(root_symbol_binding),
        "target_symbols": expected_targets,
        "matching_view_indexes": matching_views,
        "view_binding_unique": bool(view_binding_unique),
        "pair_overlap": {"min_trading_day": overlap_start, "max_trading_day": overlap_end},
        "future_oos_window": {
            "start_inclusive": FUTURE_START,
            "end_inclusive": FUTURE_END,
            "current_snapshot_covers_full_window": current_snapshot_covers_full_window,
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


def run(inputs: Path, out: Path) -> dict:
    if out.exists():
        raise RuntimeError("output_directory_already_exists")
    result = build_result(inputs)
    out.mkdir(parents=True)
    (out / "BINDING_AUDIT.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.inputs.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
