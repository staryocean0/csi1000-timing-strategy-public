"""Scale-specific continuity candidate for the graphical hierarchy.

This module never rewrites the frozen base wave/pivot/reset ledger. It only
allows a higher-level pivot engine to consume chronologically confirmed low
nodes across lower-level root boundaries while preserving those boundaries
and resets as explicit metadata. No outcomes, target-period bands, or PnL.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math

import numpy as np

from wave_dual_gate_hierarchy_v1 import (
    base_inventory,
    hierarchy,
    pivot_stream,
    roots_from_waves,
    waves_from_pivots,
)
from wave_multiscale_dual_gates_v2 import amp, qsummary


def _canonical_base_digest(base):
    payload = {
        "pivots": [
            {k: p.get(k) for k in ("kind", "occurrence_bar", "known_from_bar", "epoch", "left_censored")}
            for p in base["pivots"]
        ],
        "resets": [
            {k: r.get(k) for k in ("known_from_bar", "epoch", "previous_pivot_index")}
            for r in base["resets"]
        ],
        "waves": [
            {
                k: w.get(k)
                for k in (
                    "start_bar",
                    "high_bar",
                    "end_bar",
                    "start_low",
                    "high",
                    "end_low",
                    "known_from_bar",
                    "epoch",
                    "wave_id",
                )
            }
            for w in base["waves"]
        ],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _event(event_id, kind, occurrence_bar, known_from_bar, source_level, **extra):
    if known_from_bar < occurrence_bar:
        raise ValueError("event known before occurrence")
    return dict(
        event_id=event_id,
        kind=kind,
        occurrence_bar=int(occurrence_bar),
        known_from_bar=int(known_from_bar),
        source_level=source_level,
        **extra,
    )


def _base_reset_events(base):
    return [
        _event(
            f"base-reset-{i}",
            "LOWER_RESET",
            r["known_from_bar"],
            r["known_from_bar"],
            "BASE",
            source_epoch=r["epoch"],
            previous_pivot_index=r["previous_pivot_index"],
        )
        for i, r in enumerate(base["resets"])
    ]


def _merge_events(*groups):
    out = {}
    for group in groups:
        for e in group:
            old = out.get(e["event_id"])
            if old is not None and old != e:
                raise ValueError("event id collision")
            out[e["event_id"]] = e
    return sorted(out.values(), key=lambda e: (e["occurrence_bar"], e["known_from_bar"], e["event_id"]))


def flatten_roots(roots, source_level):
    """Flatten confirmed low nodes across lower roots; never backdate a boundary."""
    roots = sorted(
        roots,
        key=lambda r: (r["nodes"][0]["occurrence_bar"], r["nodes"][0]["known_from_bar"], r["root_id"]),
    )
    raw = []
    boundaries = []
    previous_root = None
    for root in roots:
        nodes = root["nodes"]
        if not nodes:
            continue
        if previous_root is not None:
            first = nodes[0]
            boundaries.append(
                _event(
                    f"{source_level}-root-boundary-{len(boundaries)}",
                    "LOWER_ROOT_BOUNDARY",
                    first["occurrence_bar"],
                    first["known_from_bar"],
                    source_level,
                    from_root=previous_root["root_id"],
                    to_root=root["root_id"],
                )
            )
        for n in nodes:
            row = dict(n)
            row["source_root_id"] = root["root_id"]
            row["source_parent_id"] = root.get("parent_id")
            raw.append(row)
        previous_root = root

    # Adjacent roots can share the same low anchor. Merge conservatively at the
    # later knowledge time rather than duplicate an occurrence or backdate it.
    merged = []
    duplicates = 0
    for row in sorted(raw, key=lambda n: (n["occurrence_bar"], n["known_from_bar"], n["source_root_id"])):
        if merged and row["occurrence_bar"] == merged[-1]["occurrence_bar"]:
            if not math.isclose(float(row["price"]), float(merged[-1]["price"]), rel_tol=0, abs_tol=1e-12):
                raise ValueError("duplicate occurrence has conflicting price")
            merged[-1]["known_from_bar"] = max(merged[-1]["known_from_bar"], row["known_from_bar"])
            roots_seen = set(merged[-1].get("source_root_ids", [merged[-1]["source_root_id"]]))
            roots_seen.add(row["source_root_id"])
            merged[-1]["source_root_ids"] = sorted(roots_seen)
            duplicates += 1
            continue
        merged.append(dict(row))

    previous = None
    for i, row in enumerate(merged):
        row["index"] = i
        if previous is not None and (
            row["occurrence_bar"] <= previous["occurrence_bar"]
            or row["known_from_bar"] < previous["known_from_bar"]
        ):
            raise ValueError("flattened node clocks are not causal/order preserving")
        previous = row
    return merged, boundaries, duplicates


def _reset_events(resets, stream, source_level):
    events = []
    for i, r in enumerate(resets):
        candidates = [
            n
            for n in stream
            if n["known_from_bar"] == r["known_from_bar"] and n["index"] > r["previous_pivot_index"]
        ]
        if not candidates:
            candidates = [
                n
                for n in stream
                if n["known_from_bar"] >= r["known_from_bar"] and n["index"] > r["previous_pivot_index"]
            ]
        if not candidates:
            raise ValueError("cannot locate reset trigger node")
        n = candidates[0]
        events.append(
            _event(
                f"{source_level}-reset-{i}",
                "LOWER_RESET",
                n["occurrence_bar"],
                r["known_from_bar"],
                source_level,
                source_epoch=r["epoch"],
                previous_pivot_index=r["previous_pivot_index"],
            )
        )
    return events


def _events_in_span(events, start, end):
    return [e for e in events if start < e["occurrence_bar"] <= end]


def _annotate_waves(waves, lower_events):
    for w in waves:
        events = _events_in_span(lower_events, w["start_bar"], w["end_bar"])
        resets = [e for e in events if e["kind"] == "LOWER_RESET"]
        roots = [e for e in events if e["kind"] == "LOWER_ROOT_BOUNDARY"]
        w["lower_event_ids"] = [e["event_id"] for e in events]
        w["lower_boundary_count"] = len(events)
        w["lower_root_boundary_count"] = len(roots)
        w["lower_reset_count"] = len(resets)
        w["crosses_lower_reset"] = bool(resets)
        w["crosses_lower_root_boundary"] = bool(roots)
        w["first_lower_reset_bar"] = resets[0]["occurrence_bar"] if resets else None
        w["last_lower_reset_bar"] = resets[-1]["occurrence_bar"] if resets else None
        w["lower_reset_span_bars"] = (
            resets[-1]["occurrence_bar"] - resets[0]["occurrence_bar"]
            if len(resets) > 1
            else 0
            if resets
            else None
        )
    return waves


def _annotate_pivots(pivots, lower_events):
    last_by_epoch = {}
    for p in pivots:
        prev = last_by_epoch.get(p["epoch"])
        if prev is None:
            p["lower_reset_count_since_previous_pivot"] = None
            p["crosses_lower_reset_since_previous_pivot"] = None
        else:
            events = _events_in_span(lower_events, prev["occurrence_bar"], p["occurrence_bar"])
            n = sum(e["kind"] == "LOWER_RESET" for e in events)
            p["lower_reset_count_since_previous_pivot"] = n
            p["crosses_lower_reset_since_previous_pivot"] = bool(n)
        last_by_epoch[p["epoch"]] = p
    return pivots


def _stage(input_roots, inherited_events, level, minimum=1, maximum=24):
    stream, root_boundaries, duplicates = flatten_roots(input_roots, f"L{level-1}")
    lower_events = _merge_events(inherited_events, root_boundaries)
    if len(stream) < 2:
        pivots = []
        resets = []
        waves = []
    else:
        pivots, resets = pivot_stream(stream, minimum, maximum)
        pivots = _annotate_pivots(pivots, lower_events)
        waves = waves_from_pivots(pivots, f"continuity-L{level}")
        waves = _annotate_waves(waves, lower_events)
    roots = roots_from_waves(waves, resets, f"continuity-L{level}") if waves else []
    own_reset_events = _reset_events(resets, stream, f"L{level}") if resets else []
    events_for_next = _merge_events(lower_events, own_reset_events)
    return dict(
        level=level,
        input_roots=input_roots,
        stream=stream,
        root_boundaries=root_boundaries,
        duplicate_occurrences_merged=duplicates,
        lower_events=lower_events,
        pivots=pivots,
        resets=resets,
        waves=waves,
        roots=roots,
        events_for_next=events_for_next,
    )


def continuity_hierarchy(base, minimum=1, depth=3):
    stages = []
    roots = base["roots"]
    events = _base_reset_events(base)
    for level in range(1, depth + 1):
        s = _stage(roots, events, level, minimum, 24)
        stages.append(s)
        roots = s["roots"]
        events = s["events_for_next"]
    return dict(minimum=minimum, maximum=24, stages=stages)


def _contained_children(wave, children):
    return [x for x in children if x["start_bar"] >= wave["start_bar"] and x["end_bar"] <= wave["end_bar"]]


def _stage_ratios(stages, base):
    previous = base["waves"]
    out = []
    for s in stages:
        ratios = []
        for w in s["waves"]:
            c = _contained_children(w, previous)
            if not c:
                continue
            t = float(np.median([x["duration"] for x in c]))
            a = float(np.median([amp(x) for x in c]))
            ratios.append(dict(period_ratio=w["duration"] / t, amplitude_ratio=amp(w) / a, child_n=len(c)))
        out.append(
            dict(
                period_ratio=qsummary([r["period_ratio"] for r in ratios]),
                amplitude_ratio=qsummary([r["amplitude_ratio"] for r in ratios]),
                child_count=qsummary([r["child_n"] for r in ratios]),
            )
        )
        previous = s["waves"]
    return out


def _crossing_distribution(waves, key):
    c = Counter()
    for w in waves:
        n = int(w.get(key, 0) or 0)
        c["0" if n == 0 else "1" if n == 1 else "2plus"] += 1
    return dict(c)


def _stage_summary(s, bars):
    years = Counter(int(bars.timestamp.iloc[w["known_from_bar"]].year) for w in s["waves"])
    pivot_crossing = Counter(
        "NA"
        if p["lower_reset_count_since_previous_pivot"] is None
        else "0"
        if p["lower_reset_count_since_previous_pivot"] == 0
        else "1"
        if p["lower_reset_count_since_previous_pivot"] == 1
        else "2plus"
        for p in s["pivots"]
    )
    return dict(
        level=f"C{s['level']}",
        input_roots=len(s["input_roots"]),
        input_nodes=len(s["stream"]),
        duplicate_occurrences_merged=s["duplicate_occurrences_merged"],
        root_boundaries=len(s["root_boundaries"]),
        lower_events=len(s["lower_events"]),
        pivots=len(s["pivots"]),
        resets=len(s["resets"]),
        completed_waves=len(s["waves"]),
        output_roots=len(s["roots"]),
        duration=qsummary([w["duration"] for w in s["waves"]]),
        waves_by_confirmation_year=dict(sorted(years.items())),
        lower_reset_crossing_waves=_crossing_distribution(s["waves"], "lower_reset_count"),
        lower_root_crossing_waves=_crossing_distribution(s["waves"], "lower_root_boundary_count"),
        pivot_lower_reset_crossing=dict(pivot_crossing),
    )


def analyze(bars):
    base = base_inventory(bars)
    before = _canonical_base_digest(base)
    control = hierarchy(base, 1)
    candidate = continuity_hierarchy(base, 1, 3)
    after = _canonical_base_digest(base)
    if before != after:
        raise ValueError("candidate mutated frozen base ledger")
    control_counts = [sum(len(g["waves"]) for g in control["graphs"][i].values()) for i in range(3)]
    candidate_counts = [len(s["waves"]) for s in candidate["stages"]]
    ratios = _stage_ratios(candidate["stages"], base)
    c3 = candidate_counts[2] if len(candidate_counts) > 2 else 0
    representation_pass = c3 >= 8
    return (
        dict(
            schema_id="csi1000.scale_specific_continuity_v1@1.0",
            status="REPRESENTATION_ONLY",
            base_ledger_digest=before,
            base_ledger_unchanged=before == after,
            counts=dict(
                bars=len(bars),
                base_waves=len(base["waves"]),
                base_resets=len(base["resets"]),
                base_roots=len(base["roots"]),
            ),
            control_completed_waves=dict(C1=control_counts[0], C2=control_counts[1], C3=control_counts[2]),
            candidate_completed_waves=dict(C1=candidate_counts[0], C2=candidate_counts[1], C3=candidate_counts[2]),
            candidate_stages=[_stage_summary(s, bars) for s in candidate["stages"]],
            candidate_ratio_outputs=ratios,
            fidelity_gate=dict(
                frozen_physical_capacity_proxy=14.941995359628772,
                required_fraction=0.5,
                required_complete_C3=8,
                observed_complete_C3=c3,
                representation_pass=representation_pass,
            ),
            no_target_period_band=True,
            no_outcomes=True,
            one_minute_admitted=False,
            authority=dict(scale_law=False, router=False, signal=False, trade=False, production=False),
        ),
        candidate,
        base,
    )
