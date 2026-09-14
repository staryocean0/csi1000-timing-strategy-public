"""Static public broker policy for the frozen Risk Tool 2.0 severity-persistence study.

This module deliberately reuses the reviewed research broker transport/security flow while
replacing only its exact profile allowlist. It does not permit arbitrary private source or
commands. The legacy handoff broker remains unchanged.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_legacy_research_broker", HERE / "research_broker.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("research broker unavailable")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

GateError = base.GateError

PROFILE_NAME = "risk-v2-severity-persistence-v1"
SOURCE_PATHS = (
    "runtime/research/risk_tool_v2_severity_persistence_v1/run_study.py",
    "runtime/research/risk_tool_v2_severity_persistence_v1/run_study_v2.py",
    "runtime/research/risk_tool_v2_severity_persistence_v1/verify_study.py",
    "runtime/research/risk_tool_v2_severity_persistence_v1/verify_study_v2.py",
    "docs/research/RISK_TOOL_V2_SEVERITY_PERSISTENCE_PROTOCOL_20260914.json",
    "handoff/INPUT_MANIFEST.json",
)
MANIFEST_PATH = "handoff/INPUT_MANIFEST.json"
COMMAND = [
    "runtime/research/risk_tool_v2_severity_persistence_v1/run_study_v2.py",
    "--inputs",
    "/work/inputs",
    "--out",
    "/results/study",
]
VERIFY_COMMAND = [
    "runtime/research/risk_tool_v2_severity_persistence_v1/verify_study_v2.py",
    "--inputs",
    "/work/inputs",
    "--results",
    "/results/study",
]


def digest_pair(value, min_bytes=1, max_bytes=base.SOURCE_BYTES_MAX):
    """Accept legacy SHA-256 pairs or immutable Git blob SHA-1 pairs.

    Git blob identity is used only for the new private source files because the GitHub
    contents API exposes that object id directly. The raw bytes are independently hashed
    again using Git's blob framing before use.
    """
    if not isinstance(value, dict):
        raise GateError("unknown_profile_field")
    keys = set(value)
    if keys not in ({"bytes", "sha256"}, {"bytes", "git_blob_sha1"}):
        raise GateError("unknown_profile_field")
    size = value["bytes"]
    if type(size) is not int or size < min_bytes or size > max_bytes:
        raise GateError("profile_file_size_invalid")
    if "sha256" in value:
        if not isinstance(value["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]):
            raise GateError("profile_not_immutable")
    else:
        if not isinstance(value["git_blob_sha1"], str) or not re.fullmatch(r"[0-9a-f]{40}", value["git_blob_sha1"]):
            raise GateError("profile_not_immutable")


def fetch_source_file(api, path, ref, expected):
    quoted = base.urllib.parse.quote(path, safe="/")
    meta = api.request(f"repos/{base.PRIVATE_REPO}/contents/{quoted}?ref={ref}")
    if meta.get("type") != "file" or meta.get("encoding") != "base64" or meta.get("size") != expected["bytes"]:
        raise GateError("source_blob_identity_failed")
    try:
        raw = base64.b64decode(meta["content"])
    except Exception:
        raise GateError("source_blob_identity_failed") from None
    if len(raw) != expected["bytes"]:
        raise GateError("source_blob_identity_failed")
    if "git_blob_sha1" in expected:
        digest = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        if meta.get("sha") != expected["git_blob_sha1"] or digest != expected["git_blob_sha1"]:
            raise GateError("source_blob_digest_mismatch")
    elif hashlib.sha256(raw).hexdigest() != expected["sha256"]:
        raise GateError("source_blob_digest_mismatch")
    return raw


# Patch only the immutable policy surface of the reviewed broker. Transport, isolation,
# result collection, cleanup and private writeback code are reused unchanged.
base.PROFILE_NAME = PROFILE_NAME
base.SOURCE_PATHS = SOURCE_PATHS
base.MANIFEST_PATH = MANIFEST_PATH
base.COMMAND = COMMAND
base.VERIFY_COMMAND = VERIFY_COMMAND
base._digest_pair = digest_pair
base.fetch_source_file = fetch_source_file


def run():
    base.run()


if __name__ == "__main__":
    run()
