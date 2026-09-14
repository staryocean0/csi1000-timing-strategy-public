"""Metadata-only inventory of the fixed CSI1000 handoff bundle for official Overnight carriers."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path, PurePosixPath

SCHEMA_ID = "csi1000.overnight_official_snapshot_inventory@1.0"
OFFICIAL_SNAPSHOT_ID = "d113b42dca967bb1061c8a6115c5d934e5a41074"
MANIFEST_NAME = "BUNDLE_MANIFEST.json"
DEV_YEARS = tuple(range(2015, 2021))
ALLOWED_PREFIXES = (
    "runtime/research/cloud_imports/overnight_open_context/",
    "data/runtime_text_2015_2025/",
    "data/driver_runtime_text_2015_2020/",
    "data/development/",
    "data/high_open_dev_2015_2025/",
    "data/v6a_external_sources_2015_2025/",
)
ALLOWED_TOKENS = (
    "overnight",
    "opening_clocks",
    "factor_panel",
    "driver_external",
    "high_open",
    "v6a",
)
STATUS_VALUES = {"PRESENT", "ABSENT", "AMBIGUOUS_FROM_NAMES_ONLY"}


def _safe_name(name: str) -> str:
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or ".." in path.parts or "\\" in name:
        raise ValueError("unsafe_manifest_path")
    normalized = str(path)
    if normalized != name:
        raise ValueError("noncanonical_manifest_path")
    return normalized


def _valid_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _manifest(bundle: Path) -> dict:
    with tarfile.open(bundle, "r:") as archive:
        members = archive.getmembers()
        regular = [m for m in members if m.isfile()]
        if any(m.isdir() is False and m.isfile() is False for m in members):
            raise ValueError("nonregular_bundle_member")
        names = [m.name for m in regular]
        if len(names) != len(set(names)):
            raise ValueError("duplicate_bundle_member")
        matches = [m for m in regular if m.name == MANIFEST_NAME]
        if len(matches) != 1:
            raise ValueError("bundle_manifest_identity")
        manifest_member = matches[0]
        if manifest_member.size <= 0 or manifest_member.size > 16 * 1024 * 1024:
            raise ValueError("bundle_manifest_size")
        stream = archive.extractfile(manifest_member)
        if stream is None:
            raise ValueError("bundle_manifest_unreadable")
        raw = stream.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError("bundle_manifest_size")
    try:
        value = json.loads(raw)
    except Exception as exc:
        raise ValueError("bundle_manifest_json") from exc
    if not isinstance(value, dict) or value.get("schema") != "csi1000_handoff_bundle@1":
        raise ValueError("bundle_manifest_schema")
    files = value.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("bundle_manifest_files")
    return value


def _approved_path(name: str) -> bool:
    lower = name.lower()
    return any(lower.startswith(prefix) for prefix in ALLOWED_PREFIXES) or any(token in lower for token in ALLOWED_TOKENS)


def _year_set(paths: list[str], stem: str) -> set[int]:
    found = set()
    pattern = re.compile(rf"(?:^|/){re.escape(stem)}_(20[0-9]{{2}})\.csv$")
    for name in paths:
        match = pattern.search(name.lower())
        if match:
            found.add(int(match.group(1)))
    return found


def _status_all_years(years: set[int]) -> str:
    required = set(DEV_YEARS)
    if required.issubset(years):
        return "PRESENT"
    if years:
        return "AMBIGUOUS_FROM_NAMES_ONLY"
    return "ABSENT"


def _carrier_status(all_paths: list[str]) -> dict[str, str]:
    factor_years = _year_set(all_paths, "factor_panel")
    clock_years = _year_set(all_paths, "opening_clocks")
    driver_years = _year_set(all_paths, "driver_external")
    required = set(DEV_YEARS)

    if required.issubset(factor_years) and required.issubset(clock_years):
        gap_clock = "PRESENT"
    elif factor_years or clock_years:
        gap_clock = "AMBIGUOUS_FROM_NAMES_ONLY"
    else:
        gap_clock = "ABSENT"

    # Exact factor_panel naming proves the historical frozen runtime carrier family exists,
    # but names alone do not prove its column schema for B1/rvol20.
    rvol20 = "AMBIGUOUS_FROM_NAMES_ONLY" if factor_years else "ABSENT"
    b1 = "AMBIGUOUS_FROM_NAMES_ONLY" if factor_years else "ABSENT"
    b2 = _status_all_years(driver_years)
    if b2 == "PRESENT":
        b2 = "AMBIGUOUS_FROM_NAMES_ONLY"
    b4 = "AMBIGUOUS_FROM_NAMES_ONLY" if factor_years and driver_years else (
        "ABSENT" if not factor_years and not driver_years else "AMBIGUOUS_FROM_NAMES_ONLY"
    )

    result = {
        "csi1000_gap_and_opening_clock": gap_clock,
        "rvol20_source": rvol20,
        "b1_global_risk_source": b1,
        "b2_china_offshore_source": b2,
        "b4_driver_coherence_source": b4,
    }
    if not set(result.values()).issubset(STATUS_VALUES):
        raise AssertionError("unexpected_status")
    return result


def build_inventory(bundle: Path) -> dict:
    manifest = _manifest(bundle)
    files = manifest["files"]
    rows = []
    total_bytes = 0
    all_paths = []
    for raw_name, meta in files.items():
        if not isinstance(raw_name, str):
            raise ValueError("manifest_path_type")
        name = _safe_name(raw_name)
        all_paths.append(name)
        if not isinstance(meta, dict) or set(meta) != {"bytes", "sha256"}:
            raise ValueError("manifest_file_metadata")
        size = meta["bytes"]
        digest = meta["sha256"]
        if type(size) is not int or size < 0 or not _valid_digest(digest):
            raise ValueError("manifest_file_metadata")
        total_bytes += size
        if _approved_path(name):
            rows.append({"path": name, "bytes": size, "sha256": digest})
    rows.sort(key=lambda item: item["path"])

    carriers = _carrier_status(all_paths)
    result = {
        "schema_id": SCHEMA_ID,
        "official_snapshot_id": OFFICIAL_SNAPSHOT_ID,
        "status": "passed",
        "bundle_file_count": len(files),
        "bundle_declared_bytes": total_bytes,
        "matched_files": rows,
        "carrier_family_status": carriers,
        "all_required_families_present": all(value == "PRESENT" for value in carriers.values()),
        "outcome_rows_read": 0,
        "market_data_files_opened": 0,
        "training_executed": False,
        "strategy_replayed": False,
        "production_authority": False,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("output_already_exists")
    args.out.mkdir(parents=True)
    inventory = build_inventory(args.inputs / "bundle.tar")
    target = args.out / "overnight_inventory.json"
    target.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
