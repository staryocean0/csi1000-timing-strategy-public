"""Preflight-A entrypoint for the first real Two-Wave V0800-B scale-map run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import two_wave_v0800_scale_map as base
import two_wave_v0800_semantics as semantics

CANDIDATE_RHOS = tuple(semantics.CANDIDATE_RHOS)
LEGACY_RHO_CONTROL = float(semantics.LEGACY_RHO_CONTROL)
DIAGNOSTIC_RHOS = CANDIDATE_RHOS + (LEGACY_RHO_CONTROL,)


def _rewrite_summary(path: Path) -> None:
    value = json.loads(path.read_text())
    if value.get("rho_winner") is not None or value.get("morphology_acceptance") is not False:
        raise RuntimeError("two_wave_v0800_preflight_authority_violation")
    original_hist = value.get("duration_histogram")
    if not isinstance(original_hist, dict):
        raise RuntimeError("two_wave_v0800_duration_histogram_missing")
    inclusive = {str(int(k) + 1): int(v) for k, v in original_hist.items()}
    value["study_amendment"] = "V0800_PREFLIGHT_AMENDMENT_A"
    value["duration_unit"] = "bar_intervals_between_pivot_occurrence_bars"
    value["inclusive_observation_count_relation"] = "span_rows = duration + 1"
    value["duration_histogram_inclusive_rows"] = inclusive
    value["candidate_rhos"] = list(CANDIDATE_RHOS)
    value["diagnostic_rhos"] = list(DIAGNOSTIC_RHOS)
    value["legacy_control_rho"] = LEGACY_RHO_CONTROL
    value["legacy_control_role"] = "historical_v04_width_reference_only"
    value["legacy_control_can_win"] = False
    value["legacy_control_can_change_candidate_family"] = False
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run(inputs: Path, out: Path) -> None:
    # The base analyzer is unchanged. Only its diagnostic rho loop is widened
    # for this pre-run control, then the summary explicitly separates the four
    # v0.8 candidates from the historical rho=2.0 reference.
    original = base.CANDIDATE_RHOS
    try:
        base.CANDIDATE_RHOS = DIAGNOSTIC_RHOS
        base.run(inputs, out)
    finally:
        base.CANDIDATE_RHOS = original
    _rewrite_summary(out / "SUMMARY.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    run(Path(args.inputs), Path(args.out))


if __name__ == "__main__":
    main()
