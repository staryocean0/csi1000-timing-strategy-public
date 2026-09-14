#!/usr/bin/env python3
"""Stage exact public BLACKBOX source blobs before any private credential exists."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROTOCOL = ROOT / "docs/research/OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_REUSABLE_BLACKBOX_PREREG_20260914.json"
STAGE_DIR = "overnight-tail-blackbox-public-stage"
SCHEMA = "csi1000.overnight_tail_blackbox_public_stage@1.0"
MAX_FILE_BYTES = 2 * 1024 * 1024


def git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def load_protocol() -> dict:
    value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if value.get("schema_id") != "csi1000.overnight_continuous_driver_tail_likelihood_reusable_blackbox_prereg@1.0":
        raise RuntimeError("blackbox_protocol_identity")
    if value.get("stage") != "result_free_reusable_blackbox_preregistration":
        raise RuntimeError("blackbox_protocol_stage")
    source = value.get("blackbox_source")
    if not isinstance(source, dict) or source.get("repository") != "staryocean0/factorlab-overnight-open-lab":
        raise RuntimeError("blackbox_source_identity")
    if source.get("ref") != "9905c2f8942ad0a2faf106d42c1b62fd6127e646":
        raise RuntimeError("blackbox_source_ref")
    files = source.get("files")
    if not isinstance(files, dict) or len(files) != 5:
        raise RuntimeError("blackbox_source_set")
    return value


def download(repo: str, ref: str, path: str, meta: dict) -> bytes:
    if set(meta) != {"git_blob_sha1", "bytes"}:
        raise RuntimeError("blackbox_source_meta")
    size = meta["bytes"]
    if type(size) is not int or not 1 <= size <= MAX_FILE_BYTES:
        raise RuntimeError("blackbox_source_size")
    quoted = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/{quoted}"
    request = urllib.request.Request(url, headers={"User-Agent": "csi1000-reviewed-blackbox-stage/1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        final = urllib.parse.urlparse(response.geturl())
        if final.scheme != "https" or final.hostname != "raw.githubusercontent.com":
            raise RuntimeError("blackbox_source_redirect")
        raw = response.read(size + 1)
    if len(raw) != size or git_blob_sha1(raw) != meta["git_blob_sha1"]:
        raise RuntimeError("blackbox_source_digest")
    return raw


def main() -> int:
    if os.environ.get("FACTORLAB_PRIVATE_TOKEN"):
        raise RuntimeError("private_token_must_not_reach_public_blackbox_stage")
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    root = runner_temp / STAGE_DIR
    if root.exists():
        raise RuntimeError("blackbox_stage_already_exists")
    protocol = load_protocol()
    source = protocol["blackbox_source"]
    external = root / "external"
    external.mkdir(parents=True)
    rows = []
    try:
        for path, meta in sorted(source["files"].items()):
            raw = download(source["repository"], source["ref"], path, meta)
            target = external / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            rows.append({"path": path, "bytes": len(raw), "git_blob_sha1": git_blob_sha1(raw)})
        receipt = {
            "schema_id": SCHEMA,
            "status": "passed",
            "source_repository": source["repository"],
            "source_ref": source["ref"],
            "files": rows,
            "private_credentials_used": False,
            "row_values_persisted_to_results": False,
            "production_authority": False,
        }
        (root / "stage_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise
    print("Fixed public BLACKBOX source blobs staged and verified without private credentials.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
