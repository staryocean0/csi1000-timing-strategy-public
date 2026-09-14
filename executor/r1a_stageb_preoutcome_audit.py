"""Outcome-blind Stage B cohort gate. No realized future return is constructed."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import r1a_stagea_feature_audit as feature_audit

VALID_YEARS = {2021, 2022, 2023, 2024, 2025}
MAX_HORIZON = 240
RETENTION_MIN = 0.99


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=pathlib.Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    feature_audit.source_integrity_audit(source)
    sys.path.insert(0, str(source))
    from research.index_price_validity import core

    freeze = json.loads(
        (source / "docs" / "governance" / "INDEX_PRICE_VALIDITY_FREEZE@1.0.json").read_text(encoding="utf-8")
    )
    tape = feature_audit.load_tape(source)
    feature_audit.session_audit(tape)
    events = feature_audit.build_snapshots(tape, core, freeze)
    validation = np.flatnonzero(events.year.astype(int).isin(VALID_YEARS).to_numpy())
    require(len(validation) == 1296, "validation_event_count_mismatch")
    entry = events.confirm_idx.to_numpy(int)[validation] + 1
    keep = entry + MAX_HORIZON < len(tape)
    retained = int(keep.sum())
    retention = float(retained / len(validation))
    require(retention >= RETENTION_MIN, f"common_terminal_retention_failed:{retention}")
    print(json.dumps({
        "schema": "r1a_stageb_preoutcome_common_terminal_v1",
        "mother_population": int(len(validation)),
        "common_terminal_events": retained,
        "retention": retention,
        "retention_gate_min": RETENTION_MIN,
        "max_horizon_observed_bars": MAX_HORIZON,
        "current_validation_outcomes_constructed": False,
        "data_2026_opened": False,
        "status": "STAGEB_PREOUTCOME_COHORT_GATE_PASS"
    }, sort_keys=True))


if __name__ == "__main__":
    main()
