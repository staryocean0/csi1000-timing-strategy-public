"""Trusted validator for Overnight carrier materialization."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

YEARS = tuple(range(2015, 2021))
WITHHELD = [2021, 2022, 2023, 2024, 2025]


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("json_object_required")
    return value


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def expected_records(external: Path) -> list[dict]:
    runtime = read_json(external / "data/runtime_text_2015_2025/manifest.json")
    driver = read_json(external / "data/driver_runtime_text_2015_2020/manifest.json")
    if runtime.get("schema_id") != "overnight_runtime_text_carrier@1.0":
        raise ValueError("runtime_manifest_identity")
    if runtime.get("published_year_window") != [2015, 2020] or runtime.get("withheld_years") != WITHHELD:
        raise ValueError("runtime_boundary")
    if driver.get("schema_id") != "overnight_driver_runtime_text_2015_2020@1.0":
        raise ValueError("driver_manifest_identity")
    if driver.get("withheld_years") != WITHHELD or driver.get("blackbox_opened") is not False:
        raise ValueError("driver_boundary")
    records = []
    outputs = runtime.get("outputs", {})
    for family, stem in (("factor_panel", "factor_panel"), ("opening_clocks", "opening_clocks")):
        rows = outputs.get(family, {})
        if set(rows) != {str(y) for y in YEARS}:
            raise ValueError("runtime_year_set")
        for year in YEARS:
            meta = rows[str(year)]
            path = f"data/runtime_text_2015_2025/{stem}_{year}.csv"
            if meta.get("path") != path:
                raise ValueError("runtime_file_identity")
            records.append({"path": path, "bytes": meta["bytes"], "sha256": meta["sha256"]})
    rows = driver.get("outputs", {})
    if set(rows) != {str(y) for y in YEARS}:
        raise ValueError("driver_year_set")
    for year in YEARS:
        meta = rows[str(year)]
        path = f"data/driver_runtime_text_2015_2020/driver_external_{year}.csv"
        if meta.get("path") != path:
            raise ValueError("driver_file_identity")
        records.append({"path": path, "bytes": meta["bytes"], "sha256": meta["sha256"]})
    return records


def validate(inputs: Path, results: Path) -> dict:
    source = read_json(inputs / "source_manifest.json")
    if source.get("schema_id") != "csi1000.overnight_carrier_source_manifest@1.0":
        raise ValueError("source_manifest_identity")
    if source.get("required_years") != list(YEARS) or source.get("withheld_years") != WITHHELD:
        raise ValueError("source_year_boundary")
    package = read_json(inputs / "private_authority/package_scope.json")
    bindings = read_json(inputs / "private_authority/component_bindings_v1.json")
    if package.get("production_authority") is not False or bindings.get("production_authority") is not False:
        raise ValueError("authority_scope_drift")
    components = {item.get("component_id"): item for item in bindings.get("validated_components", []) if isinstance(item, dict)}
    for name in ("OFP-B1", "OFP-B2", "OFP-B4"):
        if components.get(name, {}).get("scientific_status") != "PASS":
            raise ValueError("validated_component_missing")

    external = inputs / "external"
    records = expected_records(external)
    if len(records) != 18:
        raise ValueError("carrier_file_count")
    expected_files = {
        "overnight_carrier_materialization.json",
        "carrier/source_manifest.json",
        "carrier/data/runtime_text_2015_2025/manifest.json",
        "carrier/data/driver_runtime_text_2015_2020/manifest.json",
    }
    expected_files.update("carrier/" + row["path"] for row in records)
    actual_files = set()
    for path in results.rglob("*"):
        if path.is_file():
            actual_files.add(path.relative_to(results).as_posix())
    if actual_files != expected_files:
        raise ValueError("unexpected_result_file_set")
    for row in records:
        path = results / "carrier" / row["path"]
        if path.stat().st_size != row["bytes"] or sha256_file(path) != row["sha256"]:
            raise ValueError("materialized_digest_mismatch")
    if (results / "carrier/source_manifest.json").read_bytes() != (inputs / "source_manifest.json").read_bytes():
        raise ValueError("source_manifest_copy_mismatch")

    receipt = read_json(results / "overnight_carrier_materialization.json")
    if receipt.get("schema_id") != "csi1000.overnight_carrier_materialization@1.0" or receipt.get("status") != "passed":
        raise ValueError("receipt_identity")
    if receipt.get("files") != sorted(records, key=lambda row: row["path"]):
        raise ValueError("receipt_file_manifest")
    if receipt.get("materialized_file_count") != 18 or receipt.get("all_required_families_present") is not True:
        raise ValueError("receipt_carrier_status")
    for key in ("blackbox_window_opened", "outcome_analysis_executed", "training_executed", "strategy_replayed", "scientific_change", "production_authority"):
        if receipt.get(key) is not False:
            raise ValueError("scope_violation")
    if receipt.get("source_repository_role") != "fixed_historical_carrier_source_only_not_control_plane":
        raise ValueError("source_role_drift")
    return {
        "status": "passed",
        "schema_id": "csi1000.overnight_carrier_materialization_validator@1.0",
        "materialized_file_count": 18,
        "blackbox_window_opened": False,
        "outcome_analysis_executed": False,
        "training_executed": False,
        "production_authority": False
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.inputs, args.results), sort_keys=True))


if __name__ == "__main__":
    main()
