"""Deterministically materialize fixed 2015-2020 Overnight carriers into a private result archive.

This runner performs byte-level verification and copying only. It does not fit models,
score outcomes, inspect 2021-2025 rows, or use the historical source repository as a
control plane.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath

SCHEMA_ID = "csi1000.overnight_carrier_materialization@1.0"
SOURCE_SCHEMA = "csi1000.overnight_carrier_source_manifest@1.0"
RUNTIME_SCHEMA = "overnight_runtime_text_carrier@1.0"
DRIVER_SCHEMA = "overnight_driver_runtime_text_2015_2020@1.0"
YEARS = tuple(range(2015, 2021))
WITHHELD = [2021, 2022, 2023, 2024, 2025]
REQUIRED_COMPONENTS = {"OFP-B1", "OFP-B2", "OFP-B4"}
CARRIER_STATUS = {
    "csi1000_gap_and_opening_clock": "PRESENT",
    "rvol20_source": "PRESENT",
    "b1_global_risk_source": "PRESENT",
    "b2_china_offshore_source": "PRESENT",
    "b4_driver_coherence_source": "PRESENT",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def safe_rel(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or "\\" in value or str(path) != value:
        raise ValueError("unsafe_source_path")
    return value


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("json_object_required")
    return value


def verify_private_authority(root: Path, source: dict) -> None:
    package = read_json(root / "private_authority" / "package_scope.json")
    bindings = read_json(root / "private_authority" / "component_bindings_v1.json")
    if package.get("schema_id") != "overnight_open_cloud_theme_package_scope@1.1":
        raise ValueError("package_scope_schema")
    if package.get("production_authority") is not False:
        raise ValueError("package_scope_authority_drift")
    if "CSI1000_2015_2020_runtime_text_carrier" not in package.get("included", []):
        raise ValueError("runtime_carrier_not_in_official_scope")
    packs = package.get("data_packs", {})
    if packs.get("runtime_text_2015_2025") != "data/runtime_text_2015_2025":
        raise ValueError("runtime_pack_path_drift")
    if bindings.get("schema_id") != "overnight_component_bindings@1.0" or bindings.get("production_authority") is not False:
        raise ValueError("component_binding_schema")
    found = {}
    for item in bindings.get("validated_components", []):
        if isinstance(item, dict) and item.get("component_id") in REQUIRED_COMPONENTS:
            found[item["component_id"]] = item
    if set(found) != REQUIRED_COMPONENTS:
        raise ValueError("required_component_binding_missing")
    if any(item.get("scientific_status") != "PASS" or item.get("production_authority") is not False for item in found.values()):
        raise ValueError("required_component_not_validated")
    private = source.get("private_authority", {})
    if private.get("official_snapshot_id") != "d113b42dca967bb1061c8a6115c5d934e5a41074":
        raise ValueError("official_snapshot_identity")


def verify_runtime_manifest(value: dict) -> list[dict]:
    if value.get("schema_id") != RUNTIME_SCHEMA or value.get("instrument") != "000852.SH":
        raise ValueError("runtime_manifest_identity")
    if value.get("published_year_window") != [2015, 2020] or value.get("withheld_years") != WITHHELD:
        raise ValueError("runtime_evidence_boundary")
    if value.get("years") != list(YEARS) or value.get("production_authority") is not False:
        raise ValueError("runtime_year_identity")
    transform = value.get("transform", {})
    forbidden_true = ("scientific_change", "forward_fill", "backward_fill", "resampling", "feature_engineering", "nearest_clock_match")
    if any(transform.get(key) is not False for key in forbidden_true):
        raise ValueError("runtime_transform_drift")
    factor_columns = set(value.get("factor_panel_columns", []))
    if not {"trading_day", "gap", "rvol20", "us_nasdaq", "us_vix_chg"}.issubset(factor_columns):
        raise ValueError("runtime_factor_schema_missing")
    if value.get("clocks") != ["09:35", "09:50", "10:05", "10:35"]:
        raise ValueError("runtime_clock_drift")
    outputs = value.get("outputs", {})
    if set(outputs) != {"factor_panel", "opening_clocks"}:
        raise ValueError("runtime_output_family")
    records = []
    for family, stem in (("factor_panel", "factor_panel"), ("opening_clocks", "opening_clocks")):
        rows = outputs[family]
        if set(rows) != {str(y) for y in YEARS}:
            raise ValueError("runtime_year_set")
        for year in YEARS:
            meta = rows[str(year)]
            path = safe_rel(meta["path"])
            expected = f"data/runtime_text_2015_2025/{stem}_{year}.csv"
            if path != expected or type(meta.get("bytes")) is not int or meta["bytes"] <= 0:
                raise ValueError("runtime_file_identity")
            digest = meta.get("sha256")
            if not isinstance(digest, str) or len(digest) != 64:
                raise ValueError("runtime_file_digest")
            records.append({"path": path, "bytes": meta["bytes"], "sha256": digest})
    return records


def verify_driver_manifest(value: dict) -> list[dict]:
    if value.get("schema_id") != DRIVER_SCHEMA or value.get("instrument") != "000852.SH":
        raise ValueError("driver_manifest_identity")
    if value.get("published_window") != "2015-01-05..2020-12-31" or value.get("withheld_years") != WITHHELD:
        raise ValueError("driver_evidence_boundary")
    if value.get("blackbox_opened") is not False or value.get("production_authority") is not False:
        raise ValueError("driver_blackbox_boundary")
    transform = value.get("transform", {})
    if transform.get("scientific_change") is not False or transform.get("feature_selection_from_outcomes") is not False:
        raise ValueError("driver_transform_drift")
    if transform.get("2021_2025_row_level_text_generated") is not False:
        raise ValueError("driver_blackbox_text_exposure")
    columns = set(value.get("columns", []))
    if not {"trading_day", "a50_channel_return", "hkma_usdcny_closure_return"}.issubset(columns):
        raise ValueError("driver_schema_missing")
    outputs = value.get("outputs", {})
    if set(outputs) != {str(y) for y in YEARS}:
        raise ValueError("driver_year_set")
    records = []
    for year in YEARS:
        meta = outputs[str(year)]
        path = safe_rel(meta["path"])
        expected = f"data/driver_runtime_text_2015_2020/driver_external_{year}.csv"
        if path != expected or type(meta.get("bytes")) is not int or meta["bytes"] <= 0:
            raise ValueError("driver_file_identity")
        digest = meta.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("driver_file_digest")
        records.append({"path": path, "bytes": meta["bytes"], "sha256": digest})
    return records


def verify_source_files(external: Path, records: list[dict]) -> None:
    expected = {row["path"] for row in records}
    for path in external.rglob("*.csv"):
        rel = path.relative_to(external).as_posix()
        if rel not in expected:
            raise ValueError("unexpected_external_csv")
        if any(f"_{year}.csv" in rel for year in WITHHELD):
            raise ValueError("blackbox_window_file_present")
    for row in records:
        path = external / row["path"]
        if not path.is_file() or path.stat().st_size != row["bytes"] or sha256_file(path) != row["sha256"]:
            raise ValueError("external_carrier_digest_mismatch")


def materialize(inputs: Path, out: Path) -> dict:
    source = read_json(inputs / "source_manifest.json")
    if source.get("schema_id") != SOURCE_SCHEMA or source.get("required_years") != list(YEARS):
        raise ValueError("source_manifest_identity")
    if source.get("withheld_years") != WITHHELD or source.get("scientific_change") is not False:
        raise ValueError("source_manifest_boundary")
    if source.get("new_training") is not False or source.get("production_authority") is not False:
        raise ValueError("source_scope_violation")
    verify_private_authority(inputs, source)
    external = inputs / "external"
    runtime_path = external / "data/runtime_text_2015_2025/manifest.json"
    driver_path = external / "data/driver_runtime_text_2015_2020/manifest.json"
    runtime = read_json(runtime_path)
    driver = read_json(driver_path)
    records = verify_runtime_manifest(runtime) + verify_driver_manifest(driver)
    if len(records) != 18 or len({row["path"] for row in records}) != 18:
        raise ValueError("carrier_file_set")
    verify_source_files(external, records)

    if out.exists():
        raise ValueError("output_already_exists")
    carrier = out / "carrier"
    carrier.mkdir(parents=True)
    shutil.copyfile(inputs / "source_manifest.json", carrier / "source_manifest.json")
    for manifest in (runtime_path, driver_path):
        rel = manifest.relative_to(external)
        target = carrier / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(manifest, target)
    total = 0
    for row in records:
        source_path = external / row["path"]
        target = carrier / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
        if target.stat().st_size != row["bytes"] or sha256_file(target) != row["sha256"]:
            raise ValueError("materialized_carrier_digest_mismatch")
        total += row["bytes"]

    receipt = {
        "schema_id": SCHEMA_ID,
        "status": "passed",
        "external_repository": source["external_repository"],
        "external_ref": source["external_ref"],
        "private_ref": source["private_authority"]["private_ref"],
        "official_snapshot_id": source["private_authority"]["official_snapshot_id"],
        "years_materialized": list(YEARS),
        "withheld_years": WITHHELD,
        "materialized_file_count": len(records),
        "materialized_bytes": total,
        "files": sorted(records, key=lambda row: row["path"]),
        "carrier_family_status": CARRIER_STATUS,
        "all_required_families_present": True,
        "source_repository_role": "fixed_historical_carrier_source_only_not_control_plane",
        "blackbox_window_opened": False,
        "outcome_analysis_executed": False,
        "training_executed": False,
        "strategy_replayed": False,
        "scientific_change": False,
        "production_authority": False,
    }
    (out / "overnight_carrier_materialization.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    materialize(args.inputs, args.out)


if __name__ == "__main__":
    main()
