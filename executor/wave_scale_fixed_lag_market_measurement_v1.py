"""Issue #386 label-blind fixed-lag confirmation measurement."""
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
from wave_scale_fixed_lag_confirmation_v1 import (
    LAG_MINUTES, measure_validity_confirmation, measure_morphology_confirmation,
)
from wave_scale_diagnostic_family_v2 import measure_validity_v2, measure_morphology_v2

EXPECTED_BLIND_SHA = "5ab33685531475b3ad6cf4f69590c0af0925836679043d24ce2a44127ab7d4d1"
EXPECTED_LAG0_SHA = "a0b71c19591a83bf2ee7cc24eaecaea367d0d3b3772a0e41c03d7c361b5fa659"
EXPECTED_ELIGIBLE = 1414
EXPECTED_EXCLUSIONS = {"context_causal_flat_fill": 43, "context_support": 1}
PHASES = tuple(f"offset{i}" for i in range(5))


def _encode(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def confirmation_context(sequence, index, lag):
    if lag not in LAG_MINUTES or index - 299 < 0 or index + lag >= len(sequence):
        raise ValueError("confirmation_context_support")
    part = sequence.iloc[index - 299:index + lag + 1].copy()
    if len(part) != 300 + lag:
        raise ValueError("confirmation_context_length")
    suffix = part.iloc[299:]
    if len(suffix) != lag + 1:
        raise ValueError("confirmation_suffix_length")
    if len(set(str(x) for x in suffix["audit_day"])) != 1:
        raise ValueError("confirmation_suffix_cross_day")
    minutes = suffix["audit_minute"].to_numpy(int)
    if len(minutes) > 1 and not np.all(np.diff(minutes) == 1):
        raise ValueError("confirmation_suffix_noncontiguous")
    if bool(part["causal_flat_fill"].any()):
        raise ValueError("confirmation_causal_flat_fill")
    if not bool(part["high_frequency_analysis_eligible"].all()):
        raise ValueError("confirmation_ineligible")
    part["relative_minute"] = np.arange(-299, lag + 1, dtype=int)
    return part


def _phase_rows(frames, context):
    relative = {stamp: int(rel) for stamp, rel in zip(context["audit_utc"], context["relative_minute"])}
    allowed = {(str(day), int(minute)) for day, minute in zip(context["audit_day"], context["audit_minute"])}
    ohlc, close = {}, {}
    for offset in range(5):
        name = f"5m_offset_{offset}.parquet"
        rows_ohlc, rows_close = [], []
        for _, row in frames[name].loc[frames[name]["audit_utc"].isin(relative)].iterrows():
            members = bucket_members(offset, int(row["audit_minute"]))
            day = str(row["audit_day"])
            if members is None or any((day, int(m)) not in allowed for m in members):
                continue
            values = (float(row["low"]), float(row["close"]), float(row["high"]))
            if not all(math.isfinite(v) and v > 0 for v in values) or not values[0] <= values[1] <= values[2]:
                raise ValueError("phase_price")
            rel = relative[row["audit_utc"]]
            rows_ohlc.append((rel, *values))
            rows_close.append((rel, values[1]))
        rows_ohlc = sorted(rows_ohlc)
        rows_close = sorted(rows_close)
        if len(rows_close) < 6 or len({r[0] for r in rows_close}) != len(rows_close):
            raise ValueError("phase_support:" + name)
        ohlc[f"offset{offset}"] = rows_ohlc
        close[f"offset{offset}"] = rows_close
    return ohlc, close


def _lag_name(lag):
    return f"fixed_lag_{lag:03d}.jsonl"


def build_measurement(raw_frames, declared_rows):
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
    outputs = {lag: [] for lag in LAG_MINUTES}
    support = {str(lag): 0 for lag in LAG_MINUTES}
    for blind_row in blind:
        row = by_panel[blind_row["panel_id"]]
        idx = _anchor_index(sequence, row["day"], row["anchor"])
        base = _context(sequence, idx, 300)
        base_ohlc, _ = _phase_rows(frames, base)
        for lag in LAG_MINUTES:
            knowledge = confirmation_context(sequence, idx, lag)
            _, knowledge_close = _phase_rows(frames, knowledge)
            validity = measure_validity_confirmation(
                base["close"].to_numpy(float),
                base["relative_minute"].to_numpy(int),
                base_ohlc,
                knowledge["close"].to_numpy(float),
                knowledge["relative_minute"].to_numpy(int),
            )
            morphology = measure_morphology_confirmation(knowledge_close)
            if lag == 0:
                legacy_validity = measure_validity_v2(
                    base["close"].to_numpy(float),
                    base["relative_minute"].to_numpy(int),
                    base_ohlc,
                )
                legacy_morphology = measure_morphology_v2(knowledge_close)
                if validity != legacy_validity or morphology != legacy_morphology:
                    raise ValueError("lag0_source_semantic_mismatch")
            outputs[lag].append({
                "panel_id": row["panel_id"],
                "validity_v2": validity,
                "morphology_v2": morphology,
            })
            support[str(lag)] += 1
    files = {}
    hashes = {}
    for lag in LAG_MINUTES:
        if len(outputs[lag]) != 192 or len({r["panel_id"] for r in outputs[lag]}) != 192:
            raise ValueError("measurement_cardinality")
        raw = b"".join(_encode(row) for row in outputs[lag])
        files[_lag_name(lag)] = raw
        hashes[str(lag)] = hashlib.sha256(raw).hexdigest()
    summary = {
        "schema_id": "csi1000.scale_fixed_lag_confirmation_measurement@1.0",
        "research_issue": 386,
        "parent_issue": 381,
        "root_issue": 353,
        "status": "RAW_FIXED_LAG_CONFIRMATION_FAMILY_FROZEN_LABEL_BLIND",
        "population_role": "ITERATIVE_DEVELOPMENT_REFERENCE_NOT_FRESH_OOS",
        "panels": 192,
        "lag_minutes": list(LAG_MINUTES),
        "lag_phase_bars": [0, 1, 2, 3, 5],
        "panel_lag_rows": 192 * len(LAG_MINUTES),
        "phase_rows": 192 * len(LAG_MINUTES) * 5,
        "support_by_lag": support,
        "blind_inventory_sha256": EXPECTED_BLIND_SHA,
        "lag_diagnostics_sha256": hashes,
        "frozen_v2_reference_diagnostics_sha256": EXPECTED_LAG0_SHA,
        "lag0_source_semantics_exact_same_runtime": True,
        "cross_platform_raw_byte_identity_required": False,
        "occurrence_time_relative_minute": 0,
        "candidate_event_must_be_at_or_before_occurrence": True,
        "occurrence_relative_suffix_used_for_nonzero_lags": True,
        "knowledge_time_future_data_used": False,
        "reference_labels_visible_to_compute": False,
        "reference_labels_joined": False,
        "threshold_selection_in_run": False,
        "validity_state_assigned": False,
        "morphology_state_assigned": False,
        "dominance_v1_remeasured": False,
        "outcomes_used": False,
        "R4_selected": False,
        "router_pnl": False,
        "production_authority": False,
    }
    files["fixed_lag_summary.json"] = _encode(summary)
    return files


def result_manifest(files):
    meta = {name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name, raw in sorted(files.items())}
    return _encode({
        "schema_id": "csi1000.scale_fixed_lag_confirmation_manifest@1.0",
        "files": meta,
        "reference_labels_visible_to_compute": False,
        "threshold_selected": False,
        "production_authority": False,
    })
