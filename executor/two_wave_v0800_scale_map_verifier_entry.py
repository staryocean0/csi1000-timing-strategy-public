"""Verifier wrapper for Two-Wave V0800-B Preflight Amendment A."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

import two_wave_v0800_scale_map_verifier as base

CANDIDATES = (1.25, 4.0 / 3.0, math.sqrt(2.0), 1.5)
LEGACY = 2.0
DIAGNOSTIC = CANDIDATES + (LEGACY,)


def fail(reason: str) -> None:
    print(json.dumps({"status": "failed", "reason": reason}, sort_keys=True))
    raise SystemExit(1)


def _same_float_list(got, expected) -> bool:
    try:
        values = [float(x) for x in got]
    except Exception:
        return False
    return len(values) == len(expected) and all(abs(a - b) <= 1e-12 for a, b in zip(values, expected))


def validate_amendment(summary: dict) -> None:
    if summary.get("study_amendment") != "V0800_PREFLIGHT_AMENDMENT_A":
        fail("preflight_amendment_missing")
    if summary.get("duration_unit") != "bar_intervals_between_pivot_occurrence_bars":
        fail("duration_unit_ambiguous")
    if summary.get("inclusive_observation_count_relation") != "span_rows = duration + 1":
        fail("inclusive_span_relation_drift")
    if not _same_float_list(summary.get("candidate_rhos", []), CANDIDATES):
        fail("candidate_rho_family_drift")
    if not _same_float_list(summary.get("diagnostic_rhos", []), DIAGNOSTIC):
        fail("diagnostic_rho_family_drift")
    if abs(float(summary.get("legacy_control_rho", math.nan)) - LEGACY) > 1e-12:
        fail("legacy_control_missing")
    if summary.get("legacy_control_role") != "historical_v04_width_reference_only":
        fail("legacy_control_role_drift")
    if summary.get("legacy_control_can_win") is not False or summary.get("legacy_control_can_change_candidate_family") is not False:
        fail("legacy_control_authority_violation")
    if summary.get("rho_winner") is not None or summary.get("morphology_acceptance") is not False:
        fail("premature_authority")
    by_rho = summary.get("by_rho", {})
    if f"{LEGACY:.12g}" not in by_rho:
        fail("legacy_control_statistics_missing")
    hist = summary.get("duration_histogram", {})
    inclusive = summary.get("duration_histogram_inclusive_rows", {})
    try:
        expected = {str(int(k) + 1): int(v) for k, v in hist.items()}
    except Exception:
        fail("duration_histogram_invalid")
    if inclusive != expected:
        fail("inclusive_duration_histogram_mismatch")


def run_base_verifier(inputs: Path, results: Path, summary: dict) -> None:
    # Reuse the independently written structural verifier on all five rho
    # diagnostics without mutating the persisted candidate-only summary claim.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name in ("A_WAVES.csv", "SAME_SCALE_MATCHES.csv", "INPUT_RECEIPT.json"):
            shutil.copy2(results / name, root / name)
        temp_summary = dict(summary)
        temp_summary["candidate_rhos"] = list(DIAGNOSTIC)
        (root / "SUMMARY.json").write_text(json.dumps(temp_summary, indent=2, sort_keys=True) + "\n")
        old_rhos = base.RHOS
        old_argv = sys.argv
        captured = io.StringIO()
        try:
            base.RHOS = DIAGNOSTIC
            sys.argv = ["two_wave_v0800_scale_map_verifier.py", "--inputs", str(inputs), "--results", str(root)]
            with contextlib.redirect_stdout(captured):
                base.main()
        except SystemExit as exc:
            if exc.code not in (None, 0):
                fail("base_structural_verifier_failed")
        finally:
            base.RHOS = old_rhos
            sys.argv = old_argv
        try:
            verified = json.loads(captured.getvalue().strip())
        except Exception:
            fail("base_structural_verifier_output_invalid")
        if verified.get("status") != "passed":
            fail("base_structural_verifier_not_passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    inputs = Path(args.inputs)
    results = Path(args.results)
    try:
        summary = json.loads((results / "SUMMARY.json").read_text())
    except Exception:
        fail("summary_unavailable")
    validate_amendment(summary)
    run_base_verifier(inputs, results, summary)
    print(json.dumps({
        "status": "passed",
        "preflight_amendment": "A",
        "duration_unit_verified": True,
        "legacy_control_verified": True,
        "rho_winner": None,
        "trade_authority": False,
        "production_authority": False
    }, sort_keys=True))


if __name__ == "__main__":
    main()
