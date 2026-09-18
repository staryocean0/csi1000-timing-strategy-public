"""Independent verifier for issue #386 fixed-lag confirmation measurement.

Does not import the fixed-lag producer or pure fixed-lag module.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import numpy as np

import wave_scale_validity_market_verifier_v1 as vv
import wave_scale_dominance_market_verifier_v1 as dv
import wave_scale_reference_verifier_v2 as rv

INPUTS = Path("/work/inputs")
RESULTS = Path("/results/study")
PROTOCOL = Path("/work/scale_fixed_lag_confirmation/protocol.json")
FILES = ("1m_official.parquet", *(f"5m_offset_{i}.parquet" for i in range(5)))
LAGS = (0, 5, 10, 15, 25)
EXPECTED_BLIND_SHA = "5ab33685531475b3ad6cf4f69590c0af0925836679043d24ce2a44127ab7d4d1"
EXPECTED_LAG0_SHA = "a0b71c19591a83bf2ee7cc24eaecaea367d0d3b3772a0e41c03d7c361b5fa659"
EPS = 1e-14
VAR_FLOOR = 1e-24
POST_HORIZONS = (1, 3, 5, 10, 20)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_json(path, max_bytes=32 * 1024 * 1024):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError("json_file")
    return json.loads(path.read_text(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def protocol():
    p = load_json(PROTOCOL)
    if p.get("schema_id") != "csi1000.scale_fixed_lag_confirmation_protocol@1.0":
        raise ValueError("protocol")
    if p.get("profile") != "two-wave-scale-fixed-lag-confirmation-measurement-v1":
        raise ValueError("profile")
    if tuple(p.get("lag_minutes", [])) != LAGS or set(p.get("files", {})) != set(FILES):
        raise ValueError("lag_or_files")
    if p.get("reference_labels_visible_to_compute") is not False:
        raise ValueError("labels")
    if p.get("threshold_selection_in_run") is not False or p.get("knowledge_time_future_data_used") is not False:
        raise ValueError("scope")
    return p


def confirmation_context(seq, row, lag):
    minute = {"11:00": 660, "14:30": 870}[row["anchor"]]
    hits = seq.index[(seq["audit_day"] == row["day"]) & (seq["audit_minute"] == minute)].tolist()
    if len(hits) != 1:
        raise ValueError("anchor_support")
    idx = int(hits[0])
    if idx < 299 or idx + lag >= len(seq):
        raise ValueError("confirmation_support")
    x = seq.iloc[idx - 299:idx + lag + 1].copy()
    if len(x) != 300 + lag:
        raise ValueError("confirmation_length")
    suffix = x.iloc[299:]
    if len(set(str(v) for v in suffix["audit_day"])) != 1:
        raise ValueError("confirmation_cross_day")
    mins = suffix["audit_minute"].to_numpy(int)
    if len(mins) > 1 and not np.all(np.diff(mins) == 1):
        raise ValueError("confirmation_noncontiguous")
    if bool(x["causal_flat_fill"].any()) or not bool(x["high_frequency_analysis_eligible"].all()):
        raise ValueError("confirmation_quality")
    x["relative_minute"] = np.arange(-299, lag + 1, dtype=int)
    return x


def jump_confirmation(prices, relative):
    x = np.asarray(prices, float)
    rel = np.asarray(relative, int)
    y = np.log(x)
    signed = np.diff(y)
    absolute = np.abs(signed)
    eligible = np.flatnonzero(rel[1:] <= 0)
    if not len(eligible):
        raise ValueError("jump_support")
    move = int(eligible[np.argmax(absolute[eligible])])
    close = move + 1
    jump = float(absolute[move])
    sign = 0.0 if jump <= EPS else float(np.sign(signed[move]))
    lo, hi = max(0, move - 10), min(len(absolute), move + 11)
    neighbors = np.delete(absolute[lo:hi], move - lo)
    baseline = float(np.median(neighbors)) if len(neighbors) else 0.0
    isolation = None if baseline <= EPS else jump / baseline
    pre = float(y[close - 1])
    ratios = {}
    for h in POST_HORIZONS:
        target = close + h
        ratios[str(h)] = None if jump <= EPS or target >= len(y) else float(
            (y[target] - pre) * sign / jump
        )
    post = y[close + 1:close + 11]
    projected = None if jump <= EPS or not len(post) else (post - pre) * sign / jump
    return {
        "largest_close_jump_relative_minute": int(rel[close]),
        "local_jump_isolation_ratio": None if isolation is None or not math.isfinite(isolation) else float(isolation),
        "local_jump_baseline_log_move": baseline,
        "local_jump_isolation_undefined_zero_baseline": bool(baseline <= EPS),
        "signed_post_jump_displacement_ratio": ratios,
        "post_jump_midpoint_hold_fraction_10": None if projected is None else float(np.mean(projected >= 0.5)),
        "post_jump_reversal_extreme_10": None if projected is None else float(max(0.0, np.max(1.0 - projected))),
        "post_jump_available_bars": int(len(post)),
    }


def q(values):
    x = np.asarray([v for v in values if v is not None and math.isfinite(float(v))], float)
    if not len(x):
        return None
    return {"min": float(x.min()), "q25": float(np.quantile(x, .25)),
            "median": float(np.median(x)), "q75": float(np.quantile(x, .75)),
            "max": float(x.max())}


def morph_phase(rows):
    arr = np.asarray(rows, float)
    rel = arr[:, 0].astype(int)
    prices = arr[:, 1]
    y = np.log(prices)
    n = len(y)
    t = np.linspace(-1.0, 1.0, n)
    eligible = [i for i in range(2, n - 2) if rel[i] <= 0]
    if len(eligible) < 2:
        raise ValueError("morph_support")
    penalty = 2.0 * math.log(len(eligible))
    level = dv.fit(y, np.ones((n, 1)))
    trend = dv.fit(y, np.column_stack([np.ones(n), t]))
    background = min([("LEVEL", level, 1), ("ONE_LEG_TREND", trend, 2)],
                     key=lambda z: (z[1][4], z[2], z[0]))
    candidates = []
    for turn in eligible:
        knot = t[turn]
        fit = dv.fit(y, np.column_stack([np.ones(n), t, np.maximum(t - knot, 0.0)]))
        pre = float(fit[0][1])
        post = float(fit[0][1] + fit[0][2])
        shape = "PEAK" if pre > 0 and post < 0 else ("TROUGH" if pre < 0 and post > 0 else "NO_REVERSAL")
        candidates.append((float(fit[4]) + penalty, float(fit[4]), turn, fit, shape))
    candidates.sort(key=lambda z: (z[0], z[1], z[2]))
    best, second = candidates[0], candidates[1]
    turn, fit, shape = best[2], best[3], best[4]
    incoming_signed = float(y[turn] - y[0])
    incoming = abs(incoming_signed)
    anchor_signed = float(y[-1] - y[turn])
    counter = abs(anchor_signed) if incoming > EPS and incoming_signed * anchor_signed < 0 else 0.0
    completion = None if incoming <= EPS else counter / incoming
    return {
        "bars": int(n),
        "best_turn_index": int(turn),
        "best_turn_relative_minute": int(rel[turn]),
        "shape": shape,
        "incoming_leg_amplitude_log": incoming,
        "counter_leg_amplitude_log": counter,
        "reversal_completion_ratio": completion,
        "post_turn_fraction": float((n - 1 - turn) / n),
        "turn_edge_distance_fraction": float(min(turn, n - 1 - turn) / max(1, n - 1)),
        "delta_search_adjusted_bic_vs_one_leg": float(best[0] - trend[4]),
        "one_leg_bic": float(trend[4]),
        "background_selected": background[0],
        "best_second_adjusted_bic_gap": float(second[0] - best[0]),
        "search_adjusted_bic": float(best[0]),
        "eligible_knots": int(len(eligible)),
    }


def morph_panel(close_rows):
    phases = {name: morph_phase(close_rows[name]) for name in sorted(close_rows)}
    shapes = Counter(p["shape"] for p in phases.values())
    turns = [p["best_turn_relative_minute"] for p in phases.values()]
    return {
        "schema_id": "csi1000.scale_morphology_evidence@2.0",
        "phases": phases,
        "phase_stability": {
            "shape_counts": dict(sorted(shapes.items())),
            "shape_agreement_max": int(max(shapes.values())),
            "turn_relative_minute_range": int(max(turns) - min(turns)),
            "reversal_completion_ratio": q([p["reversal_completion_ratio"] for p in phases.values()]),
            "post_turn_fraction": q([p["post_turn_fraction"] for p in phases.values()]),
            "turn_edge_distance_fraction": q([p["turn_edge_distance_fraction"] for p in phases.values()]),
            "delta_search_adjusted_bic_vs_one_leg": q([p["delta_search_adjusted_bic_vs_one_leg"] for p in phases.values()]),
            "best_second_adjusted_bic_gap": q([p["best_second_adjusted_bic_gap"] for p in phases.values()]),
            "one_leg_background_count": int(sum(p["background_selected"] == "ONE_LEG_TREND" for p in phases.values())),
        },
        "morphology_state": "UNASSIGNED_THRESHOLD_FREE",
        "ambiguity_region_selected": False,
        "threshold_selected": False,
    }


def expected_panel(pid, base, base_ohlc, knowledge, knowledge_ohlc):
    v1 = vv.panel(pid, base, base_ohlc)["validity"]
    ext = jump_confirmation(knowledge["close"].to_numpy(float), knowledge["relative_minute"].to_numpy(int))
    close_rows = {name: [(r[0], r[2]) for r in rows] for name, rows in knowledge_ohlc.items()}
    return {
        "panel_id": pid,
        "validity_v2": {
            "schema_id": "csi1000.scale_validity_evidence@2.0",
            "v1_controls": v1,
            "jump_extension": ext,
            "validity_state": "UNASSIGNED_THRESHOLD_FREE",
            "threshold_selected": False,
        },
        "morphology_v2": morph_panel(close_rows),
    }


def close(a, b, path="root"):
    if isinstance(a, dict):
        if set(a) != set(b):
            raise ValueError("dict_keys:" + path)
        for key in a:
            close(a[key], b[key], path + "." + key)
    elif isinstance(a, list):
        if len(a) != len(b):
            raise ValueError("list_len:" + path)
        for i, (x, y) in enumerate(zip(a, b)):
            close(x, y, f"{path}[{i}]")
    elif isinstance(a, (int, str, bool)) or a is None:
        if a != b:
            raise ValueError("value:" + path)
    elif not math.isclose(float(a), float(b), rel_tol=2e-10, abs_tol=2e-10):
        raise ValueError("float:" + path)


def main():
    p = protocol()
    fs = vv.frames(p)
    common = vv.common_days(fs)
    seq = vv.sequence(fs["1m_official.parquet"], common)
    eligible = vv.anchor_eligible(seq, common)
    full = rv.derive(sorted(eligible))
    blind = rv.expected_blind(full)
    blind_raw = (json.dumps(blind, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if hashlib.sha256(blind_raw).hexdigest() != EXPECTED_BLIND_SHA:
        raise ValueError("blind_hash")
    order = [row["panel_id"] for row in blind]
    by_panel = {row["panel_id"]: row for row in full}
    hashes = {}
    for lag in LAGS:
        path = RESULTS / f"fixed_lag_{lag:03d}.jsonl"
        lines = path.read_text().splitlines()
        if len(lines) != 192:
            raise ValueError("diagnostic_rows")
        got = [json.loads(line, parse_constant=lambda z: (_ for _ in ()).throw(ValueError(z))) for line in lines]
        if [row["panel_id"] for row in got] != order:
            raise ValueError("diagnostic_order")
        for actual in got:
            row = by_panel[actual["panel_id"]]
            base = vv.context(seq, row)
            base_ohlc = vv.phase_rows(fs, base)
            knowledge = confirmation_context(seq, row, lag)
            knowledge_ohlc = vv.phase_rows(fs, knowledge)
            expected = expected_panel(row["panel_id"], base, base_ohlc, knowledge, knowledge_ohlc)
            close(actual, expected)
        hashes[str(lag)] = sha(path)
    summary = load_json(RESULTS / "fixed_lag_summary.json")
    if summary.get("lag_diagnostics_sha256") != hashes:
        raise ValueError("summary_hashes")
    if summary.get("frozen_v2_reference_diagnostics_sha256") != EXPECTED_LAG0_SHA:
        raise ValueError("frozen_v2_reference")
    if summary.get("lag0_source_semantics_exact_same_runtime") is not True:
        raise ValueError("lag0_semantics")
    if summary.get("cross_platform_raw_byte_identity_required") is not False:
        raise ValueError("byte_identity_scope")
    if summary.get("support_by_lag") != {str(lag): 192 for lag in LAGS}:
        raise ValueError("summary_support")
    if summary.get("reference_labels_joined") is not False or summary.get("threshold_selection_in_run") is not False:
        raise ValueError("summary_scope")
    if summary.get("knowledge_time_future_data_used") is not False:
        raise ValueError("knowledge_scope")
    manifest = load_json(RESULTS / "manifest.json")
    if manifest.get("reference_labels_visible_to_compute") is not False or manifest.get("threshold_selected") is not False:
        raise ValueError("manifest_scope")
    for name, meta in manifest["files"].items():
        result = RESULTS / name
        if meta != {"bytes": result.stat().st_size, "sha256": sha(result)}:
            raise ValueError("manifest_identity")
    print(json.dumps({
        "status": "passed",
        "panels_verified": 192,
        "lag_minutes": list(LAGS),
        "lag_diagnostics_sha256": hashes,
        "reference_labels_joined": False,
        "threshold_selected": False,
        "production_authority": False,
    }, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
