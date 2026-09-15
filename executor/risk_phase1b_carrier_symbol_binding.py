"""Identity-only symbol binding evidence for the Phase-1b frozen carrier.

This module is invoked only by the controlled private-mirror step. It reads the
already frozen SOURCE_MANIFEST.json from the pinned handoff bundle and emits
only symbol codes plus adjacent identity metadata (rows/dates/hashes/paths).
It never deserializes parquet or exports market values, returns, labels, model
outputs, scores, PnL, or other semantic data.
"""

from __future__ import annotations

import hashlib
import json
import re
import tarfile
from pathlib import Path, PurePosixPath

SCHEMA = "risk_tool_v2_phase1b_carrier_symbol_binding@1.0"
STATUS = "SYMBOL_IDENTITY_METADATA_EXTRACTED"
SYMBOL_RE = re.compile(r"^\d{6}\.(?:SH|SZ)$")
HEX_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PATHISH_RE = re.compile(r"^[A-Za-z0-9_.:/@+\-]+$")

CONTROL_KEYS = {
    "year_2026_semantic_read",
    "parquet_deserialization",
    "price_return_label_columns_read",
    "model_fit",
    "confirmatory_scoring",
    "new_training",
    "production_authority",
}
FORBIDDEN_KEY_TOKENS = {
    "open", "high", "low", "close", "price", "return", "label", "volume",
    "amount", "turnover", "vwap", "pnl", "prediction", "probability", "score",
    "bid", "ask", "trade", "signal", "feature", "target_y",
}
IDENTITY_KEY_TOKENS = {
    "row", "count", "valid", "first", "last", "min_day", "max_day", "date", "day",
    "bytes", "size", "sha", "hash", "path", "file", "name", "source", "target",
    "symbol", "filter", "select", "subset", "include", "exclude", "where",
    "transform", "offset", "frequency", "freq", "scale", "interval", "timeframe",
    "dataset", "schema", "version", "coverage", "range", "identity", "provenance",
}
STRUCTURAL_TOKENS = {
    "symbol", "filter", "select", "subset", "include", "exclude", "where",
    "transform", "migration", "slice", "partition", "universe",
}
MAX_OCCURRENCES = 512
MAX_STRUCTURAL_PATHS = 512
MAX_DEPTH = 12


def _pointer(parts: list[object]) -> str:
    def escape(piece: object) -> str:
        return str(piece).replace("~", "~0").replace("/", "~1")
    return "/" + "/".join(escape(part) for part in parts)


def _safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(path.parts) and not path.is_absolute() and ".." not in path.parts and "\\" not in name


def _forbidden_key(key: object) -> bool:
    if not isinstance(key, str) or not key or len(key) > 160:
        return True
    lowered = key.lower()
    return any(token in lowered for token in FORBIDDEN_KEY_TOKENS)


def _identity_key(key: object) -> bool:
    if _forbidden_key(key):
        return False
    assert isinstance(key, str)
    if SYMBOL_RE.fullmatch(key):
        return True
    lowered = key.lower()
    return any(token in lowered for token in IDENTITY_KEY_TOKENS)


def _safe_path_value(value: str) -> bool:
    lowered = value.lower()
    return (
        0 < len(value) <= 240
        and PATHISH_RE.fullmatch(value) is not None
        and not any(token in lowered for token in FORBIDDEN_KEY_TOKENS)
    )


def _safe_identity_scalar(key: str, value: object) -> object | None:
    lowered = key.lower()
    if isinstance(value, bool):
        return value
    if type(value) is int:
        return value
    if not isinstance(value, str):
        return None
    if SYMBOL_RE.fullmatch(value):
        return value
    if ("sha" in lowered or "hash" in lowered) and HEX_RE.fullmatch(value):
        return value
    if any(token in lowered for token in ("date", "day", "first", "last", "start", "end", "min", "max")) and DATE_RE.fullmatch(value):
        return value
    if any(token in lowered for token in ("path", "file", "name", "dataset", "source", "target")) and _safe_path_value(value):
        return value
    return None


