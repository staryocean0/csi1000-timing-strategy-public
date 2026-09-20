"""Runner for issue #624 local-only state-exit compression study."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

import two_wave_local_state_exit_compression_v1 as study
import two_wave_delayed_causal_wrapper_v1 as wrapper
import two_wave_current_band_recognizer_v1 as oracle


EXPECTED_DATA_SHA256 = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"
EXPECTED_DATA_BYTES = 3_351_411
EXPECTED_DATA_ROWS = 70_114
DATA_REF = "factorlab-two-wave-strategy-lab/data/development/5m_offset_0.parquet"
EXPECTED_RECOGNIZER_SHA256 = "998e51b257540ce2e0384371d6a0b0b8226f3436e7b378a5d0aa9a3266b6e175"
EXPECTED_WRAPPER_SHA256 = "3ae2a9afa75dac173773d83356e115b58c248985567faa8b1ea9bd042cb6d3d9"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_ready(result: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in result.items()
        if key not in {"ledger", "scored"}
    }


def run(data: Path, out: Path) -> dict[str, object]:
    if not data.is_file():
        raise FileNotFoundError(data)
    data_bytes = data.stat().st_size
    data_sha = sha256_file(data)
    if data_bytes != EXPECTED_DATA_BYTES:
        raise RuntimeError(f"data_bytes_mismatch:{data_bytes}")
    if data_sha != EXPECTED_DATA_SHA256:
        raise RuntimeError(f"data_sha256_mismatch:{data_sha}")

    recognizer_sha = sha256_file(Path(oracle.__file__).resolve())
    wrapper_sha = sha256_file(Path(wrapper.__file__).resolve())
    if recognizer_sha != EXPECTED_RECOGNIZER_SHA256:
        raise RuntimeError(f"recognizer_sha256_mismatch:{recognizer_sha}")
    if wrapper_sha != EXPECTED_WRAPPER_SHA256:
        raise RuntimeError(f"wrapper_sha256_mismatch:{wrapper_sha}")

    bars = pd.read_parquet(data)
    if len(bars) != EXPECTED_DATA_ROWS:
        raise RuntimeError(f"data_rows_mismatch:{len(bars)}")

    result = study.analyze(bars)
    module_sha = sha256_file(Path(study.__file__).resolve())

    exact = {
        "schema_version": "two_wave_local_state_exit_compression_result_exact_v1",
        "issue": 624,
        "date": "2026-09-20",
        "input": {
            "data_ref": DATA_REF,
            "data_sha256": data_sha,
            "bytes": int(data_bytes),
            "rows": int(len(bars)),
        },
        "hashes": {
            "study_module_sha256": module_sha,
            "recognizer_module_sha256": recognizer_sha,
            "wrapper_module_sha256": wrapper_sha,
        },
        **_json_ready(result),
    }

    out.mkdir(parents=True, exist_ok=True)
    scored_path = out / "ISSUE624_SCORED_LEDGER.csv"
    result_path = out / "ISSUE624_RESULT_EXACT.json"
    # Canonical evidence serialization: 11 significant digits removes
    # platform/libm last-bit drift while preserving far more precision than
    # any frozen decision threshold uses.
    result["scored"].to_csv(scored_path, index=False, float_format="%.10g")
    scored_sha = sha256_file(scored_path)
    exact["hashes"]["scored_ledger_sha256"] = scored_sha

    result_path.write_text(
        json.dumps(exact, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    exact_sha = sha256_file(result_path)

    summary = {
        "status": exact["status"],
        "verdict": exact["decision"]["verdict"],
        "study_module_sha256": module_sha,
        "scored_ledger_sha256": scored_sha,
        "exact_result_sha256": exact_sha,
        "scored_test_rows": exact["meta"]["scored_test_rows"],
        "bootstrap_blocks": exact["bootstrap"]["blocks"],
        "authority": exact["authority"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.data, args.out)


if __name__ == "__main__":
    main()
