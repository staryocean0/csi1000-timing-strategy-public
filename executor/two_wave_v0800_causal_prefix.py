"""Two-Wave v0.8.0 V0800-C causal prefix replay.

Development morphology diagnostic only. No future return, PnL, trading action,
position, execution route, rho selection, or production authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

from two_wave_v0800_scale_map import (
    DATA_BYTES,
    DATA_FILE,
    DATA_SHA256,
    DEV_END_EXCLUSIVE,
    DEV_START,
    MAX_UNFINISHED_LEG,
    MIN_LEG,
    SOURCE_REF,
    SOURCE_REPO,
    TemporalMaturityAEngine,
    WaveRecord,
    load_bars,
)
from two_wave_v0800_semantics import CANDIDATE_RHOS, same_scale

SCHEMA = "csi1000.two_wave_v0800_causal_prefix@1.0"
STUDY = "V0800-C_CAUSAL_PREFIX_REPLAY"
FIXED_ROW_STRIDE = 4096
EVENT_WAVE_STRIDE = 256


def stable_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def canonical_wave(rec: WaveRecord) -> tuple:
    w = rec.wave
    return (
        str(w.wave_id),
        int(rec.epoch),
        int(w.start_bar),
        int(w.high_bar),
        int(w.end_bar),
        int(w.confirmation_bar),
        int(w.duration),
    )


def _rho_key(rho: float) -> str:
    return f"{rho:.12g}"


def nearest_predecessor(records: list[WaveRecord], current_index: int, rho: float) -> WaveRecord | None:
    current_rec = records[current_index]
    current = current_rec.wave
    # Earlier records are in causal publication order. End bars are monotone
    # within an epoch, so reverse search returns the nearest eligible object.
    for previous_rec in reversed(records[:current_index]):
        previous = previous_rec.wave
        if previous_rec.epoch != current_rec.epoch:
            continue
        if previous.confirmation_bar > current.confirmation_bar:
            continue
        if previous.end_bar > current.start_bar:
            continue
        if same_scale(previous.duration, current.duration, rho):
            return previous_rec
    return None


def canonical_pairs(records: list[WaveRecord]) -> tuple[list[tuple], dict[str, int]]:
    pairs: list[tuple] = []
    violations = {
        "future_reference_violations": 0,
        "predecessor_after_current_violations": 0,
        "nearer_eligible_predecessor_skip_violations": 0,
    }
    for i, current_rec in enumerate(records):
        current = current_rec.wave
        if current.end_bar > current.confirmation_bar:
            violations["future_reference_violations"] += 1
        for rho in CANDIDATE_RHOS:
            previous_rec = nearest_predecessor(records, i, rho)
            if previous_rec is None:
                continue
            previous = previous_rec.wave
            if previous.confirmation_bar > current.confirmation_bar:
                violations["future_reference_violations"] += 1
            if previous.end_bar > current.start_bar:
                violations["predecessor_after_current_violations"] += 1
            # Independently prove that there is no later-ended eligible wave.
            for candidate_rec in records[:i]:
                candidate = candidate_rec.wave
                if candidate_rec.epoch != current_rec.epoch:
                    continue
                if candidate.confirmation_bar > current.confirmation_bar:
                    continue
                if candidate.end_bar > current.start_bar or candidate.end_bar <= previous.end_bar:
                    continue
                if same_scale(candidate.duration, current.duration, rho):
                    violations["nearer_eligible_predecessor_skip_violations"] += 1
                    break
            pairs.append(
                (
                    _rho_key(rho),
                    str(current.wave_id),
                    str(previous.wave_id),
                    int(current_rec.epoch),
                    int(current.start_bar),
                    int(current.end_bar),
                    int(current.confirmation_bar),
                    int(current.duration),
                    int(previous.start_bar),
                    int(previous.end_bar),
                    int(previous.confirmation_bar),
                    int(previous.duration),
                )
            )
    return pairs, violations


def run_engine(bars: pd.DataFrame) -> list[WaveRecord]:
    records, _, _ = TemporalMaturityAEngine(bars).run()
    return records


def checkpoint_map(bars: pd.DataFrame, full_records: list[WaveRecord]) -> dict[int, set[str]]:
    n = len(bars)
    checkpoints: dict[int, set[str]] = {}

    def add(length: int, reason: str) -> None:
        length = int(length)
        if 1 <= length <= n:
            checkpoints.setdefault(length, set()).add(reason)

    for length in range(FIXED_ROW_STRIDE, n, FIXED_ROW_STRIDE):
        add(length, "fixed_stride")
    years = bars.timestamp.dt.year
    for year in range(2015, 2021):
        positions = bars.index[years.eq(year)]
        if len(positions):
            add(int(positions.max()) + 1, f"year_end_{year}")
    if full_records:
        for ordinal in range(0, len(full_records), EVENT_WAVE_STRIDE):
            add(full_records[ordinal].wave.confirmation_bar + 1, f"wave_ordinal_{ordinal}")
        add(full_records[-1].wave.confirmation_bar + 1, "final_wave_confirmation")
    add(n, "full_rows")
    return dict(sorted(checkpoints.items()))


def _list_mismatch(a: list[tuple], b: list[tuple]) -> int:
    if a == b:
        return 0
    common = min(len(a), len(b))
    unequal = sum(a[i] != b[i] for i in range(common))
    return unequal + abs(len(a) - len(b))


def analyze(bars: pd.DataFrame) -> tuple[pd.DataFrame, dict, dict]:
    full_records = run_engine(bars)
    full_waves = [canonical_wave(x) for x in full_records]
    full_pairs, full_violations = canonical_pairs(full_records)
    checkpoints = checkpoint_map(bars, full_records)
    audit_rows = []
    checkpoint_hashes = {}
    totals = {
        "future_reference_violations": int(full_violations["future_reference_violations"]),
        "predecessor_after_current_violations": int(full_violations["predecessor_after_current_violations"]),
        "nearer_eligible_predecessor_skip_violations": int(full_violations["nearer_eligible_predecessor_skip_violations"]),
        "wave_prefix_mismatches": 0,
        "pair_prefix_mismatches": 0,
        "ledger_hash_mismatches": 0,
    }
    for length, reasons in checkpoints.items():
        prefix_records = run_engine(bars.iloc[:length].copy())
        actual_waves = [canonical_wave(x) for x in prefix_records]
        actual_pairs, prefix_violations = canonical_pairs(prefix_records)
        expected_waves = [row for row in full_waves if int(row[5]) < length]
        current_confirmation = {row[0]: int(row[5]) for row in full_waves}
        expected_pairs = [row for row in full_pairs if current_confirmation[row[1]] < length]
        wave_mismatch = _list_mismatch(actual_waves, expected_waves)
        pair_mismatch = _list_mismatch(actual_pairs, expected_pairs)
        actual_wave_hash = stable_hash(actual_waves)
        expected_wave_hash = stable_hash(expected_waves)
        actual_pair_hash = stable_hash(actual_pairs)
        expected_pair_hash = stable_hash(expected_pairs)
        hash_mismatch = int(actual_wave_hash != expected_wave_hash) + int(actual_pair_hash != expected_pair_hash)
        totals["future_reference_violations"] += int(prefix_violations["future_reference_violations"])
        totals["predecessor_after_current_violations"] += int(prefix_violations["predecessor_after_current_violations"])
        totals["nearer_eligible_predecessor_skip_violations"] += int(
            prefix_violations["nearer_eligible_predecessor_skip_violations"]
        )
        totals["wave_prefix_mismatches"] += int(wave_mismatch)
        totals["pair_prefix_mismatches"] += int(pair_mismatch)
        totals["ledger_hash_mismatches"] += int(hash_mismatch)
        passed = (
            wave_mismatch == 0
            and pair_mismatch == 0
            and hash_mismatch == 0
            and all(int(v) == 0 for v in prefix_violations.values())
        )
        audit_rows.append(
            {
                "prefix_length": int(length),
                "reasons": ";".join(sorted(reasons)),
                "actual_wave_count": len(actual_waves),
                "expected_wave_count": len(expected_waves),
                "actual_pair_count": len(actual_pairs),
                "expected_pair_count": len(expected_pairs),
                "future_reference_violations": int(prefix_violations["future_reference_violations"]),
                "predecessor_after_current_violations": int(prefix_violations["predecessor_after_current_violations"]),
                "nearer_eligible_predecessor_skip_violations": int(
                    prefix_violations["nearer_eligible_predecessor_skip_violations"]
                ),
                "wave_prefix_mismatches": int(wave_mismatch),
                "pair_prefix_mismatches": int(pair_mismatch),
                "ledger_hash_mismatches": int(hash_mismatch),
                "passed": bool(passed),
            }
        )
        checkpoint_hashes[str(length)] = {
            "actual_wave_sha256": actual_wave_hash,
            "expected_wave_sha256": expected_wave_hash,
            "actual_pair_sha256": actual_pair_hash,
            "expected_pair_sha256": expected_pair_hash,
        }
    audit = pd.DataFrame(audit_rows)
    scientific_pass = bool(all(value == 0 for value in totals.values()) and audit.passed.all())
    pair_counts = {
        _rho_key(rho): sum(1 for row in full_pairs if row[0] == _rho_key(rho)) for rho in CANDIDATE_RHOS
    }
    hashes = {
        "schema_id": "csi1000.two_wave_v0800_causal_prefix_hashes@1.0",
        "full_wave_sha256": stable_hash(full_waves),
        "full_pair_sha256": stable_hash(full_pairs),
        "checkpoint_hashes": checkpoint_hashes,
    }
    summary = {
        "schema_id": SCHEMA,
        "study": STUDY,
        "role": "already_consumed_semantic_development_not_fresh_oos",
        "symbol": "000852.SH",
        "timeframe": "5m_offset_0",
        "pivot_kernel": {
            "name": "v0.4.3_opposite_extremum_min_leg_maturity",
            "min_leg": MIN_LEG,
            "max_unfinished_leg": MAX_UNFINISHED_LEG,
        },
        "candidate_rhos": list(CANDIDATE_RHOS),
        "checkpoint_count": int(len(audit)),
        "passed_checkpoint_count": int(audit.passed.sum()),
        "full_wave_count": int(len(full_waves)),
        "full_pair_count": int(len(full_pairs)),
        "full_pair_count_by_rho": pair_counts,
        "violations": totals,
        "causal_replay_passed": scientific_pass,
        "rho_winner": None,
        "year_2026_read": False,
        "future_outcome_used": False,
        "pnl_used": False,
        "morphology_acceptance": False,
        "direction_winner": None,
        "trade_authority": False,
        "production_authority": False,
    }
    return audit, hashes, summary


def run(inputs: Path, out: Path) -> None:
    data = inputs / DATA_FILE
    bars = load_bars(data)
    audit, hashes, summary = analyze(bars)
    out.mkdir(parents=True, exist_ok=False)
    audit.to_csv(out / "CHECKPOINT_AUDIT.csv", index=False)
    (out / "LEDGER_HASHES.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out / "INPUT_RECEIPT.json").write_text(
        json.dumps(
            {
                "schema_id": "csi1000.two_wave_v0800_causal_prefix_input@1.0",
                "source_repository": SOURCE_REPO,
                "source_ref": SOURCE_REF,
                "file": DATA_FILE,
                "bytes": DATA_BYTES,
                "sha256": DATA_SHA256,
                "rows_read": int(len(bars)),
                "min_timestamp": str(bars.timestamp.min()),
                "max_timestamp": str(bars.timestamp.max()),
                "allowed_start": str(DEV_START.date()),
                "allowed_end": str((DEV_END_EXCLUSIVE - pd.Timedelta(days=1)).date()),
                "year_2026_read": False,
                "substitute_data_used": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    run(Path(args.inputs), Path(args.out))


if __name__ == "__main__":
    main()
