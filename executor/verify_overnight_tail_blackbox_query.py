#!/usr/bin/env python3
"""Trusted read-only validator for the frozen reusable Overnight tail BLACKBOX query."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_overnight_tail_blackbox_query", HERE / "overnight_tail_blackbox_query.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("blackbox_query_module_unavailable")
query = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(query)


def load_receipt(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("blackbox_receipt_invalid")
    allowed = {
        "schema_id", "query_id", "research_identity", "parent_model_artifact_id", "decision",
        "protocol_sha256", "source_ref", "source_file_blob_identities", "public_detail_release",
        "internal_metrics_persisted", "reused_period_is_independent_oos", "production_authority",
    }
    if set(value) != allowed:
        raise RuntimeError("blackbox_receipt_surface")
    if value.get("schema_id") != query.RECEIPT_SCHEMA or value.get("research_identity") != query.IDENTITY:
        raise RuntimeError("blackbox_receipt_identity")
    if value.get("decision") not in {"PASS", "FAIL", "INSUFFICIENT"}:
        raise RuntimeError("blackbox_receipt_decision")
    if value.get("public_detail_release") is not False or value.get("internal_metrics_persisted") is not False:
        raise RuntimeError("blackbox_receipt_scope")
    if value.get("reused_period_is_independent_oos") is not False or value.get("production_authority") is not False:
        raise RuntimeError("blackbox_receipt_scope")
    return value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", type=Path, required=True)
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--protocol", type=Path, required=True)
    ap.add_argument("--results", type=Path, required=True)
    args = ap.parse_args()
    try:
        expected = query.evaluate(args.source_root, args.model, args.protocol)
        actual = load_receipt(args.results / "blackbox_receipt.json")
        if actual != expected:
            raise RuntimeError("blackbox_receipt_mismatch")
    except Exception:
        print(json.dumps({"status": "failed", "production_authority": False}, sort_keys=True))
        return 1
    print(json.dumps({"status": "passed", "decision": actual["decision"], "production_authority": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
