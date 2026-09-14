"""Trusted validator for the metadata-only Overnight handoff inventory."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCHEMA_ID = "csi1000.overnight_official_snapshot_inventory@1.0"
OFFICIAL_SNAPSHOT_ID = "d113b42dca967bb1061c8a6115c5d934e5a41074"
STATUS_VALUES = {"PRESENT", "ABSENT", "AMBIGUOUS_FROM_NAMES_ONLY"}
CARRIER_KEYS = {
    "csi1000_gap_and_opening_clock",
    "rvol20_source",
    "b1_global_risk_source",
    "b2_china_offshore_source",
    "b4_driver_coherence_source",
}
TOP_KEYS = {
    "schema_id",
    "official_snapshot_id",
    "status",
    "bundle_file_count",
    "bundle_declared_bytes",
    "matched_files",
    "carrier_family_status",
    "all_required_families_present",
    "outcome_rows_read",
    "market_data_files_opened",
    "training_executed",
    "strategy_replayed",
    "production_authority",
}
FORBIDDEN_KEY_FRAGMENTS = {
    "return",
    "score",
    "probability",
    "target_value",
    "gap_value",
    "event_date",
    "row_count",
    "year_breakdown",
    "quarter_breakdown",
    "label",
    "prediction",
}


def fail(code: str) -> None:
    print(code, file=sys.stderr)
    raise SystemExit(1)


def validate(value: object) -> None:
    if not isinstance(value, dict) or set(value) != TOP_KEYS:
        fail("inventory_schema")
    if value["schema_id"] != SCHEMA_ID or value["official_snapshot_id"] != OFFICIAL_SNAPSHOT_ID or value["status"] != "passed":
        fail("inventory_identity")
    if type(value["bundle_file_count"]) is not int or value["bundle_file_count"] <= 0:
        fail("inventory_counts")
    if type(value["bundle_declared_bytes"]) is not int or value["bundle_declared_bytes"] <= 0:
        fail("inventory_counts")
    if value["outcome_rows_read"] != 0 or value["market_data_files_opened"] != 0:
        fail("outcome_read_forbidden")
    if value["training_executed"] is not False or value["strategy_replayed"] is not False or value["production_authority"] is not False:
        fail("scope_forbidden")
    carriers = value["carrier_family_status"]
    if not isinstance(carriers, dict) or set(carriers) != CARRIER_KEYS or not set(carriers.values()).issubset(STATUS_VALUES):
        fail("carrier_status_schema")
    if value["all_required_families_present"] is not all(v == "PRESENT" for v in carriers.values()):
        fail("carrier_summary")
    matched = value["matched_files"]
    if not isinstance(matched, list) or len(matched) > 2000:
        fail("matched_files_schema")
    prior = None
    for item in matched:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
            fail("matched_file_schema")
        path, size, digest = item["path"], item["bytes"], item["sha256"]
        if not isinstance(path, str) or not path or path.startswith("/") or ".." in Path(path).parts or "\\" in path:
            fail("matched_file_path")
        if type(size) is not int or size < 0:
            fail("matched_file_size")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            fail("matched_file_digest")
        if prior is not None and path <= prior:
            fail("matched_file_order")
        prior = path

    def walk(node):
        if isinstance(node, dict):
            for key, child in node.items():
                low = str(key).lower()
                if any(fragment in low for fragment in FORBIDDEN_KEY_FRAGMENTS):
                    fail("forbidden_output_key")
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)


def main() -> None:
    root = Path("/results")
    expected = root / "study" / "overnight_inventory.json"
    if not expected.is_file():
        fail("inventory_missing")
    allowed = {
        "study/overnight_inventory.json",
        "compute.log",
        "compute_receipt.json",
        "container.log",
    }
    actual = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}
    # Controller validation files are added after this validator runs, so they are not expected here.
    if actual != allowed:
        fail("unexpected_result_file")
    try:
        value = json.loads(expected.read_text())
    except Exception:
        fail("inventory_json")
    validate(value)
    print(json.dumps({"status": "passed", "inventory_schema": SCHEMA_ID}, sort_keys=True))


if __name__ == "__main__":
    main()
