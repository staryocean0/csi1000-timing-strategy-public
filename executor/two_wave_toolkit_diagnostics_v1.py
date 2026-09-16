"""Descriptive wave-period diagnostics, never automatic natural-scale discovery."""
from __future__ import annotations

from dataclasses import replace
import math

import numpy as np
import pandas as pd

from two_wave_toolkit_v1 import BarView, WaveConfig, build_inventory, validate_bars

DEFAULT_PERIOD_EDGES = tuple(4.0 * 2.0 ** (i / 2.0) for i in range(17))


def period_histogram(durations, edges=DEFAULT_PERIOD_EDGES) -> dict:
    edges = np.asarray(edges, dtype=float)
    values = np.asarray(list(durations), dtype=float)
    if edges.ndim != 1 or len(edges) < 2 or not np.isfinite(edges).all() or (edges <= 0).any() or (np.diff(edges) <= 0).any():
        raise ValueError("period edges must be finite, positive and strictly increasing")
    if values.ndim != 1 or not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("periods must be finite and positive")
    counts, _ = np.histogram(values, bins=edges)
    n = len(values)
    density = counts / (n * np.diff(np.log2(edges))) if n else np.zeros(len(counts))
    bins = []
    for i, count in enumerate(counts):
        bins.append({
            "period_lower_bars": float(edges[i]), "period_upper_bars": float(edges[i + 1]),
            "last_bin_right_inclusive": i == len(counts) - 1,
            "count": int(count), "fraction_of_all_waves": float(count / n) if n else None,
            "density_per_log2_period": float(density[i]) if n else None,
        })
    # Only strict interior maxima are candidates. Flat tops and boundaries are not declared clusters.
    modes = [i for i in range(1, len(counts) - 1) if counts[i] > 0 and density[i] > density[i-1] and density[i] > density[i+1]]
    return {
        "total_waves": n, "underflow": int((values < edges[0]).sum()),
        "overflow": int((values > edges[-1]).sum()), "bins": bins,
        "interior_density_peak_bin_candidates": modes,
        "natural_cluster_accepted": False,
        "boundary_peaks_and_flat_tops_not_promoted": True,
    }


def scan_periods(bars: pd.DataFrame, view: BarView, configs, edges=DEFAULT_PERIOD_EDGES) -> dict:
    """One input view at a time; analyze ALL extracted waves, not selected bands.

    Target bands do not trigger another extraction. Exact pivot triples repeated
    across detector settings are deduplicated in the union, not independent votes.
    No frequencies, number of clusters, or boundaries are selected for use here.
    """
    bars = validate_bars(bars, view)
    configs = list(configs)
    if not configs or any(not isinstance(c, WaveConfig) for c in configs):
        raise ValueError("at least one explicit WaveConfig is required")
    # Validate edges even when no waves are extracted.
    period_histogram([], edges)
    seen, union, settings = set(), {}, []
    for config in configs:
        detection_key = (config.min_leg_bars, config.max_unfinished_leg_bars)
        if detection_key in seen:
            continue
        seen.add(detection_key)
        unfiltered = replace(config, target_period_bars=None)
        inv = build_inventory(bars, view, unfiltered)
        rows = inv["waves"]
        for row in rows:
            union.setdefault(row["wave_identity"], row)
        years = sorted({str(row["confirmation_time"])[:4] for row in rows})
        settings.append({
            "min_leg_bars": config.min_leg_bars,
            "max_unfinished_leg_bars": config.max_unfinished_leg_bars,
            "wave_count": len(rows), "reset_count": len(inv["resets"]),
            "terminal_unconfirmed_candidate_present": inv["terminal_unconfirmed_candidate_present"],
            "duration_histogram": period_histogram((r["duration"] for r in rows), edges),
            "by_confirmation_year": {year: period_histogram((r["duration"] for r in rows if str(r["confirmation_time"]).startswith(year)), edges) for year in years},
        })
    return {
        "schema_id": "csi1000.wave_period_scan@1.0", "view": inv["view"],
        "bars_read": len(bars), "setting_count": len(settings), "settings": settings,
        "unique_pivot_triples_across_settings": len(union),
        "deduplicated_union_histogram": period_histogram((r["duration"] for r in union.values()), edges),
        "target_band_conditioning_used": False, "timeframes_pooled": False,
        "duplicate_settings_are_independent_evidence": False,
        "union_is_independent_sample": False,
        "natural_cluster_accepted": False, "selected_periods": [],
        "acceptance_requires": [
            "cross_year_stability", "detector_maturity_and_reset_sensitivity",
            "bin_origin_and_width_sensitivity", "unconfirmed_and_reset_censoring_review",
            "distinct_structure_overlap_review", "preregistered_null_comparison",
            "separate_visual_and_post_run_adjudication",
        ],
        "authority": dict(inv["authority"]),
    }
