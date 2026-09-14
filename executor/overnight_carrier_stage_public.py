"""Stage fixed public 2015-2020 Overnight carrier files before private credentials exist."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "overnight_carrier_source_manifest.json"
EXTERNAL_REPO = "staryocean0/factorlab-overnight-open-lab"
EXTERNAL_REF = "9905c2f8942ad0a2faf106d42c1b62fd6127e646"
YEARS = tuple(range(2015, 2021))
WITHHELD = [2021, 2022, 2023, 2024, 2025]
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024


def git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def safe_rel(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or "\\" in value or str(path) != value:
        raise RuntimeError("unsafe_source_path")
    return value


def expected_blob(value: object) -> str:
    if not isinstance(value, dict) or set(value) != {"git_blob_sha1"}:
        raise RuntimeError("source_not_immutable")
    digest = value["git_blob_sha1"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{40}", digest):
        raise RuntimeError("source_not_immutable")
    return digest


def fetch_raw(path: str, blob: object | None = None, size: int | None = None, digest: str | None = None) -> bytes:
    safe_rel(path)
    url = f"https://raw.githubusercontent.com/{EXTERNAL_REPO}/{EXTERNAL_REF}/{urllib.parse.quote(path, safe='/')}"
    request = urllib.request.Request(url, headers={"User-Agent": "csi1000-overnight-carrier-stage/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(MAX_FILE_BYTES + 1)
    if not 1 <= len(raw) <= MAX_FILE_BYTES:
        raise RuntimeError("source_size_invalid")
    if blob is not None and git_blob_sha1(raw) != expected_blob(blob):
        raise RuntimeError("source_blob_mismatch")
    if size is not None and len(raw) != size:
        raise RuntimeError("source_size_mismatch")
    if digest is not None and hashlib.sha256(raw).hexdigest() != digest:
        raise RuntimeError("source_digest_mismatch")
    return raw


def records(runtime: dict, driver: dict) -> list[dict]:
    if runtime.get("schema_id") != "overnight_runtime_text_carrier@1.0":
        raise RuntimeError("runtime_manifest_identity")
    if runtime.get("published_year_window") != [2015, 2020] or runtime.get("withheld_years") != WITHHELD:
        raise RuntimeError("runtime_boundary")
    if driver.get("schema_id") != "overnight_driver_runtime_text_2015_2020@1.0":
        raise RuntimeError("driver_manifest_identity")
    if driver.get("withheld_years") != WITHHELD or driver.get("blackbox_opened") is not False:
        raise RuntimeError("driver_boundary")
    out = []
    for family, stem in (("factor_panel", "factor_panel"), ("opening_clocks", "opening_clocks")):
        rows = runtime.get("outputs", {}).get(family, {})
        if set(rows) != {str(y) for y in YEARS}:
            raise RuntimeError("runtime_year_set")
        for year in YEARS:
            meta = rows[str(year)]
            path = f"data/runtime_text_2015_2025/{stem}_{year}.csv"
            if meta.get("path") != path:
                raise RuntimeError("runtime_path_drift")
            out.append({"path": path, "bytes": meta["bytes"], "sha256": meta["sha256"]})
    rows = driver.get("outputs", {})
    if set(rows) != {str(y) for y in YEARS}:
        raise RuntimeError("driver_year_set")
    for year in YEARS:
        meta = rows[str(year)]
        path = f"data/driver_runtime_text_2015_2020/driver_external_{year}.csv"
        if meta.get("path") != path:
            raise RuntimeError("driver_path_drift")
        out.append({"path": path, "bytes": meta["bytes"], "sha256": meta["sha256"]})
    if len(out) != 18 or sum(row["bytes"] for row in out) > MAX_TOTAL_BYTES:
        raise RuntimeError("carrier_budget")
    return out


def main() -> None:
    if os.environ.get("FACTORLAB_PRIVATE_TOKEN"):
        raise RuntimeError("private_token_must_not_reach_public_stage")
    source_raw = SOURCE.read_bytes()
    source = json.loads(source_raw)
    if source.get("schema_id") != "csi1000.overnight_carrier_source_manifest@1.0":
        raise RuntimeError("source_manifest_identity")
    if source.get("external_repository") != EXTERNAL_REPO or source.get("external_ref") != EXTERNAL_REF:
        raise RuntimeError("external_source_identity")
    if source.get("required_years") != list(YEARS) or source.get("withheld_years") != WITHHELD:
        raise RuntimeError("evidence_boundary")
    manifests = source.get("external_manifests", {})
    expected_paths = {
        "data/runtime_text_2015_2025/manifest.json",
        "data/driver_runtime_text_2015_2020/manifest.json",
    }
    if set(manifests) != expected_paths:
        raise RuntimeError("manifest_set")
    root = Path(os.environ["RUNNER_TEMP"]) / "overnight-carrier-public-stage"
    if root.exists():
        shutil.rmtree(root)
    external = root / "external"
    external.mkdir(parents=True)
    parsed = {}
    for path in sorted(expected_paths):
        raw = fetch_raw(path, blob=manifests[path])
        target = external / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        parsed[path] = json.loads(raw)
    rows = records(
        parsed["data/runtime_text_2015_2025/manifest.json"],
        parsed["data/driver_runtime_text_2015_2020/manifest.json"],
    )
    for row in rows:
        raw = fetch_raw(row["path"], size=row["bytes"], digest=row["sha256"])
        target = external / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    receipt = {
        "schema_id": "csi1000.overnight_carrier_public_stage@1.0",
        "status": "passed",
        "external_repository": EXTERNAL_REPO,
        "external_ref": EXTERNAL_REF,
        "source_manifest_sha256": hashlib.sha256(source_raw).hexdigest(),
        "files": sorted(rows, key=lambda row: row["path"]),
        "withheld_years": WITHHELD,
        "blackbox_window_opened": False,
        "private_credentials_used": False,
        "production_authority": False,
    }
    (root / "stage_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Fixed public Overnight carrier source staged and verified without private credentials.")


if __name__ == "__main__":
    main()
