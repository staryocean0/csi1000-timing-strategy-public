"""Relocate frozen 5m base-cycle blind spots inside continuous C2/C3.

Diagnostic only: the base 4/48 recognizer is not changed. Retrospective
completed-wave morphology and causal as-of state are kept separate. No
returns, PnL, router objective, 1m input or authority promotion.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
import hashlib
import math

import numpy as np

from wave_cycle_identifiability_v1 import _base_coverage, _quartile, _reason, _runs, qsummary
from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_multiscale_dual_gates_v2 import amp, phase
from wave_scale_specific_continuity_v1 import continuity_hierarchy

DIRS = ("DOWN", "RANGE", "UP")
LEGS = ("DOWN", "UP")
PHASES = ("EARLY", "MIDDLE", "LATE")


def _cross_bucket(n):
    n = int(n or 0)
    return "0" if n == 0 else "1" if n == 1 else "2PLUS"


def _empty(n):
    return np.full(n, "UNRESOLVED", dtype=object)


def retrospective_stage(stage, n):
    """Completed occurrence geometry only; never a live historical state."""
    desc, leg, ph, aq, cross = (_empty(n) for _ in range(5))
    amplitudes = np.asarray([amp(w) for w in stage["waves"]], float)
    conflicts = 0
    for w in stage["waves"]:
        s, e, hi = int(w["start_bar"]), int(w["end_bar"]), int(w["high_bar"])
        if not 0 <= s < e <= n:
            raise ValueError("retrospective wave outside input")
        duration = e - s
        amplitude_q = _quartile(amp(w), amplitudes)
        crossing = _cross_bucket(w.get("lower_reset_count"))
        # Left-closed/right-open prevents a shared low anchor from carrying
        # two incompatible completed-wave labels.
        for t in range(s, e):
            cell = (w["direction"], "UP" if t <= hi else "DOWN", phase((t - s) / duration), amplitude_q, crossing)
            old = (desc[t], leg[t], ph[t], aq[t], cross[t])
            if desc[t] != "UNRESOLVED" and old != cell:
                conflicts += 1
                continue
            desc[t], leg[t], ph[t], aq[t], cross[t] = cell
    return {
        "descriptor": desc,
        "leg": leg,
        "phase": ph,
        "amplitude_quartile": aq,
        "crossing": cross,
        "meta": {"waves": len(stage["waves"]), "overlap_conflicts": conflicts, "amplitude_reference": qsummary(amplitudes.tolist())},
    }


def _prepare_asof(stage):
    return {
        "pivots": stage["pivots"],
        "pivot_known": [p["known_from_bar"] for p in stage["pivots"]],
        "waves": stage["waves"],
        "wave_known": [w["known_from_bar"] for w in stage["waves"]],
        "stream": stage["stream"],
        "node_known": [x["known_from_bar"] for x in stage["stream"]],
    }


def causal_state(prepared, t):
    """Then-known state only. Completed-wave descriptor is not backfilled."""
    npiv = bisect_right(prepared["pivot_known"], t)
    nwav = bisect_right(prepared["wave_known"], t)
    nnod = bisect_right(prepared["node_known"], t)
    piv = [p for p in prepared["pivots"][:npiv] if not p["left_censored"]]
    waves = prepared["waves"][:nwav]
    nodes = prepared["stream"][:nnod]
    if not piv:
        return {"status": "NO_CONFIRMED_PIVOT"}
    if not waves:
        return {"status": "NO_COMPLETED_WAVE"}
    if not nodes:
        return {"status": "NO_CONFIRMED_NODE"}
    recent = waves[-min(3, len(waves)):]
    period = float(np.median([w["duration"] for w in recent]))
    amplitude = float(np.median([amp(w) for w in recent]))
    p = piv[-1]
    age = (t - p["occurrence_bar"]) / period if period > 0 else None
    direction = "UP" if p["kind"] == "low" else "DOWN"
    latest = waves[-1]
    return {
        "status": "RESOLVED",
        "descriptor": latest["direction"],
        "leg": direction,
        "phase": phase(age),
        "period": period,
        "amplitude": amplitude,
        "age_ratio": age,
        "evidence_age_bars": t - nodes[-1]["occurrence_bar"],
        "crossing": _cross_bucket(latest.get("lower_reset_count")),
        "latest_wave_known_from": latest["known_from_bar"],
        "latest_pivot_occurrence": p["occurrence_bar"],
    }


def _episode_rows(bars, base, covered, T0):
    close = np.log(bars.close.to_numpy(float))
    high = bars.high.to_numpy(float)
    low = bars.low.to_numpy(float)
    reference = np.asarray([amp(w) for w in base["waves"]], float)
    rows = []
    for s, e in _runs(~covered):
        seg = close[s:e+1]
        variation = float(np.abs(np.diff(seg)).sum()) if len(seg) > 1 else 0.0
        raw_range = float(math.log(float(high[s:e+1].max()) / float(low[s:e+1].min())))
        displacement = float(abs(seg[-1] - seg[0])) if len(seg) > 1 else 0.0
        reason = _reason(base, s, e, len(bars))
        episode_id = hashlib.sha256(f"blind:{s}:{e}:{reason}".encode()).hexdigest()[:16]
        rows.append({
            "id": episode_id,
            "start": s,
            "end": e,
            "bars": e - s + 1,
            "T0_units": (e - s + 1) / T0,
            "reason": reason,
            "raw_log_range": raw_range,
            "path_efficiency": displacement / variation if variation else 0.0,
            "amplitude_quartile": _quartile(raw_range, reference),
        })
    return rows


def _majority_cell(mapping, s, e):
    cells = Counter()
    for t in range(s, e + 1):
        if mapping["descriptor"][t] == "UNRESOLVED":
            continue
        key = tuple(mapping[k][t] for k in ("descriptor", "leg", "phase", "amplitude_quartile", "crossing"))
        cells[key] += 1
    if not cells:
        return {"cell": None, "overlap_fraction": 0.0}
    key, count = cells.most_common(1)[0]
    return {
        "cell": {"descriptor": key[0], "leg": key[1], "phase": key[2], "amplitude_quartile": key[3], "crossing": key[4]},
        "overlap_fraction": count / (e - s + 1),
    }


def _exposure_table(blind, arrays, fields, minimum_exposure=1):
    exposure = Counter()
    missed = Counter()
    n = len(blind)
    for t in range(n):
        values = tuple(arrays[f][t] for f in fields)
        if any(v == "UNRESOLVED" for v in values):
            continue
        exposure[values] += 1
        if blind[t]:
            missed[values] += 1
    baseline = float(blind.mean())
    rows = []
    for key, total in exposure.items():
        if total < minimum_exposure:
            continue
        b = missed[key]
        rate = b / total
        rows.append({
            **{f: key[i] for i, f in enumerate(fields)},
            "bars": total,
            "blind_bars": b,
            "blind_fraction": rate,
            "lift_vs_all_bars": rate / baseline if baseline else None,
        })
    return sorted(rows, key=lambda r: (-r["blind_fraction"], -r["bars"], tuple(str(r[f]) for f in fields)))


def retrospective_report(blind, mappings):
    result = {}
    for level, m in mappings.items():
        resolved = m["descriptor"] != "UNRESOLVED"
        result[level] = {
            "meta": m["meta"],
            "resolved_all_bar_fraction": float(resolved.mean()),
            "resolved_blind_bar_fraction": float((resolved & blind).sum() / max(1, blind.sum())),
            "by_descriptor": _exposure_table(blind, m, ("descriptor",)),
            "by_leg": _exposure_table(blind, m, ("leg",)),
            "by_phase": _exposure_table(blind, m, ("phase",)),
            "by_amplitude": _exposure_table(blind, m, ("amplitude_quartile",)),
            "by_crossing": _exposure_table(blind, m, ("crossing",)),
            "descriptor_phase": _exposure_table(blind, m, ("descriptor", "phase"), 50),
            "descriptor_leg_phase": _exposure_table(blind, m, ("descriptor", "leg", "phase"), 50),
        }
    c2, c3 = mappings["C2"], mappings["C3"]
    joint = {
        "C2_C3_descriptor": _exposure_table(blind, {
            "C2_descriptor": c2["descriptor"], "C3_descriptor": c3["descriptor"]
        }, ("C2_descriptor", "C3_descriptor"), 50),
        "C2_C3_phase": _exposure_table(blind, {
            "C2_phase": c2["phase"], "C3_phase": c3["phase"]
        }, ("C2_phase", "C3_phase"), 50),
    }
    result["joint"] = joint
    return result


def causal_report(bars, blind, candidate, T0):
    confirms = sorted(w["known_from_bar"] for w in base_inventory(bars)["waves"])
    output = {}
    for level_index, level in ((1, "C2"), (2, "C3")):
        prepared = _prepare_asof(candidate["stages"][level_index])
        cells = defaultdict(list)
        resolved = 0
        blind_resolved = 0
        for t in range(len(bars)):
            state = causal_state(prepared, t)
            if state["status"] != "RESOLVED":
                continue
            resolved += 1
            blind_resolved += int(blind[t])
            i = bisect_right(confirms, t)
            last = confirms[i-1] if i else None
            left1 = int(np.searchsorted(confirms, t - T0 + 1, side="left"))
            key = (state["descriptor"], state["leg"], state["phase"], state["crossing"])
            cells[key].append((bool(blind[t]), None if last is None else (t-last)/T0, i-left1, state["amplitude"]))
        rows = []
        for key, values in cells.items():
            n = len(values)
            b = sum(v[0] for v in values)
            rows.append({
                "descriptor": key[0], "leg": key[1], "phase": key[2], "crossing": key[3],
                "bars": n, "blind_bars": b, "blind_fraction": b/n,
                "lift_vs_all_bars": (b/n)/float(blind.mean()) if blind.mean() else None,
                "age_since_base_confirmation_T0": qsummary([v[1] for v in values if v[1] is not None]),
                "mean_confirmations_last_T0": float(np.mean([v[2] for v in values])),
                "no_confirmation_last_T0_fraction": float(np.mean([v[2] == 0 for v in values])),
                "amplitude": qsummary([v[3] for v in values]),
            })
        output[level] = {
            "resolved_bars": resolved,
            "resolved_all_bar_fraction": resolved/len(bars),
            "resolved_blind_bar_fraction": blind_resolved/max(1, int(blind.sum())),
            "cells": sorted(rows, key=lambda r: (-r["blind_fraction"], -r["bars"], r["descriptor"], r["leg"], r["phase"])),
        }
    return output


def analyze(bars):
    base = base_inventory(bars)
    candidate = continuity_hierarchy(base, 1, 3)
    initial = [w["duration"] for w in base["waves"] if int(bars.timestamp.iloc[w["known_from_bar"]].year) <= 2017]
    if not initial:
        raise ValueError("no initial base waves")
    T0 = max(2, int(math.ceil(np.median(initial))))
    covered = _base_coverage(base, len(bars))
    blind = ~covered
    episodes = _episode_rows(bars, base, covered, T0)
    mappings = {
        "C2": retrospective_stage(candidate["stages"][1], len(bars)),
        "C3": retrospective_stage(candidate["stages"][2], len(bars)),
    }
    episode_summary = []
    for row in episodes:
        out = {k: row[k] for k in ("id", "bars", "T0_units", "reason", "raw_log_range", "path_efficiency", "amplitude_quartile")}
        for level in ("C2", "C3"):
            located = _majority_cell(mappings[level], row["start"], row["end"])
            out[level] = located
        episode_summary.append(out)
    root_break = [r for r in episode_summary if r["reason"] == "RESET_ROOT_BREAK"]
    deterministic_examples = [r["id"] for r in sorted(root_break, key=lambda r: hashlib.sha256(r["id"].encode()).hexdigest())[:24]]
    report = {
        "schema_id": "csi1000.blindspot_relocation_v1@1.0",
        "status": "AGGREGATE_DIAGNOSTIC_ONLY",
        "T0_bars": T0,
        "counts": {
            "bars": len(bars), "base_waves": len(base["waves"]), "base_resets": len(base["resets"]),
            "blind_bars": int(blind.sum()), "blind_episodes": len(episodes), "reset_root_break_episodes": len(root_break),
            "continuous_C2_waves": len(candidate["stages"][1]["waves"]), "continuous_C3_waves": len(candidate["stages"][2]["waves"]),
        },
        "blind_fraction": float(blind.mean()),
        "amplitude_quartile_counts": dict(sorted(Counter(r["amplitude_quartile"] for r in episodes).items())),
        "root_break_location": {
            level: {
                "episodes_any_overlap": sum(r[level]["overlap_fraction"] > 0 for r in root_break),
                "episodes_majority_overlap": sum(r[level]["overlap_fraction"] >= 0.5 for r in root_break),
                "overlap_fraction": qsummary([r[level]["overlap_fraction"] for r in root_break]),
            } for level in ("C2", "C3")
        },
        "retrospective": retrospective_report(blind, mappings),
        "causal_asof": causal_report(bars, blind, candidate, T0),
        "blind_episode_aggregate": episode_summary,
        "deterministic_visual_example_ids": deterministic_examples,
        "interpretation_boundary": "Completed C2/C3 morphology is retrospective only; only causal_asof cells may inform a later preregistered repair.",
        "one_minute_admitted": False,
        "outcomes_used": False,
        "authority": {"signal": False, "detector_repair": False, "router": False, "trade": False, "production": False},
    }
    return report
