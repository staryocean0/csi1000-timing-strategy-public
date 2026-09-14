"""Apply one frozen public -> private governance synchronization request.

This is not a research runner. The request has a fixed identity, private base,
target set and two phases: stage an exact private branch, then fast-forward the
private main ref to that exact verified branch. Chat mutates only public files.
"""
from __future__ import annotations

import argparse
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

PRIVATE_BASE_BRANCH = "main"
PRIVATE_BASE_SHA = "653fdfc232f1d877f051e05e3238d409d269f85d"
SYNC_ID = "two-repo-control-plane-hardening-v1"
PRIVATE_BRANCH = "sync/public-governance/" + SYNC_ID
REQUEST_PATH = ROOT / "governance/private_sync/v1/request.json"
TARGETS = (
    {
        "source": "governance/private_sync/v1/AGENTS.md",
        "target": "AGENTS.md",
        "expected_private_blob": "344a0dfea3614868de78e570d4f47f0215239537",
    },
    {
        "source": "governance/private_sync/v1/docs/WORKFLOW.md",
        "target": "docs/WORKFLOW.md",
        "expected_private_blob": "4c2053f177bd96d6a007c0773859643f37c92524",
    },
)
TARGET_NAMES = [row["target"] for row in TARGETS]


def _source_bytes(row: dict[str, str]) -> bytes:
    path = ROOT / row["source"]
    if path.is_symlink() or not path.is_file():
        raise GateError("governance_source_missing")
    raw = path.read_bytes()
    if not raw or len(raw) > 128 * 1024:
        raise GateError("governance_source_size_invalid")
    return raw


def _require_context() -> None:
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != PUBLIC_REPO
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
        or env.get("GITHUB_EVENT_NAME") not in {"workflow_dispatch", "push"}
    ):
        raise GateError("not_approved_governance_event")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")):
        raise GateError("invalid_run_identity")


def _load_request() -> dict:
    try:
        value = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        raise GateError("invalid_governance_request") from None
    expected = {"schema_id", "sync_id", "phase", "private_base_sha", "targets"}
    if not isinstance(value, dict) or set(value) != expected:
        raise GateError("invalid_governance_request")
    if value["schema_id"] != "csi1000.private_governance_sync_request@1.0":
        raise GateError("invalid_governance_request")
    if value["sync_id"] != SYNC_ID or value["private_base_sha"] != PRIVATE_BASE_SHA:
        raise GateError("governance_request_identity_drift")
    if value["phase"] not in {"stage", "merge"}:
        raise GateError("governance_request_phase_invalid")
    if value["targets"] != TARGET_NAMES:
        raise GateError("governance_request_target_drift")
    return value


def self_test() -> None:
    if PRIVATE_REPO != "staryocean0/csi1000-timing-strategy-private":
        raise GateError("private_identity_drift")
    if not re.fullmatch(r"[0-9a-f]{40}", PRIVATE_BASE_SHA):
        raise GateError("private_base_not_immutable")
    if set(TARGET_NAMES) != {"AGENTS.md", "docs/WORKFLOW.md"}:
        raise GateError("governance_target_scope_drift")
    for row in TARGETS:
        if not re.fullmatch(r"[0-9a-f]{40}", row["expected_private_blob"]):
            raise GateError("private_blob_not_immutable")
        _source_bytes(row)
    _load_request()
    print("Bounded governance sync contract is structurally valid.")


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
        raise GateError("private_governance_branch_missing")
    return head


def _verify_branch_files(api: GitHub) -> dict[str, str]:
    digests: dict[str, str] = {}
    for row in TARGETS:
        target_q = urllib.parse.quote(row["target"], safe="/")
        returned = api.request(
            f"repos/{PRIVATE_REPO}/contents/{target_q}?ref="
            + urllib.parse.quote(PRIVATE_BRANCH, safe="")
        )
        try:
            actual = base64.b64decode(returned["content"])
        except Exception:
            raise GateError("private_governance_readback_failed") from None
        expected = _source_bytes(row)
        if actual != expected:
            raise GateError("private_governance_readback_failed")
        digests[row["target"]] = hashlib.sha256(actual).hexdigest()
    return digests


