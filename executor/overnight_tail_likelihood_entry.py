"""Entrypoint that makes receipts truthful for the dedicated training-enabled profile only."""
from __future__ import annotations

import base64
import json

import overnight_tail_likelihood_broker as broker

base = broker.base
GateError = broker.GateError
_original_compute = base.compute
_original_publish = base.publish


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


def publish(profile):
    caught = None
    try:
        _original_publish(profile)
    except GateError as error:
        caught = error
    _rewrite_private_receipt()
    if caught is not None:
        raise caught


base.compute = compute
base.publish = publish


def run():
    broker.run()


if __name__ == "__main__":
    run()
