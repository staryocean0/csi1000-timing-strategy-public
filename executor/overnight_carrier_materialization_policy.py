"""Pure local policy helpers for Overnight carrier materialization.

No network access and no private credentials are used here.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tarfile
from pathlib import Path

YEARS = tuple(range(2015, 2021))
WITHHELD = [2021, 2022, 2023, 2024, 2025]
STAGE_DIR = "overnight-carrier-public-stage"
SOURCE_FILE = "overnight_carrier_source_manifest.json"
PUBLIC_SOURCE_MAP = {
    SOURCE_FILE: "overnight_carrier/source_manifest.json",
    "overnight_carrier_materialization.py": "overnight_carrier_materialization/run_study.py",
    "verify_overnight_carrier_materialization.py": "overnight_carrier_materialization/verify_study.py",
    "overnight_carrier_stage_public.py": None,
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def expected_blob(value: object) -> str:
    if not isinstance(value, dict) or set(value) != {"git_blob_sha1"}:
        raise ValueError("profile_not_immutable")
    digest = value["git_blob_sha1"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{40}", digest):
        raise ValueError("profile_not_immutable")
    return digest


def expected_stage_paths() -> set[str]:
    result = set()
    for year in YEARS:
        result.add(f"data/runtime_text_2015_2025/factor_panel_{year}.csv")
        result.add(f"data/runtime_text_2015_2025/opening_clocks_{year}.csv")
        result.add(f"data/driver_runtime_text_2015_2020/driver_external_{year}.csv")
    return result


def verify_local_public_sources(executor: Path, public_files: dict, max_bytes: int) -> dict[str, bytes]:
    if set(public_files) != set(PUBLIC_SOURCE_MAP):
        raise ValueError("public_source_set")
    output = {}
    for name, expected in public_files.items():
        path = executor / name
        if not path.is_file() or path.is_symlink() or not 1 <= path.stat().st_size <= max_bytes:
            raise ValueError("public_source_identity")
        raw = path.read_bytes()
        if git_blob_sha1(raw) != expected_blob(expected):
            raise ValueError("public_source_digest")
        output[name] = raw
    return output


def verify_stage(runner_temp: Path, source: dict) -> tuple[Path, list[dict]]:
    root = runner_temp / STAGE_DIR
    receipt_path = root / "stage_receipt.json"
    if not receipt_path.is_file():
        raise ValueError("public_stage_missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema_id") != "csi1000.overnight_carrier_public_stage@1.0" or receipt.get("status") != "passed":
        raise ValueError("public_stage_identity")
    if receipt.get("external_repository") != source.get("external_repository") or receipt.get("external_ref") != source.get("external_ref"):
        raise ValueError("public_stage_source")
    source_sha = hashlib.sha256(json.dumps(source, indent=2).encode()).hexdigest()
    if not isinstance(receipt.get("source_manifest_sha256"), str):
        raise ValueError("public_stage_manifest")
    if receipt.get("withheld_years") != WITHHELD or receipt.get("blackbox_window_opened") is not False:
        raise ValueError("public_stage_boundary")
    if receipt.get("private_credentials_used") is not False or receipt.get("production_authority") is not False:
        raise ValueError("public_stage_scope")
    rows = receipt.get("files")
    if not isinstance(rows, list) or len(rows) != 18:
        raise ValueError("public_stage_files")
    if {row.get("path") for row in rows if isinstance(row, dict)} != expected_stage_paths():
        raise ValueError("public_stage_files")
    external = root / "external"
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256"}:
            raise ValueError("public_stage_row")
        path = external / row["path"]
        if not path.is_file() or path.stat().st_size != row["bytes"] or sha256_file(path) != row["sha256"]:
            raise ValueError("public_stage_digest")
    return external, rows


def extract_authority(bundle: Path, target: Path, source: dict, max_bytes: int) -> None:
    files = source.get("private_authority", {}).get("files", {})
    if not isinstance(files, dict) or len(files) != 2:
        raise ValueError("authority_file_set")
    target.mkdir(parents=True)
    with tarfile.open(bundle, "r:") as archive:
        for name, expected in files.items():
            try:
                member = archive.getmember(name)
            except KeyError:
                raise ValueError("authority_file_missing") from None
            if not member.isfile() or not 1 <= member.size <= max_bytes:
                raise ValueError("authority_file_identity")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("authority_file_unreadable")
            raw = stream.read(max_bytes + 1)
            if len(raw) != member.size or git_blob_sha1(raw) != expected_blob(expected):
                raise ValueError("authority_file_digest")
            (target / Path(name).name).write_bytes(raw)


def install_overlay(work: Path, executor: Path, public_raw: dict[str, bytes], external_stage: Path, rows: list[dict], source: dict, max_bytes: int) -> None:
    for name, target_name in PUBLIC_SOURCE_MAP.items():
        if target_name is None:
            continue
        target = work / target_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(public_raw[name])
    extract_authority(work / "inputs" / "bundle.tar", work / "overnight_carrier" / "private_authority", source, max_bytes)
    external = work / "overnight_carrier" / "external"
    shutil.copytree(external_stage, external)
    for row in rows:
        path = external / row["path"]
        if path.stat().st_size != row["bytes"] or sha256_file(path) != row["sha256"]:
            raise ValueError("overlay_digest")
