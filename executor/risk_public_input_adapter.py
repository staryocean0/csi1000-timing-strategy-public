from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pandas as pd

PRIVATE_V3 = Path("runtime/research/risk_tool_v2_severity_persistence_v1/run_study_v3.py")
CANONICAL_ROOT = Path("inputs/canonical_v19_5m")
SOURCE_RECEIPT = CANONICAL_ROOT / "SOURCE_RECEIPT.json"


def load_private_runner():
    spec = importlib.util.spec_from_file_location("risk_v2_private_v3", PRIVATE_V3)
    if spec is None or spec.loader is None:
        raise RuntimeError("private Risk Tool runner unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def load_receipt() -> dict:
    value = json.loads(SOURCE_RECEIPT.read_text(encoding="utf-8"))
    required = {
        "schema_id",
        "repository",
        "ref",
        "files",
        "fetch_authentication",
        "market_rows_read_during_prepare",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise RuntimeError("canonical source receipt schema mismatch")
    if value["schema_id"] != "risk_tool_v2_canonical_public_data_receipt@1.0":
        raise RuntimeError("canonical source receipt identity mismatch")
    if value["fetch_authentication"] != "none" or value["market_rows_read_during_prepare"] != 0:
        raise RuntimeError("canonical source transport policy mismatch")
    return value


def load_selected_5m(_legacy_bundle: Path):
    private = load_private_runner()
    base = private.v2.base
    receipt = load_receipt()
    required = {(symbol, year) for symbol in base.SYMBOLS for year in base.YEARS}
    files = receipt.get("files")
    if not isinstance(files, dict):
        raise RuntimeError("canonical source file receipt unavailable")

    expected_paths = {
        f"data/market/5m/{symbol}/{year}.parquet": (symbol, year)
        for symbol, year in required
    }
    if set(files) != set(expected_paths):
        raise RuntimeError("canonical source set mismatch")

    frames = {}
    selected = {}
    for rel, key in sorted(expected_paths.items()):
        meta = files[rel]
        if not isinstance(meta, dict) or set(meta) != {"bytes", "git_blob_sha1", "sha256"}:
            raise RuntimeError("canonical source identity metadata mismatch")
        path = CANONICAL_ROOT / rel
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("canonical source file unavailable")
        raw = path.read_bytes()
        if len(raw) != meta["bytes"]:
            raise RuntimeError("canonical source byte mismatch")
        sha256 = hashlib.sha256(raw).hexdigest()
        blob = git_blob_sha1(raw)
        if sha256 != meta["sha256"] or blob != meta["git_blob_sha1"]:
            raise RuntimeError("canonical source digest mismatch")
        frames[key] = pd.read_parquet(io.BytesIO(raw))
        selected[f"{key[0]}|{key[1]}"] = {
            "path": rel,
            "bytes": len(raw),
            "sha256": sha256,
            "git_blob_sha1": blob,
        }

    input_receipt = {
        "schema_id": "risk_tool_v2_input_data_receipt@1.2",
        "task_id": base.TASK_ID,
        "canonical_source_repository": receipt["repository"],
        "canonical_source_ref": receipt["ref"],
        "canonical_suffix": "data/market/5m/<symbol>/<year>.parquet",
        "selected_files": selected,
        "years_read": list(base.YEARS),
        "year_2026_read": False,
        "substitute_data_used": False,
        "legacy_handoff_bundle_used_for_market_data": False,
        "market_data_transport": "immutable_public_git_blob_verified_shards",
    }
    return frames, input_receipt


def run(inputs: Path, out: Path):
    private = load_private_runner()
    private.v2.base.load_selected_5m = load_selected_5m
    result = private.v2.run(inputs, out)
    result["input_boundary"] = {
        "canonical_suffix": "data/market/5m/<symbol>/<year>.parquet",
        "source_repository": load_receipt()["repository"],
        "source_ref": load_receipt()["ref"],
        "source_selection": "exact_12_git_blob_verified_public_shards",
        "authority": "frozen_v19_load_reference",
        "other_5m_views_allowed": False,
    }
    (out / "SUMMARY.json").write_text(
        private.v2.base.json.dumps(private.v2.base.clean(result), indent=2, sort_keys=True) + "\n"
    )
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    run(args.inputs.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
