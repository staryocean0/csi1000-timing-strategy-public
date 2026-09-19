"""CLI runner for preregistered issue #615.

Writes an exact JSON payload plus a joined research ledger. Development evidence only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

import two_wave_t0_causal_c1_compression_interaction_v1 as study

DATA_SHA256 = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    data = Path(args.data).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    data_sha = sha256(data)
    if data_sha != DATA_SHA256:
        raise RuntimeError(f"frozen data hash mismatch: {data_sha}")

    bars = pd.read_parquet(data).reset_index(drop=True)
    result = study.analyze(bars)
    ledger = result.pop("ledger")

    ledger_path = out / "ISSUE615_JOINED_LEDGER.csv"
    ledger.to_csv(ledger_path, index=False)
    ledger_sha = sha256(ledger_path)

    module_path = Path(study.__file__).resolve()
    payload = {
        "schema_version": "two_wave_t0_causal_c1_compression_interaction_result_exact_v1",
        "issue": 615,
        "date": "2026-09-20",
        "input": {
            "data_ref": "factorlab-two-wave-strategy-lab/data/development/5m_offset_0.parquet",
            "data_sha256": data_sha,
            "rows": int(len(bars)),
            "risk507_authoritative_scored_ledger_sha256": study.AUTHORITATIVE_SCORED_LEDGER_SHA256,
        },
        "hashes": {
            "module_sha256": sha256(module_path),
            "joined_ledger_sha256": ledger_sha,
        },
        **result,
    }

    exact_path = out / "ISSUE615_RESULT_EXACT.json"
    exact_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    exact_sha = sha256(exact_path)

    print(json.dumps({
        "verdict": payload["decision"]["verdict"],
        "module_sha256": payload["hashes"]["module_sha256"],
        "joined_ledger_sha256": ledger_sha,
        "exact_result_sha256": exact_sha,
        "prefix_replay_passed": payload["prefix_replay_passed"],
        "support_passed": payload["support"]["passed"],
        "point_contrasts": payload["point_contrasts"],
        "bootstrap": payload["bootstrap"],
        "yearly_contrasts": payload["yearly_contrasts"],
        "checks": payload["decision"]["checks"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
