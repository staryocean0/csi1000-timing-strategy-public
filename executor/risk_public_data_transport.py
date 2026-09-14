from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "risk_canonical_public_data.json"
ADAPTER_PATH = HERE / "risk_public_input_adapter.py"
DEST_ROOT = Path("inputs/canonical_v19_5m")
EXPECTED_REPOSITORY = "staryocean0/factorlab-trend-reversion-regime-lab"
EXPECTED_ROOT = "data/market/5m"
SYMBOLS = ("000688.SH", "000852.SH")
YEARS = (2020, 2021, 2022, 2023, 2024, 2025)
MAX_FILE_BYTES = 2 * 1024 * 1024


class TransportError(RuntimeError):
    pass


def _safe_relative(value: str) -> PurePosixPath:
    p = PurePosixPath(value)
    if p.is_absolute() or not p.parts or any(part in {"", ".", ".."} for part in p.parts):
        raise TransportError("canonical public path invalid")
    return p


def _git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def _load_config() -> dict:
    try:
        value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        raise TransportError("canonical public config unavailable") from None
    if not isinstance(value, dict) or set(value) != {"schema_id", "repository", "ref", "root", "files"}:
        raise TransportError("canonical public config schema mismatch")
    if value["schema_id"] != "risk_tool_v2_canonical_public_data@1.0":
        raise TransportError("canonical public config identity mismatch")
    if value["repository"] != EXPECTED_REPOSITORY or value["root"] != EXPECTED_ROOT:
        raise TransportError("canonical public repository drift")
    if not isinstance(value["ref"], str) or not re.fullmatch(r"[0-9a-f]{40}", value["ref"]):
        raise TransportError("canonical public ref not immutable")
    files = value["files"]
    expected_paths = {
        f"data/market/5m/{symbol}/{year}.parquet"
        for symbol in SYMBOLS
        for year in YEARS
    }
    if not isinstance(files, dict) or set(files) != expected_paths:
        raise TransportError("canonical public source set mismatch")
    for path, meta in files.items():
        _safe_relative(path)
        if not isinstance(meta, dict) or set(meta) != {"bytes", "git_blob_sha1"}:
            raise TransportError("canonical public source metadata mismatch")
        if type(meta["bytes"]) is not int or meta["bytes"] < 1 or meta["bytes"] > MAX_FILE_BYTES:
            raise TransportError("canonical public source size invalid")
        if not isinstance(meta["git_blob_sha1"], str) or not re.fullmatch(r"[0-9a-f]{40}", meta["git_blob_sha1"]):
            raise TransportError("canonical public source blob invalid")
    return value


def _download(repo: str, ref: str, path: str, expected: dict) -> bytes:
    quoted = "/".join(urllib.parse.quote(part, safe="") for part in _safe_relative(path).parts)
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/{quoted}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "csi1000-risk-public-data-transport/1.0",
            "Accept": "application/octet-stream",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            final = urllib.parse.urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname != "raw.githubusercontent.com":
                raise TransportError("canonical public redirect rejected")
            raw = response.read(expected["bytes"] + 1)
    except TransportError:
        raise
    except Exception:
        raise TransportError("canonical public download failed") from None
    if len(raw) != expected["bytes"]:
        raise TransportError("canonical public source byte mismatch")
    if _git_blob_sha1(raw) != expected["git_blob_sha1"]:
        raise TransportError("canonical public source digest mismatch")
    return raw


def materialize(root: Path) -> dict:
    config = _load_config()
    work = root / "work"
    destination_root = work / DEST_ROOT
    if destination_root.exists():
        raise TransportError("canonical public destination already exists")
    destination_root.mkdir(parents=True)

    receipt_files = {}
    for rel, expected in sorted(config["files"].items()):
        raw = _download(config["repository"], config["ref"], rel, expected)
        destination = destination_root.joinpath(*_safe_relative(rel).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink() or destination.exists():
            raise TransportError("canonical public destination collision")
        destination.write_bytes(raw)
        receipt_files[rel] = {
            "bytes": len(raw),
            "git_blob_sha1": expected["git_blob_sha1"],
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    receipt = {
        "schema_id": "risk_tool_v2_canonical_public_data_receipt@1.0",
        "repository": config["repository"],
        "ref": config["ref"],
        "files": receipt_files,
        "fetch_authentication": "none",
        "market_rows_read_during_prepare": 0,
    }
    (destination_root / "SOURCE_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    adapter_raw = ADAPTER_PATH.read_bytes()
    adapter_destination = work / "risk_public_input_adapter.py"
    if adapter_destination.exists() or adapter_destination.is_symlink():
        raise TransportError("public input adapter destination collision")
    adapter_destination.write_bytes(adapter_raw)
    return receipt
