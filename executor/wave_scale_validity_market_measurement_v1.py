"""Label-blind validity-feature market measurement for issue #376."""
from __future__ import annotations

import hashlib
import json
import math
import numpy as np

from wave_scale_reference_packet_v2 import (
    qualify_frames, _common_sequence, anchor_context_eligible_days,
    _anchor_index, _context,
)
from wave_scale_reference_sampling_v2 import select_primary_days, blinded_inventory
from wave_segmentation_carrier_qualification_v1 import bucket_members
from wave_scale_validity_diagnostics_v1 import measure_validity

EXPECTED_BLIND_SHA = "5ab33685531475b3ad6cf4f69590c0af0925836679043d24ce2a44127ab7d4d1"
EXPECTED_ELIGIBLE = 1414
EXPECTED_EXCLUSIONS = {"context_causal_flat_fill": 43, "context_support": 1}


def _encode(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _phase_rows(frames, context300):
    relative = {stamp: int(rel) for stamp, rel in zip(context300["audit_utc"], context300["relative_minute"])}
    allowed = {(str(day), int(minute)) for day, minute in zip(context300["audit_day"], context300["audit_minute"])}
    out = {}
    for offset in range(5):
        name = f"5m_offset_{offset}.parquet"
        rows = []
        for _, row in frames[name].loc[frames[name]["audit_utc"].isin(relative)].iterrows():
            members = bucket_members(offset, int(row["audit_minute"]))
            day = str(row["audit_day"])
            if members is None or any((day, int(m)) not in allowed for m in members):
                continue
            values = (float(row["low"]), float(row["close"]), float(row["high"]))
            if not all(math.isfinite(v) and v > 0 for v in values):
                raise ValueError("phase_price")
            if not values[0] <= values[1] <= values[2]:
                raise ValueError("phase_order")
            rows.append((relative[row["audit_utc"]], *values))
        rows = sorted(rows)
        if len(rows) < 6 or len({r[0] for r in rows}) != len(rows):
            raise ValueError("phase_support:" + name)
        out[f"offset{offset}"] = rows
    return out


def build_validity_measurement(raw_frames, declared_rows):
    frames, common, _ = qualify_frames(raw_frames, declared_rows)
    sequence = _common_sequence(frames["1m_official.parquet"], common)
    eligible, exclusions = anchor_context_eligible_days(frames, sequence, common)
    if len(eligible) != EXPECTED_ELIGIBLE or exclusions != EXPECTED_EXCLUSIONS:
        raise ValueError("anchor_eligibility_identity")
    full = select_primary_days(sorted(eligible))
    blind = blinded_inventory(full)
    blind_raw = _encode(blind)
    if hashlib.sha256(blind_raw).hexdigest() != EXPECTED_BLIND_SHA:
        raise ValueError("blind_inventory_identity")
    by_panel = {row["panel_id"]: row for row in full}
    output = []
    for blind_row in blind:
        row = by_panel[blind_row["panel_id"]]
        idx = _anchor_index(sequence, row["day"], row["anchor"])
        context = _context(sequence, idx, 300)
        evidence = measure_validity(
            context["close"].to_numpy(float),
            context["relative_minute"].to_numpy(int),
            _phase_rows(frames, context),
        )
        output.append({"panel_id": row["panel_id"], "validity": evidence})
    if len(output) != 192 or len({row["panel_id"] for row in output}) != 192:
        raise ValueError("measurement_cardinality")
    diagnostics_raw = b"".join(_encode(row) for row in output)
    summary = {
        "schema_id": "csi1000.scale_validity_market_measurement@1.0",
        "research_issue": 376,
        "parent_issue": 353,
        "status": "RAW_VALIDITY_DIAGNOSTICS_FROZEN_LABEL_BLIND",
        "population_role": "PREVIOUSLY_CONSUMED_DEVELOPMENT_REFERENCE_ONLY",
        "panels": 192,
        "anchor_context_eligible_days": len(eligible),
        "anchor_context_exclusions": exclusions,
        "blind_inventory_sha256": EXPECTED_BLIND_SHA,
        "validity_diagnostics_sha256": hashlib.sha256(diagnostics_raw).hexdigest(),
        "reference_labels_visible_to_compute": False,
        "reference_labels_joined": False,
        "future_suffix_used": False,
        "validity_state_assigned": False,
        "numeric_validity_thresholds": None,
        "outcomes_used": False,
        "R4_selected": False,
        "one_minute_strategy_admitted": False,
        "router_pnl": False,
        "production_authority": False,
    }
    return {
        "validity_diagnostics.jsonl": diagnostics_raw,
        "validity_summary.json": _encode(summary),
    }


def result_manifest(files: dict[str, bytes]) -> bytes:
    meta = {name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name, raw in sorted(files.items())}
    return _encode({
        "schema_id": "csi1000.scale_validity_market_manifest@1.0",
        "files": meta,
        "reference_labels_visible_to_compute": False,
        "threshold_selected": False,
        "production_authority": False,
    })
