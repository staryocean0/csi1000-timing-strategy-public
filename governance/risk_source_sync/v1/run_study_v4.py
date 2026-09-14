from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import re
import tarfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
V3_PATH = HERE / "run_study_v3.py"
_spec = importlib.util.spec_from_file_location("risk_v2_phase1_v3_runner", V3_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("v3 runner unavailable")
v3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v3)


def _meta(value):
    return (
        isinstance(value, dict)
        and set(value) == {"bytes", "sha256"}
        and type(value.get("bytes")) is int
        and value["bytes"] >= 0
        and isinstance(value.get("sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is not None
    )


def load_selected_5m(bundle: Path):
    """Read the canonical V19 5m set directly from the signed handoff bundle.

    The reviewed handoff asset is itself the 2,813-member tar. There is no
    requirement for a second nested tar layer. Only exact canonical suffixes
    accepted by v3.selected_key are read, and every selected member is checked
    against the signed BUNDLE_MANIFEST before parquet decoding.
    """
    base = v3.v2.base
    outer_sha = base.sha256_file(bundle)
    required = {(s, y) for s in base.SYMBOLS for y in base.YEARS}
    frames = {}
    receipts = {}

    with tarfile.open(bundle, "r:") as outer:
        members = outer.getmembers()
        if not members or any(not member.isfile() for member in members):
            raise RuntimeError("outer bundle contains non-file member")
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise RuntimeError("duplicate outer member")
        for name in names:
            base.safe_member(name)
        if "BUNDLE_MANIFEST.json" not in names:
            raise RuntimeError("missing BUNDLE_MANIFEST.json")

        manifest_stream = outer.extractfile("BUNDLE_MANIFEST.json")
        if manifest_stream is None:
            raise RuntimeError("BUNDLE_MANIFEST.json unreadable")
        manifest = json.load(manifest_stream)
        if manifest.get("schema") != "csi1000_handoff_bundle@1":
            raise RuntimeError("unexpected bundle manifest schema")
        expected = manifest.get("files")
        if not isinstance(expected, dict) or set(names) != set(expected) | {"BUNDLE_MANIFEST.json"}:
            raise RuntimeError("outer member set mismatch")

        for member in members:
            key = v3.selected_key(member.name)
            if key is None:
                continue
            if key in frames:
                raise RuntimeError(f"duplicate canonical 5m source for {key}: {member.name}")
            expected_meta = expected.get(member.name)
            if not _meta(expected_meta):
                raise RuntimeError("canonical member metadata invalid")
            if member.size != expected_meta["bytes"]:
                raise RuntimeError("canonical member size mismatch")
            stream = outer.extractfile(member)
            if stream is None:
                raise RuntimeError("canonical member unreadable")
            raw = stream.read()
            if len(raw) != member.size:
                raise RuntimeError("short canonical member read")
            digest = hashlib.sha256(raw).hexdigest()
            if digest != expected_meta["sha256"]:
                raise RuntimeError("canonical member digest mismatch")
            frames[key] = pd.read_parquet(io.BytesIO(raw))
            receipts[f"{key[0]}|{key[1]}"] = {
                "path": member.name,
                "bytes": len(raw),
                "sha256": digest,
            }

    if set(frames) != required:
        missing = sorted(required - set(frames))
        extra = sorted(set(frames) - required)
        raise RuntimeError(f"canonical V19 direct member set mismatch missing={missing} extra={extra}")

    receipt = {
        "schema_id": "risk_tool_v2_input_data_receipt@1.2",
        "task_id": v3.v2.base.TASK_ID,
        "bundle_tar_sha256": outer_sha,
        "bundle_member_count": len(expected),
        "data_member_selection": "direct_signed_outer_members_complete_canonical_v19_5m_set",
        "canonical_suffix": "data/market/5m/<symbol>/<year>.parquet",
        "selected_files": receipts,
        "years_read": list(v3.v2.base.YEARS),
        "year_2026_read": False,
        "substitute_data_used": False,
    }
    return frames, receipt


def run(inputs: Path, out: Path):
    # Patch only physical input discovery. Scientific state/model code and the
    # independent verifier remain exactly the frozen v2/v3 implementations.
    v3.v2.base.selected_key = v3.selected_key
    v3.v2.base.load_selected_5m = load_selected_5m
    result = v3.v2.run(inputs, out)
    result["input_boundary"] = {
        "canonical_suffix": "data/market/5m/<symbol>/<year>.parquet",
        "outer_member_selection": "direct_signed_outer_members_complete_canonical_v19_5m_set",
        "authority": "frozen_v19_load_reference",
        "other_5m_views_allowed": False,
    }
    (out / "SUMMARY.json").write_text(
        v3.v2.base.json.dumps(v3.v2.base.clean(result), indent=2, sort_keys=True) + "\n"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.inputs.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