def _verify_exact_compare(api: GitHub, head_sha: str) -> None:
    compare = api.request(f"repos/{PRIVATE_REPO}/compare/{PRIVATE_BASE_SHA}...{head_sha}")
    if (
        compare.get("status") != "ahead"
        or compare.get("behind_by") != 0
        or compare.get("merge_base_commit", {}).get("sha") != PRIVATE_BASE_SHA
    ):
        raise GateError("private_governance_history_drift")
    files = compare.get("files")
    if not isinstance(files, list) or {row.get("filename") for row in files} != set(TARGET_NAMES):
        raise GateError("private_governance_diff_scope_drift")
    if any(row.get("status") != "modified" for row in files):
        raise GateError("private_governance_diff_scope_drift")


def stage(api: GitHub) -> None:
    _require_private_base(api)
    api.request(
        f"repos/{PRIVATE_REPO}/git/refs",
        {"ref": "refs/heads/" + PRIVATE_BRANCH, "sha": PRIVATE_BASE_SHA},
        method="POST",
    )
    for row in TARGETS:
        target_q = urllib.parse.quote(row["target"], safe="/")
        meta = api.request(f"repos/{PRIVATE_REPO}/contents/{target_q}?ref={PRIVATE_BASE_SHA}")
        if meta.get("type") != "file" or meta.get("sha") != row["expected_private_blob"]:
            raise GateError("private_governance_target_drift")
        api.request(
            f"repos/{PRIVATE_REPO}/contents/{target_q}",
            {
                "message": "Apply reviewed public governance sync [skip ci]",
                "branch": PRIVATE_BRANCH,
                "sha": meta["sha"],
                "content": base64.b64encode(_source_bytes(row)).decode("ascii"),
            },
            method="PUT",
        )
    head_sha = _branch_head(api)
    _verify_branch_files(api)
    _verify_exact_compare(api, head_sha)
    print("Bounded private governance sync staged and verified on the fixed private branch.")


def merge(api: GitHub) -> None:
    _require_private_base(api)
    head_sha = _branch_head(api)
    _verify_branch_files(api)
    _verify_exact_compare(api, head_sha)
    result = api.request(
        f"repos/{PRIVATE_REPO}/git/refs/heads/{PRIVATE_BASE_BRANCH}",
        {"sha": head_sha, "force": False},
        method="PATCH",
    )
    if result.get("object", {}).get("sha") != head_sha:
        raise GateError("private_governance_fast_forward_failed")
    main = api.request(f"repos/{PRIVATE_REPO}/branches/{PRIVATE_BASE_BRANCH}")
    if main.get("commit", {}).get("sha") != head_sha:
        raise GateError("private_governance_fast_forward_readback_failed")
    for row in TARGETS:
        target_q = urllib.parse.quote(row["target"], safe="/")
        returned = api.request(f"repos/{PRIVATE_REPO}/contents/{target_q}?ref={head_sha}")
        try:
            actual = base64.b64decode(returned["content"])
        except Exception:
            raise GateError("private_governance_fast_forward_readback_failed") from None
        if actual != _source_bytes(row):
            raise GateError("private_governance_fast_forward_readback_failed")
    print("Bounded private governance sync fast-forwarded private main after exact diff verification.")


def run_sync() -> None:
    _require_context()
    self_test()
    request = _load_request()
    api = _api()
    if request["phase"] == "stage":
        stage(api)
    else:
        merge(api)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        run_sync()


if __name__ == "__main__":
    try:
        main()
    except GateError as error:
        print("Governance sync stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Governance sync failed without publishing private content.", file=sys.stderr)
        raise SystemExit(1)
