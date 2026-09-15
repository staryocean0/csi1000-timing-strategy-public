"""Bounded public-to-private sync for the accepted Risk Tool consumer adapter.

This is governance infrastructure, not a research runner. It can only stage or
fast-forward one fixed pair of public-origin files into one fixed private base.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
_spec = importlib.util.spec_from_file_location("_csi1000_broker", HERE / "broker.py")
broker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(broker)
GateError = broker.GateError
GitHub = broker.GitHub
PUBLIC_REPO = broker.PUBLIC_REPO
PRIVATE_REPO = broker.PRIVATE_REPO

SYNC_ID = "risk-v2-consumer-runtime-import-20260915-v1"
PRIVATE_BASE_BRANCH = "main"
PRIVATE_BASE_SHA = "67effb80f51228f6129dca5c4f7971a0bb6c7f15"
PRIVATE_BRANCH = "sync/public-runtime/risk-v2-consumer-runtime-import-20260915-v1"
REQUEST_PATH = ROOT / "governance/private_sync/v1/risk_tool_v2/runtime_consumer_request.json"
TARGETS = (
    {
        "source": "executor/risk_probability_reliability_consumer_v1.py",
        "target": "runtime/src/factor_lab/market_state/risk_probability_reliability_consumer_v1.py",
        "expected_public_blob": "bfe25858f30b007505519ebd262f8396c508f519",
    },
    {
        "source": "governance/private_sync/v1/risk_tool_v2/test_risk_probability_reliability_consumer_integration_v1.py",
        "target": "runtime/tests/unit/test_risk_probability_reliability_consumer_integration_v1.py",
        "expected_public_blob": "f4ac613b9b696530de55f1d07d33cf28ae143cf4",
    },
)


def _git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _source_bytes(row: dict[str, str]) -> bytes:
    path = ROOT / row["source"]
    if path.is_symlink() or not path.is_file():
        raise GateError("runtime_sync_source_missing")
    raw = path.read_bytes()
    if not raw or len(raw) > 128 * 1024:
        raise GateError("runtime_sync_source_size_invalid")
    if _git_blob_sha(raw) != row["expected_public_blob"]:
        raise GateError("runtime_sync_source_identity_drift")
    return raw


def _load_request() -> dict:
    try:
        value = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        raise GateError("runtime_sync_request_invalid") from None
    expected = {"schema_id", "sync_id", "phase", "private_base_sha", "targets"}
    if not isinstance(value, dict) or set(value) != expected:
        raise GateError("runtime_sync_request_invalid")
    if value["schema_id"] != "csi1000.private_runtime_sync_request@1.0":
        raise GateError("runtime_sync_request_invalid")
    if value["sync_id"] != SYNC_ID or value["private_base_sha"] != PRIVATE_BASE_SHA:
        raise GateError("runtime_sync_request_identity_drift")
    if value["phase"] not in {"stage", "merge"}:
        raise GateError("runtime_sync_request_phase_invalid")
    if value["targets"] != [row["target"] for row in TARGETS]:
        raise GateError("runtime_sync_request_target_drift")
    return value


def self_test() -> None:
    if PRIVATE_REPO != "staryocean0/csi1000-timing-strategy-private":
        raise GateError("private_identity_drift")
    if not re.fullmatch(r"[0-9a-f]{40}", PRIVATE_BASE_SHA):
        raise GateError("private_base_not_immutable")
    if not PRIVATE_BRANCH.startswith("sync/public-runtime/"):
        raise GateError("private_branch_scope_drift")
    names = [row["target"] for row in TARGETS]
    if len(names) != 2 or len(names) != len(set(names)):
        raise GateError("runtime_sync_target_scope_drift")
    if names != [
        "runtime/src/factor_lab/market_state/risk_probability_reliability_consumer_v1.py",
        "runtime/tests/unit/test_risk_probability_reliability_consumer_integration_v1.py",
    ]:
        raise GateError("runtime_sync_target_scope_drift")
    for row in TARGETS:
        if not re.fullmatch(r"[0-9a-f]{40}", row["expected_public_blob"]):
            raise GateError("public_blob_not_immutable")
        _source_bytes(row)
    _load_request()
    print("Risk consumer runtime sync contract is structurally valid.")


def _require_context() -> None:
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != PUBLIC_REPO
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
        or env.get("GITHUB_EVENT_NAME") not in {"workflow_dispatch", "push"}
    ):
        raise GateError("not_approved_runtime_sync_event")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")):
        raise GateError("invalid_run_identity")


def _api() -> GitHub:
    token = os.environ.get("FACTORLAB_PRIVATE_TOKEN")
    if not token:
        raise GateError("private_token_missing")
    api = GitHub(token)
    api.private_identity()
    return api


def _require_private_base(api: GitHub) -> None:
    meta = api.request(f"repos/{PRIVATE_REPO}/branches/{PRIVATE_BASE_BRANCH}")
    if meta.get("commit", {}).get("sha") != PRIVATE_BASE_SHA:
        raise GateError("private_base_moved_re_freeze_required")


def _branch_head(api: GitHub) -> str:
    branch = api.request(
        f"repos/{PRIVATE_REPO}/branches/" + urllib.parse.quote(PRIVATE_BRANCH, safe="")
    )
    head = branch.get("commit", {}).get("sha")
    if not re.fullmatch(r"[0-9a-f]{40}", head or ""):
        raise GateError("private_runtime_sync_branch_missing")
    return head


def _verify_branch_files(api: GitHub, ref: str) -> dict[str, str]:
    digests: dict[str, str] = {}
    for row in TARGETS:
        target_q = urllib.parse.quote(row["target"], safe="/")
        returned = api.request(
            f"repos/{PRIVATE_REPO}/contents/{target_q}?ref=" + urllib.parse.quote(ref, safe="")
        )
        try:
            actual = base64.b64decode(returned["content"])
        except Exception:
            raise GateError("private_runtime_sync_readback_failed") from None
        expected = _source_bytes(row)
        if actual != expected:
            raise GateError("private_runtime_sync_readback_failed")
        digests[row["target"]] = hashlib.sha256(actual).hexdigest()
    return digests


def _verify_exact_compare(api: GitHub, head_sha: str) -> None:
    compare = api.request(f"repos/{PRIVATE_REPO}/compare/{PRIVATE_BASE_SHA}...{head_sha}")
    if (
        compare.get("status") != "ahead"
        or compare.get("behind_by") != 0
        or compare.get("merge_base_commit", {}).get("sha") != PRIVATE_BASE_SHA
    ):
        raise GateError("private_runtime_sync_history_drift")
    files = compare.get("files")
    expected_names = {row["target"] for row in TARGETS}
    if not isinstance(files, list) or {row.get("filename") for row in files} != expected_names:
        raise GateError("private_runtime_sync_diff_scope_drift")
    if any(row.get("status") != "added" for row in files):
        raise GateError("private_runtime_sync_diff_scope_drift")


def stage(api: GitHub) -> None:
    _require_private_base(api)
    api.request(
        f"repos/{PRIVATE_REPO}/git/refs",
        {"ref": "refs/heads/" + PRIVATE_BRANCH, "sha": PRIVATE_BASE_SHA},
        method="POST",
    )
    for row in TARGETS:
        target_q = urllib.parse.quote(row["target"], safe="/")
        api.request(
            f"repos/{PRIVATE_REPO}/contents/{target_q}",
            {
                "message": "Import reviewed Risk Tool consumer runtime surface [skip ci]",
                "branch": PRIVATE_BRANCH,
                "content": base64.b64encode(_source_bytes(row)).decode("ascii"),
            },
            method="PUT",
        )
    head_sha = _branch_head(api)
    _verify_branch_files(api, PRIVATE_BRANCH)
    _verify_exact_compare(api, head_sha)
    print("Risk consumer runtime sync staged and exactly verified on the fixed private branch.")


def merge(api: GitHub) -> None:
    _require_private_base(api)
    head_sha = _branch_head(api)
    _verify_branch_files(api, PRIVATE_BRANCH)
    _verify_exact_compare(api, head_sha)
    result = api.request(
        f"repos/{PRIVATE_REPO}/git/refs/heads/{PRIVATE_BASE_BRANCH}",
        {"sha": head_sha, "force": False},
        method="PATCH",
    )
    if result.get("object", {}).get("sha") != head_sha:
        raise GateError("private_runtime_sync_fast_forward_failed")
    main = api.request(f"repos/{PRIVATE_REPO}/branches/{PRIVATE_BASE_BRANCH}")
    if main.get("commit", {}).get("sha") != head_sha:
        raise GateError("private_runtime_sync_fast_forward_readback_failed")
    _verify_branch_files(api, head_sha)
    print("Risk consumer runtime sync fast-forwarded private main after exact verification.")


def main() -> None:
    _require_context()
    self_test()
    request = _load_request()
    api = _api()
    if request["phase"] == "stage":
        stage(api)
    else:
        merge(api)


if __name__ == "__main__":
    try:
        main()
    except GateError as error:
        print("Runtime sync stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Runtime sync failed without exposing private content.", file=sys.stderr)
        raise SystemExit(1)