def _identity_context(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    output: dict[str, object] = {}
    for key, child in value.items():
        if not _identity_key(key):
            continue
        assert isinstance(key, str)
        scalar = _safe_identity_scalar(key, child)
        if scalar is not None:
            output[key] = scalar
            continue
        if isinstance(child, list) and "symbol" in key.lower() and len(child) <= 64:
            symbols = [item for item in child if isinstance(item, str) and SYMBOL_RE.fullmatch(item)]
            if symbols and len(symbols) == len(child):
                output[key] = symbols
    return output


def collect_symbol_metadata(contract: object) -> tuple[list[dict], list[str]]:
    """Return only exact symbol tokens and structural selector key paths."""
    occurrences: list[dict] = []
    structural_paths: list[str] = []

    def add_occurrence(parts: list[object], kind: str, symbol: str, context: dict) -> None:
        if len(occurrences) >= MAX_OCCURRENCES:
            return
        row = {
            "json_pointer": _pointer(parts),
            "kind": kind,
            "symbol": symbol,
            "identity_context": context,
        }
        if row not in occurrences:
            occurrences.append(row)

    def walk(value: object, parts: list[object], parent_context: dict, depth: int) -> None:
        if depth > MAX_DEPTH or len(occurrences) >= MAX_OCCURRENCES:
            return
        if isinstance(value, dict):
            here_context = _identity_context(value)
            for key, child in value.items():
                if isinstance(key, str) and not _forbidden_key(key):
                    lowered = key.lower()
                    if any(token in lowered for token in STRUCTURAL_TOKENS):
                        path = _pointer(parts + [key])
                        if path not in structural_paths and len(structural_paths) < MAX_STRUCTURAL_PATHS:
                            structural_paths.append(path)
                    if SYMBOL_RE.fullmatch(key):
                        context = _identity_context(child) if isinstance(child, dict) else here_context
                        add_occurrence(parts + [key], "key", key, context)
                    if isinstance(child, str) and SYMBOL_RE.fullmatch(child):
                        add_occurrence(parts + [key], "value", child, here_context)
                    elif isinstance(child, list):
                        for index, item in enumerate(child[:128]):
                            if isinstance(item, str) and SYMBOL_RE.fullmatch(item):
                                add_occurrence(parts + [key, index], "value", item, here_context)
                walk(child, parts + [key], here_context, depth + 1)
        elif isinstance(value, list):
            for index, child in enumerate(value[:256]):
                if isinstance(child, str) and SYMBOL_RE.fullmatch(child):
                    add_occurrence(parts + [index], "value", child, parent_context)
                else:
                    walk(child, parts + [index], parent_context, depth + 1)

    walk(contract, [], {}, 0)
    return occurrences, structural_paths


def _validate_context(context: object) -> None:
    if not isinstance(context, dict) or len(context) > 64:
        raise ValueError("symbol_binding_context_invalid")
    for key, value in context.items():
        if not _identity_key(key):
            raise ValueError("symbol_binding_context_key_invalid")
        if isinstance(value, list):
            if not value or len(value) > 64 or any(not isinstance(item, str) or not SYMBOL_RE.fullmatch(item) for item in value):
                raise ValueError("symbol_binding_context_list_invalid")
        elif _safe_identity_scalar(key, value) != value:
            raise ValueError("symbol_binding_context_value_invalid")


def validate_result(value: dict, inv) -> dict:
    expected_keys = {
        "schema_id", "task_id", "status", "source_contract", "frozen_candidate",
        "source_sha256_present", "symbol_occurrences", "structural_key_paths", "controls",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise inv.GateError("symbol_binding_result_shape_invalid")
    if value.get("schema_id") != SCHEMA or value.get("task_id") != inv.TASK_ID or value.get("status") != STATUS:
        raise inv.GateError("symbol_binding_schema_or_status_invalid")
    source = value.get("source_contract")
    if not isinstance(source, dict) or set(source) != {"archive_path", "bytes", "sha256", "git_blob_sha1"}:
        raise inv.GateError("symbol_binding_source_shape_invalid")
    if source.get("bytes") != inv.SOURCE_CONTRACT_BYTES or source.get("sha256") != inv.SOURCE_CONTRACT_SHA256:
        raise inv.GateError("symbol_binding_source_identity_invalid")
    if not isinstance(source.get("archive_path"), str) or not (
        source["archive_path"] == inv.SOURCE_CONTRACT_SUFFIX
        or source["archive_path"].endswith("/" + inv.SOURCE_CONTRACT_SUFFIX)
    ):
        raise inv.GateError("symbol_binding_source_path_invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", str(source.get("git_blob_sha1", ""))):
        raise inv.GateError("symbol_binding_source_git_sha_invalid")
    if value.get("frozen_candidate") != inv.FROZEN_CANDIDATE:
        raise inv.GateError("symbol_binding_candidate_changed")
    if type(value.get("source_sha256_present")) is not bool:
        raise inv.GateError("symbol_binding_source_flag_invalid")
    controls = value.get("controls")
    if not isinstance(controls, dict) or set(controls) != CONTROL_KEYS or any(controls[key] is not False for key in CONTROL_KEYS):
        raise inv.GateError("symbol_binding_semantic_or_authority_flag")
    occurrences = value.get("symbol_occurrences")
    if not isinstance(occurrences, list) or len(occurrences) > MAX_OCCURRENCES:
        raise inv.GateError("symbol_binding_occurrences_invalid")
    try:
        for row in occurrences:
            if not isinstance(row, dict) or set(row) != {"json_pointer", "kind", "symbol", "identity_context"}:
                raise ValueError("shape")
            if not isinstance(row["json_pointer"], str) or not row["json_pointer"].startswith("/"):
                raise ValueError("pointer")
            if row["kind"] not in {"key", "value"} or not isinstance(row["symbol"], str) or not SYMBOL_RE.fullmatch(row["symbol"]):
                raise ValueError("symbol")
            _validate_context(row["identity_context"])
        paths = value.get("structural_key_paths")
        if not isinstance(paths, list) or len(paths) > MAX_STRUCTURAL_PATHS:
            raise ValueError("paths")
        for path in paths:
            if not isinstance(path, str) or not path.startswith("/") or len(path) > 1000:
                raise ValueError("path")
            lowered = path.lower()
            if any(token in lowered for token in FORBIDDEN_KEY_TOKENS):
                raise ValueError("forbidden_path")
            if not any(token in lowered for token in STRUCTURAL_TOKENS):
                raise ValueError("nonstructural_path")
    except ValueError as error:
        raise inv.GateError("symbol_binding_evidence_invalid") from error
    return value


def extract_from_bundle(bundle_path: Path, inv) -> dict:
    profile = inv.load_profile()
    if bundle_path.stat().st_size != profile["bundle_member"]["bytes"] or inv.sha(bundle_path) != profile["bundle_member"]["sha256"]:
        raise inv.GateError("symbol_binding_bundle_identity_mismatch")

    with tarfile.open(bundle_path, "r:") as archive:
        members = [member for member in archive.getmembers() if member.isfile()]
        if any(not _safe_member_name(member.name) for member in members):
            raise inv.GateError("symbol_binding_invalid_bundle_member")
        by_name = {member.name: member for member in members}
        if len(by_name) != len(members):
            raise inv.GateError("symbol_binding_duplicate_bundle_member")
        names = [name for name in by_name if name == inv.SOURCE_CONTRACT_SUFFIX or name.endswith("/" + inv.SOURCE_CONTRACT_SUFFIX)]
        if len(names) != 1:
            raise inv.GateError("symbol_binding_source_not_unique")
        name = names[0]
        member = by_name[name]
        if member.size != inv.SOURCE_CONTRACT_BYTES:
            raise inv.GateError("symbol_binding_source_size_mismatch")
        stream = archive.extractfile(member)
        if stream is None:
            raise inv.GateError("symbol_binding_source_unreadable")
        raw = stream.read(inv.SOURCE_CONTRACT_BYTES + 1)
        if len(raw) != inv.SOURCE_CONTRACT_BYTES or hashlib.sha256(raw).hexdigest() != inv.SOURCE_CONTRACT_SHA256:
            raise inv.GateError("symbol_binding_source_digest_mismatch")

    try:
        contract = json.loads(raw)
    except Exception:
        raise inv.GateError("symbol_binding_source_json_invalid") from None
    if not isinstance(contract, (dict, list)):
        raise inv.GateError("symbol_binding_source_root_invalid")
    occurrences, structural_paths = collect_symbol_metadata(contract)
    raw_text = raw.decode("utf-8")
    git_sha1 = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    result = {
        "schema_id": SCHEMA,
        "task_id": inv.TASK_ID,
        "status": STATUS,
        "source_contract": {
            "archive_path": name,
            "bytes": inv.SOURCE_CONTRACT_BYTES,
            "sha256": inv.SOURCE_CONTRACT_SHA256,
            "git_blob_sha1": git_sha1,
        },
        "frozen_candidate": dict(inv.FROZEN_CANDIDATE),
        "source_sha256_present": inv.FROZEN_CANDIDATE["source_sha256"] in raw_text,
        "symbol_occurrences": occurrences,
        "structural_key_paths": structural_paths,
        "controls": {key: False for key in CONTROL_KEYS},
    }
    return validate_result(result, inv)
