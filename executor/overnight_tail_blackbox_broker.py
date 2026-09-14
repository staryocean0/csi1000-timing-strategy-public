"""Bounded broker for one preregistered reusable Overnight tail BLACKBOX query."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
_spec = importlib.util.spec_from_file_location("_blackbox_base_broker", HERE / "research_broker.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("research broker unavailable")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
GateError = base.GateError

PROFILE_NAME = "overnight-continuous-tail-likelihood-blackbox-v1"
PROFILE_SCHEMA = "factorlab.public_overnight_tail_blackbox_profile@1.0"
PROTOCOL_PATH = ROOT / "docs/research/OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_REUSABLE_BLACKBOX_PREREG_20260914.json"
STAGE_DIR = "overnight-tail-blackbox-public-stage"
STAGE_SCHEMA = "csi1000.overnight_tail_blackbox_public_stage@1.0"
RESULT_SCHEMA = "csi1000.overnight_continuous_driver_tail_likelihood_blackbox_receipt@1.0"
IDENTITY = "overnight_continuous_driver_tail_likelihood_reusable_blackbox_v1"
SOURCE_REPO = "staryocean0/factorlab-overnight-open-lab"
SOURCE_REF = "9905c2f8942ad0a2faf106d42c1b62fd6127e646"
SAFE_RESULT_MAX_BYTES = 64 * 1024
PROFILE_KEYS = {
    "schema_id", "profile_name", "private_ref", "parent_model", "parent_dev_report",
    "public_source_files", "command", "verify_command", "command_timeout_seconds",
    "verification_timeout_seconds", "new_training", "production_authority",
}
PUBLIC_SOURCE_MAP = {
    "overnight_tail_blackbox_stage_public.py": None,
    "overnight_tail_blackbox_query.py": "overnight_tail_blackbox/run_query.py",
    "verify_overnight_tail_blackbox_query.py": "overnight_tail_blackbox/verify_query.py",
    "docs/research/OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_REUSABLE_BLACKBOX_PREREG_20260914.json": "overnight_tail_blackbox/protocol.json",
}
COMMAND = [
    "overnight_tail_blackbox/run_query.py", "--source-root", "/work/blackbox_source",
    "--model", "/work/overnight_tail_blackbox/frozen_model.json",
    "--protocol", "/work/overnight_tail_blackbox/protocol.json", "--out", "/results/study",
]
VERIFY_COMMAND = [
    "overnight_tail_blackbox/verify_query.py", "--source-root", "/work/blackbox_source",
    "--model", "/work/overnight_tail_blackbox/frozen_model.json",
    "--protocol", "/work/overnight_tail_blackbox/protocol.json", "--results", "/results/study",
]


def git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def read_config() -> dict:
    try:
        value = json.loads((HERE / "overnight_tail_blackbox_profile.json").read_text(encoding="utf-8"))
    except Exception:
        raise GateError("profile_catalog_unavailable") from None
    if not isinstance(value, dict) or set(value) != PROFILE_KEYS:
        raise GateError("profile_catalog_invalid")
    if value.get("schema_id") != PROFILE_SCHEMA or value.get("profile_name") != PROFILE_NAME:
        raise GateError("profile_catalog_invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", value.get("private_ref", "")):
        raise GateError("profile_not_immutable")
    for key in ("parent_model", "parent_dev_report"):
        spec = value.get(key)
        expected_keys = {"ref", "path", "git_blob_sha1"} if key == "parent_model" else {"ref", "path", "git_blob_sha1", "required_decision"}
        if not isinstance(spec, dict) or set(spec) != expected_keys:
            raise GateError("profile_catalog_invalid")
        if not re.fullmatch(r"[0-9a-f]{40}", spec.get("git_blob_sha1", "")):
            raise GateError("profile_not_immutable")
    public = value.get("public_source_files")
    if not isinstance(public, dict) or set(public) != set(PUBLIC_SOURCE_MAP):
        raise GateError("unapproved_public_source_set")
    for meta in public.values():
        if not isinstance(meta, dict) or set(meta) != {"git_blob_sha1"} or not re.fullmatch(r"[0-9a-f]{40}", meta["git_blob_sha1"]):
            raise GateError("profile_not_immutable")
    if value.get("command") != COMMAND or value.get("verify_command") != VERIFY_COMMAND:
        raise GateError("unapproved_command")
    if value.get("command_timeout_seconds") != 300 or value.get("verification_timeout_seconds") != 300:
        raise GateError("profile_timeout_changed")
    if value.get("new_training") is not False or value.get("production_authority") is not False:
        raise GateError("scope_not_authorized")
    return value


def local_source(name: str) -> Path:
    return ROOT / name if name.startswith("docs/") else HERE / name


def verify_public_sources(cfg: dict) -> dict[str, bytes]:
    raw_map = {}
    for name, meta in cfg["public_source_files"].items():
        path = local_source(name)
        if path.is_symlink() or not path.is_file() or not 1 <= path.stat().st_size <= base.SOURCE_BYTES_MAX:
            raise GateError("public_source_identity")
        raw = path.read_bytes()
        if git_blob_sha1(raw) != meta["git_blob_sha1"]:
            raise GateError("public_source_digest")
        raw_map[name] = raw
    return raw_map


def load_protocol(raw: bytes) -> dict:
    try:
        value = json.loads(raw)
    except Exception:
        raise GateError("blackbox_protocol_invalid") from None
    if value.get("schema_id") != "csi1000.overnight_continuous_driver_tail_likelihood_reusable_blackbox_prereg@1.0":
        raise GateError("blackbox_protocol_invalid")
    if value.get("research_identity") != IDENTITY or value.get("stage") != "result_free_reusable_blackbox_preregistration":
        raise GateError("blackbox_protocol_invalid")
    source = value.get("blackbox_source", {})
    if source.get("repository") != SOURCE_REPO or source.get("ref") != SOURCE_REF or not isinstance(source.get("files"), dict):
        raise GateError("blackbox_protocol_invalid")
    if value.get("production_authority") is not False:
        raise GateError("blackbox_protocol_invalid")
    return value


def verify_stage(protocol: dict) -> tuple[Path, list[dict]]:
    root = Path(os.environ["RUNNER_TEMP"]).resolve() / STAGE_DIR
    receipt_path = root / "stage_receipt.json"
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception:
        raise GateError("blackbox_stage_missing") from None
    if receipt.get("schema_id") != STAGE_SCHEMA or receipt.get("status") != "passed":
        raise GateError("blackbox_stage_identity")
    if receipt.get("source_repository") != SOURCE_REPO or receipt.get("source_ref") != SOURCE_REF:
        raise GateError("blackbox_stage_source")
    if receipt.get("private_credentials_used") is not False or receipt.get("row_values_persisted_to_results") is not False:
        raise GateError("blackbox_stage_scope")
    if receipt.get("production_authority") is not False:
        raise GateError("blackbox_stage_scope")
    rows = receipt.get("files")
    expected = protocol["blackbox_source"]["files"]
    if not isinstance(rows, list) or {row.get("path") for row in rows if isinstance(row, dict)} != set(expected):
        raise GateError("blackbox_stage_files")
    external = root / "external"
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "git_blob_sha1"}:
            raise GateError("blackbox_stage_row")
        meta = expected[row["path"]]
        path = external / row["path"]
        if path.is_symlink() or not path.is_file() or path.stat().st_size != meta["bytes"]:
            raise GateError("blackbox_stage_digest")
        raw = path.read_bytes()
        if git_blob_sha1(raw) != meta["git_blob_sha1"] or row["git_blob_sha1"] != meta["git_blob_sha1"] or row["bytes"] != meta["bytes"]:
            raise GateError("blackbox_stage_digest")
    return external, rows


def fetch_private_json(api, spec: dict) -> tuple[dict, bytes]:
    quoted = base.urllib.parse.quote(spec["path"], safe="/")
    ref = base.urllib.parse.quote(spec["ref"], safe="")
    meta = api.request(f"repos/{base.PRIVATE_REPO}/contents/{quoted}?ref={ref}")
    if meta.get("type") != "file" or meta.get("encoding") != "base64" or meta.get("sha") != spec["git_blob_sha1"]:
        raise GateError("parent_artifact_identity")
    try:
        raw = base64.b64decode(meta["content"])
        value = json.loads(raw)
    except Exception:
        raise GateError("parent_artifact_identity") from None
    if git_blob_sha1(raw) != spec["git_blob_sha1"] or not isinstance(value, dict):
        raise GateError("parent_artifact_digest")
    return value, raw


def validate_parent(report: dict, model: dict, cfg: dict) -> None:
    if report.get("schema_id") != "csi1000.overnight_continuous_driver_tail_likelihood_dev@1.0":
        raise GateError("parent_dev_report_invalid")
    if report.get("research_identity") != "overnight_continuous_driver_tail_likelihood_v1" or report.get("decision") != cfg["parent_dev_report"]["required_decision"]:
        raise GateError("parent_dev_report_invalid")
    if report.get("blackbox_rows_read") != 0 or report.get("production_authority") is not False:
        raise GateError("parent_dev_report_scope")
    if model.get("schema_id") != "csi1000.overnight_continuous_driver_tail_likelihood_model@1.0":
        raise GateError("parent_model_invalid")
    if model.get("research_identity") != "overnight_continuous_driver_tail_likelihood_v1" or model.get("available") is not True:
        raise GateError("parent_model_invalid")
    if model.get("blackbox_authorized") is not False or model.get("production_authority") is not False:
        raise GateError("parent_model_scope")
    if model.get("model_frozen_before_holdout_evaluation") is not True:
        raise GateError("parent_model_scope")


def load_profile(name: str) -> dict:
    if name != PROFILE_NAME:
        raise GateError("unknown_profile")
    cfg = read_config()
    public = verify_public_sources(cfg)
    protocol_raw = public["docs/research/OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_REUSABLE_BLACKBOX_PREREG_20260914.json"]
    load_protocol(protocol_raw)
    return {
        "private_ref": cfg["private_ref"],
        "manifest_sha256": hashlib.sha256(protocol_raw).hexdigest(),
        "command": cfg["command"],
        "verify_command": cfg["verify_command"],
        "command_timeout_seconds": cfg["command_timeout_seconds"],
        "verification_timeout_seconds": cfg["verification_timeout_seconds"],
        "new_training": False,
        "production_authority": False,
    }


def prepare_inputs(api, root: Path, profile: dict) -> Path:
    cfg = read_config()
    public = verify_public_sources(cfg)
    protocol_raw = public["docs/research/OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_REUSABLE_BLACKBOX_PREREG_20260914.json"]
    protocol = load_protocol(protocol_raw)
    external, rows = verify_stage(protocol)
    report, _ = fetch_private_json(api, cfg["parent_dev_report"])
    model, model_raw = fetch_private_json(api, cfg["parent_model"])
    validate_parent(report, model, cfg)
    work = root / "work"
    work.mkdir()
    source_target = work / "blackbox_source"
    shutil.copytree(external, source_target)
    for row in rows:
        path = source_target / row["path"]
        if git_blob_sha1(path.read_bytes()) != row["git_blob_sha1"]:
            raise GateError("blackbox_overlay_digest")
    query_root = work / "overnight_tail_blackbox"
    query_root.mkdir()
    (query_root / "run_query.py").write_bytes(public["overnight_tail_blackbox_query.py"])
    (query_root / "verify_query.py").write_bytes(public["verify_overnight_tail_blackbox_query.py"])
    (query_root / "protocol.json").write_bytes(protocol_raw)
    (query_root / "frozen_model.json").write_bytes(model_raw)
    return work


def safe_receipt(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or not 1 <= path.stat().st_size <= SAFE_RESULT_MAX_BYTES:
        raise GateError("blackbox_result_invalid")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise GateError("blackbox_result_invalid") from None
    allowed = {
        "schema_id", "query_id", "research_identity", "parent_model_artifact_id", "decision",
        "protocol_sha256", "source_ref", "source_file_blob_identities", "public_detail_release",
        "internal_metrics_persisted", "reused_period_is_independent_oos", "production_authority",
    }
    if not isinstance(value, dict) or set(value) != allowed:
        raise GateError("blackbox_result_surface")
    if value.get("schema_id") != RESULT_SCHEMA or value.get("research_identity") != IDENTITY:
        raise GateError("blackbox_result_identity")
    if value.get("decision") not in {"PASS", "FAIL", "INSUFFICIENT"}:
        raise GateError("blackbox_result_decision")
    if value.get("source_ref") != SOURCE_REF:
        raise GateError("blackbox_result_identity")
    if value.get("public_detail_release") is not False or value.get("internal_metrics_persisted") is not False:
        raise GateError("blackbox_result_scope")
    if value.get("reused_period_is_independent_oos") is not False or value.get("production_authority") is not False:
        raise GateError("blackbox_result_scope")
    protocol = load_protocol(PROTOCOL_PATH.read_bytes())
    expected_blobs = {path: meta["git_blob_sha1"] for path, meta in protocol["blackbox_source"]["files"].items()}
    if value.get("source_file_blob_identities") != expected_blobs:
        raise GateError("blackbox_result_source_identity")
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


_original_publish = base.publish


def publish(profile: dict) -> None:
    state, root = base.load_state()
    payload = None
    if state.get("compute_success"):
        payload = safe_receipt(root / "results" / "study" / "blackbox_receipt.json")
    _original_publish(profile)
    if payload is None:
        return
    api = base.require_private_api()
    target = f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-overnight-tail-blackbox.json"
    api.request(
        target,
        {
            "message": "Record bounded Overnight reusable BLACKBOX decision [skip ci]",
            "branch": state["branch"],
            "content": base64.b64encode(payload).decode("ascii"),
        },
        method="PUT",
    )
    ref = base.urllib.parse.quote(state["branch"], safe="")
    returned = api.request(target + "?ref=" + ref)
    try:
        readback = base64.b64decode(returned["content"])
    except Exception:
        raise GateError("blackbox_result_readback_failed") from None
    if readback != payload:
        raise GateError("blackbox_result_readback_failed")
    print("Bounded Overnight reusable BLACKBOX decision verified on the private run branch.")


base.PROFILE_NAME = PROFILE_NAME
base.load_profile = load_profile
base.prepare_inputs = prepare_inputs
base.publish = publish


def run() -> None:
    base.run()


if __name__ == "__main__":
    run()
