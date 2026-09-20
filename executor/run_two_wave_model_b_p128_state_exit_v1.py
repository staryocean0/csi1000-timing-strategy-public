"""Governed runner for issue #635 Model B P128 state-exit increment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

import two_wave_model_b_p128_state_exit_v1 as study

EXPECTED_DATA_SHA256 = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"
EXPECTED_DATA_BYTES = 3_351_411
EXPECTED_DATA_ROWS = 70_114
EXPECTED_PREREG_SHA256 = "31784bcc4d4613347b1cda2e68f332e6d02703b9fcec3f07fc92834df875f508"
DATA_REF = "factorlab-two-wave-strategy-lab/data/development/5m_offset_0.parquet"
FROZEN_SOURCE_HASHES = {
    "two_wave_local_state_exit_compression_v1.py": "2dc3c316172fcd3d5e8f4f0086d05c356e5806e9d0b735fb72580bd5c2671908",
    "two_wave_current_band_recognizer_v1.py": "998e51b257540ce2e0384371d6a0b0b8226f3436e7b378a5d0aa9a3266b6e175",
    "two_wave_delayed_causal_wrapper_v1.py": "3ae2a9afa75dac173773d83356e115b58c248985567faa8b1ea9bd042cb6d3d9",
    "two_wave_postdelay_persistence_v1.py": "34fc30211db3922f6ba67b563a05b983fe5780870409fbe3cb39676448389a0f",
}


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def canonical(value):
    if isinstance(value, dict):
        return {str(k): canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("non-finite exact-result float")
        return float(format(value, ".12g"))
    return value


def run(data: Path, out: Path, prereg: Path) -> dict[str, object]:
    if not data.is_file() or data.is_symlink():
        raise FileNotFoundError(data)
    if not prereg.is_file() or prereg.is_symlink():
        raise FileNotFoundError(prereg)
    if data.stat().st_size != EXPECTED_DATA_BYTES:
        raise RuntimeError("data_bytes_mismatch")
    if sha256_file(data) != EXPECTED_DATA_SHA256:
        raise RuntimeError("data_sha256_mismatch")
    if sha256_file(prereg) != EXPECTED_PREREG_SHA256:
        raise RuntimeError("prereg_sha256_mismatch")

    here = Path(__file__).resolve().parent
    frozen_checks = {}
    for name, expected in FROZEN_SOURCE_HASHES.items():
        path = here / name
        actual = sha256_file(path)
        frozen_checks[name] = {"actual": actual, "expected": expected, "passed": actual == expected}
    if not all(v["passed"] for v in frozen_checks.values()):
        raise RuntimeError("frozen_source_identity_mismatch")

    bars = pd.read_parquet(data)
    if len(bars) != EXPECTED_DATA_ROWS:
        raise RuntimeError("data_rows_mismatch")

    result = study.analyze(bars, run_causal_audit=True)
    out.mkdir(parents=True, exist_ok=True)
    exact_path = out / "ISSUE635_RESULT_EXACT.json"
    base_hashes = {
        "prereg_sha256": EXPECTED_PREREG_SHA256,
        "study_module_sha256": sha256_file(Path(study.__file__).resolve()),
        "frozen_sources": frozen_checks,
    }
    exact = {
        "schema_version": "two_wave_model_b_p128_state_exit_result_exact_v1",
        "issue": 635,
        "date": "2026-09-20",
        "input": {
            "data_ref": DATA_REF,
            "data_sha256": EXPECTED_DATA_SHA256,
            "bytes": EXPECTED_DATA_BYTES,
            "rows": EXPECTED_DATA_ROWS,
            "fresh_oos": False,
        },
        "hashes": dict(base_hashes),
        **{k: v for k, v in result.items() if k != "scored"},
    }

    if result["status"] == "MODEL_B_P128_STATE_EXIT_INSUFFICIENT_SUPPORT":
        exact = canonical(exact)
        exact_path.write_text(
            json.dumps(exact, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        exact_sha = sha256_file(exact_path)
        summary = {
            "status": exact["status"],
            "verdict": exact["decision"]["verdict"],
            "evaluation_rows": 0,
            "baseline_identity_passed": False,
            "support_passed": False,
            "causal_audit_passed": False,
            "scored_ledger_sha256": None,
            "exact_result_sha256": exact_sha,
            "authority": exact["authority"],
        }
    else:
        ledger_path = out / "ISSUE635_SCORED_LEDGER.csv"
        result["scored"].to_csv(ledger_path, index=False, float_format="%.10g")
        ledger_sha = sha256_file(ledger_path)
        exact["hashes"]["scored_ledger_sha256"] = ledger_sha
        exact = canonical(exact)
        exact_path.write_text(
            json.dumps(exact, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        exact_sha = sha256_file(exact_path)
        summary = {
            "status": exact["status"],
            "verdict": exact["decision"]["verdict"],
            "evaluation_rows": exact["meta"]["evaluation_rows"],
            "baseline_identity_passed": bool(
                exact["baseline_identity"]["rows_match"]
                and exact["baseline_identity"]["hash_match"]
                and exact["baseline_identity"]["row_keys_match"]
                and exact["baseline_identity"]["frozen_fields_match"]
            ),
            "support_passed": exact["support"]["passed"],
            "causal_audit_passed": exact["causal_audit"]["passed"],
            "scored_ledger_sha256": ledger_sha,
            "exact_result_sha256": exact_sha,
            "authority": exact["authority"],
        }

    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prereg", type=Path, required=True)
    args = parser.parse_args()
    run(args.data, args.out, args.prereg)


if __name__ == "__main__":
    main()
