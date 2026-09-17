"""Fixed no-argument market entry for issue #352 carrier qualification."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import pandas as pd
from wave_segmentation_carrier_qualification_v1 import FILES, build_report

INPUTS = Path("/work/inputs")
OUT = Path("/results/study")
PROTOCOL = Path("/work/segmentation_carrier/protocol.json")
MAX_RESULT_BYTES = 8 * 1024 * 1024


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git_blob(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def clean(value):
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("nonfinite_output")
        return value
    if hasattr(value, "item"):
        return clean(value.item())
    raise TypeError(type(value).__name__)


def encode(value) -> bytes:
    return (json.dumps(clean(value), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def load_protocol() -> dict:
    if PROTOCOL.is_symlink() or not PROTOCOL.is_file():
        raise RuntimeError("protocol_path")
    value = json.loads(PROTOCOL.read_text())
    if value.get("schema_id") != "csi1000.segmentation_carrier_qualification_protocol@1.0":
        raise RuntimeError("protocol_identity")
    if value.get("profile") != "two-wave-segmentation-carrier-qualification-v1":
        raise RuntimeError("profile_identity")
    if set(value.get("files", {})) != set(FILES):
        raise RuntimeError("file_set")
    if value.get("comparison", {}).get("abs_tolerance") != 1e-10 or value.get("comparison", {}).get("rel_tolerance") != 1e-12:
        raise RuntimeError("tolerance_drift")
    return value


def load_inputs(protocol: dict) -> tuple[dict[str, pd.DataFrame], dict, dict]:
    frames = {}; identities = {}; rows = {}
    if INPUTS.is_symlink() or not INPUTS.is_dir():
        raise RuntimeError("input_root")
    actual = {path.name for path in INPUTS.iterdir()}
    if actual != set(FILES):
        raise RuntimeError("input_directory_set")
    for name in FILES:
        path = INPUTS / name; meta = protocol["files"][name]
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise RuntimeError("input_file_type")
        if path.stat().st_size != meta["bytes"] or sha256(path) != meta["sha256"] or git_blob(path) != meta["git_blob_sha1"]:
            raise RuntimeError("input_identity")
        frame = pd.read_parquet(path)
        frames[name] = frame
        rows[name] = int(meta["declared_rows"])
        identities[name] = {"bytes": int(path.stat().st_size), "sha256": meta["sha256"],
                            "git_blob_sha1": meta["git_blob_sha1"]}
    return frames, rows, identities


def main() -> None:
    if OUT.exists():
        raise RuntimeError("fresh_output_required")
    protocol = load_protocol()
    frames, declared_rows, identities = load_inputs(protocol)
    report = build_report(frames, declared_rows)
    report["input_identity"] = identities
    report["source_provenance"] = {"repository": protocol["external_repository"], "ref": protocol["external_ref"],
        "datahub_export_commit": protocol["datahub_provenance"]["export_commit"]}
    OUT.mkdir(parents=True)
    raw = encode(report)
    if len(raw) > MAX_RESULT_BYTES:
        raise RuntimeError("report_bound")
    (OUT / "report.json").write_bytes(raw)
    manifest = {"schema_id": "csi1000.segmentation_carrier_result_manifest@1.0",
        "files": {"report.json": {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}},
        "input_identity": identities, "new_training": False, "production_authority": False}
    manifest_raw = encode(manifest)
    if len(manifest_raw) > 1024 * 1024:
        raise RuntimeError("manifest_bound")
    (OUT / "manifest.json").write_bytes(manifest_raw)


if __name__ == "__main__":
    main()
