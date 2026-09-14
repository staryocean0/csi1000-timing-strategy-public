"""Stage one reviewed Risk Tool 2.0 loader source into a fixed private branch.

This is a bounded source-transport controller, not a research runner. It reads one
reviewed public source file and writes exactly one new file on an immutable-base
private branch, then verifies exact bytes and diff scope.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import re
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

SYNC_ID = "risk-v2-direct-members-v1"
PRIVATE_BASE_BRANCH = "main"
PRIVATE_BASE_SHA = "cbe97535403b17cf8c4311bcc6567328b726ce67"
PRIVATE_BRANCH = "sync/risk-v2/direct-members-v1"
SOURCE_PATH = ROOT / "governance/risk_source_sync/v1/run_study_v4.py"
REQUEST_PATH = ROOT / "governance/risk_source_sync/v1/request.json"
TARGET_PATH = "runtime/research/risk_tool_v2_severity_persistence_v1/run_study_v4.py"
SOURCE_GIT_BLOB_SHA1 = "204284c523876b6d9708c14cd478efe6c2b539d1"


def _source_bytes() -> bytes:
    if SOURCE_PATH.is_symlink() or not SOURCE_PATH.is_file():
        raise GateError("risk_source_missing")
    raw = SOURCE_PATH.read_bytes()
    if not raw or len(raw) > 64 * 1024:
        raise GateError("risk_source_size_invalid")
    git_blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    if git_blob != SOURCE_GIT_BLOB_SHA1:
        raise GateError("risk_source_identity_drift")
    return raw


def _load_request() -> dict:
    try:
        value = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        raise GateError("invalid_risk_source_request") from None
    expected = {"schema_id", "sync_id", "phase", "private_base_sha", "target"}
    if not isinstance(value, dict) or set(value) != expected:
        raise GateError("invalid_risk_source_request")
    if value != {
        "schema_id": "csi1000.risk_source_sync_request@1.0",
        "sync_id": SYNC_ID,
        "phase": "stage",
        "private_base_sha": PRIVATE_BASE_SHA,
        "target": TARGET_PATH,
    }:
        raise GateError("risk_source_request_drift")
    return value


def _require_context() -> None:
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != PUBLIC_REPO
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
        or env.get("GITHUB_EVENT_NAME") not in {"workflow_dispatch", "push"}
    ):
        raise GateError("not_approved_risk_source_sync_event")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")):
        raise GateError("invalid_run_identity")


def self_test() -> None:
    if PRIVATE_REPO != "staryocean0/csi1000-timing-strategy-private":
        raise GateError("private_identity_drift")
    if not re.fullmatch(r"[0-9a-f]{40}", PRIVATE_BASE_SHA):
        raise GateError("private_base_not_immutable")
    if not TARGET_PATH.endswith("/run_study_v4.py"):
        raise GateError("risk_source_target_drift")
    _source_bytes()
    _load_request()
    print("Bounded Risk source sync contract is structurally valid.")


def _api() -> GitHub:
    token = os.environ.get("FACTORLAB_PRIVATE_TOKEN")
    if not token:
        raise GateError("private_token_missing")
    api = GitHub(token)
    api.private_identity()
    return api


def _branch_head(api: GitHub) -> str:
    branch = api.request(
        f"repos/{PRIVATE_REPO}/branches/" + urllib.parse.quote(PRIVATE_BRANCH, safe="")
    )
    head = branch.get("commit", {}).get("sha")
    if not re.fullmatch(r"[0-9a-f]{40}", head or ""):
        raise GateError("private_risk_source_branch_missing")
    return head


def stage() -> None:
    _require_context()
    self_test()
    api = _api()
    main = api.request(f"repos/{PRIVATE_REPO}/branches/{PRIVATE_BASE_BRANCH}")
    if main.get("commit", {}).get("sha") != PRIVATE_BASE_SHA:
        raise GateError("private_base_moved_re_freeze_required")
    api.request(
        f"repos/{PRIVATE_REPO}/git/refs",
        {"ref": "refs/heads/" + PRIVATE_BRANCH, "sha": PRIVATE_BASE_SHA},
        method="POST",
    )
    raw = _source_bytes()
    target_q = urllib.parse.quote(TARGET_PATH, safe="/")
    api.request(
        f"repos/{PRIVATE_REPO}/contents/{target_q}",
        {
            "message": "Stage reviewed Risk v2 direct-member loader [skip ci]",
            "branch": PRIVATE_BRANCH,
            "content": base64.b64encode(raw).decode("ascii"),
        },
        method="PUT",
    )
    head = _branch_head(api)
    returned = api.request(
        f"repos/{PRIVATE_REPO}/contents/{target_q}?ref=" + urllib.parse.quote(PRIVATE_BRANCH, safe="")
    )
    try:
        actual = base64.b64decode(returned["content"])
    except Exception:
        raise GateError("private_risk_source_readback_failed") from None
    if actual != raw or returned.get("sha") != SOURCE_GIT_BLOB_SHA1:
        raise GateError("private_risk_source_readback_failed")
    compare = api.request(f"repos/{PRIVATE_REPO}/compare/{PRIVATE_BASE_SHA}...{head}")
    files = compare.get("files")
    if (
        compare.get("status") != "ahead"
        or compare.get("behind_by") != 0
        or compare.get("merge_base_commit", {}).get("sha") != PRIVATE_BASE_SHA
        or not isinstance(files, list)
        or len(files) != 1
        or files[0].get("filename") != TARGET_PATH
        or files[0].get("status") != "added"
    ):
        raise GateError("private_risk_source_diff_scope_drift")
    print("Bounded Risk source staged and verified on the fixed private branch: " + head)


if __name__ == "__main__":
    try:
        import sys
        if sys.argv[1:] == ["--self-test"]:
            self_test()
        elif not sys.argv[1:]:
            stage()
        else:
            raise GateError("unapproved_risk_source_sync_mode")
    except GateError as error:
        print("Risk source sync stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Risk source sync failed without publishing private content.", file=sys.stderr)
        raise SystemExit(1)
