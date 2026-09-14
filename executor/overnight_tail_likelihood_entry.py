"""Entrypoint that makes receipts truthful and mirrors bounded DEV outputs for this profile only."""
from __future__ import annotations

import base64
import json

import overnight_tail_likelihood_broker as broker

base = broker.base
GateError = broker.GateError
_original_compute = base.compute
_original_publish = base.publish
IDENTITY = "overnight_continuous_driver_tail_likelihood_v1"
REPORT_SCHEMA = "csi1000.overnight_continuous_driver_tail_likelihood_dev@1.0"
MODEL_SCHEMA = "csi1000.overnight_continuous_driver_tail_likelihood_model@1.0"
SAFE_OUTPUT_MAX_BYTES = 256 * 1024


def _rewrite_compute_receipt():
    state, root = base.load_state()
    path = root / "results" / "compute_receipt.json"
    if not path.is_file():
        return
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise GateError("training_compute_receipt_invalid") from None
    if not isinstance(value, dict) or value.get("production_authority") is not False:
        raise GateError("training_compute_receipt_invalid")
    value["new_training"] = True
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def compute():
    caught = None
    try:
        _original_compute()
    except GateError as error:
        caught = error
    _rewrite_compute_receipt()
    if caught is not None:
        raise caught


def _rewrite_private_receipt():
    state, _ = base.load_state()
    api = base.require_private_api()
    target = f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}.json"
    ref = base.urllib.parse.quote(state["branch"], safe="")
    meta = api.request(target + "?ref=" + ref)
    try:
        raw = base64.b64decode(meta["content"])
        value = json.loads(raw)
    except Exception:
        raise GateError("training_private_receipt_invalid") from None
    if (
        not isinstance(value, dict)
        or value.get("schema_id") != base.RECEIPT_SCHEMA
        or value.get("public_run_id") != state["run_id"]
        or value.get("profile") != broker.PROFILE_NAME
        or value.get("production_authority") is not False
    ):
        raise GateError("training_private_receipt_invalid")
    value["new_training"] = True
    payload = (json.dumps(value, indent=2) + "\n").encode("utf-8")
    api.request(
        target,
        {
            "message": "Correct reviewed training scope in runner receipt [skip ci]",
            "branch": state["branch"],
            "content": base64.b64encode(payload).decode("ascii"),
            "sha": meta["sha"],
        },
        method="PUT",
    )
    returned = api.request(target + "?ref=" + ref)
    if base64.b64decode(returned["content"]) != payload:
        raise GateError("training_private_receipt_readback_failed")


def _bounded_payload(path, kind):
    if path.is_symlink() or not path.is_file() or not 1 <= path.stat().st_size <= SAFE_OUTPUT_MAX_BYTES:
        raise GateError("tail_dev_safe_output_invalid")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise GateError("tail_dev_safe_output_invalid") from None
    if not isinstance(value, dict) or value.get("research_identity") != IDENTITY:
        raise GateError("tail_dev_safe_output_invalid")
    if value.get("production_authority") is not False:
        raise GateError("tail_dev_safe_output_scope_violation")
    if kind == "report":
        if value.get("schema_id") != REPORT_SCHEMA:
            raise GateError("tail_dev_safe_output_invalid")
        if value.get("decision") not in {"DEV_PASS", "DEV_NO_PROGRESS", "DEV_INSUFFICIENT"}:
            raise GateError("tail_dev_safe_output_invalid")
        if value.get("blackbox_rows_read") != 0 or value.get("opening_clock_files_read") != 0:
            raise GateError("tail_dev_safe_output_scope_violation")
        if value.get("row_level_predictions_persisted") is not False or value.get("new_training") is not True:
            raise GateError("tail_dev_safe_output_scope_violation")
        if value.get("blackbox_authorized", False) is not False:
            raise GateError("tail_dev_safe_output_scope_violation")
    elif kind == "model":
        if value.get("schema_id") != MODEL_SCHEMA or type(value.get("available")) is not bool:
            raise GateError("tail_dev_safe_output_invalid")
        if value.get("blackbox_authorized") is not False:
            raise GateError("tail_dev_safe_output_scope_violation")
        if value.get("available") and value.get("model_frozen_before_holdout_evaluation") is not True:
            raise GateError("tail_dev_safe_output_scope_violation")
    else:
        raise GateError("tail_dev_safe_output_invalid")
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _mirror_safe_outputs():
    state, root = base.load_state()
    study = root / "results" / "study"
    payloads = {
        "overnight-tail-dev-report": _bounded_payload(study / "dev_report.json", "report"),
        "overnight-tail-frozen-model": _bounded_payload(study / "frozen_model.json", "model"),
    }
    api = base.require_private_api()
    ref = base.urllib.parse.quote(state["branch"], safe="")
    for suffix, payload in payloads.items():
        target = f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-{suffix}.json"
        api.request(
            target,
            {
                "message": "Record bounded Overnight tail DEV output [skip ci]",
                "branch": state["branch"],
                "content": base64.b64encode(payload).decode("ascii"),
            },
            method="PUT",
        )
        returned = api.request(target + "?ref=" + ref)
        try:
            readback = base64.b64decode(returned["content"])
        except Exception:
            raise GateError("tail_dev_safe_output_readback_failed") from None
        if readback != payload:
            raise GateError("tail_dev_safe_output_readback_failed")


def publish(profile):
    caught = None
    try:
        _original_publish(profile)
    except GateError as error:
        caught = error
    _rewrite_private_receipt()
    if caught is None:
        _mirror_safe_outputs()
    if caught is not None:
        raise caught


base.compute = compute
base.publish = publish


def run():
    broker.run()


if __name__ == "__main__":
    run()
