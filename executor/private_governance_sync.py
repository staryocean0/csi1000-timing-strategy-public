"""Apply one frozen public -> private governance synchronization request.

This is not a research runner. The request has a fixed identity, private base,
target set and two phases: stage a private PR, then merge that exact PR after
readback verification. Chat mutates only the public request file.
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
SYNC_TITLE = "governance: enforce Chat-only-public two-repo control plane"
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
    if not isinstance(value, dict) or set(value) != {
        "schema_id", "sync_id", "phase", "private_base_sha", "targets"
    }:
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
    digests = _verify_branch_files(api)
    public_sha = os.environ.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", public_sha):
        raise GateError("public_source_not_immutable")
    body = "\n".join(
        [
            "Bounded public -> private governance synchronization.", "",
            f"Sync id: `{SYNC_ID}`",
            f"Public source: `{PUBLIC_REPO}@{public_sha}`",
            f"Frozen private base: `{PRIVATE_REPO}@{PRIVATE_BASE_SHA}`",
            "Targets: `AGENTS.md`, `docs/WORKFLOW.md` only.",
            "No research execution, private data access, arbitrary paths, or production authority.",
            "", "SHA256 readback:",
            *[f"- `{path}`: `{digest}`" for path, digest in sorted(digests.items())],
        ]
    )
    pr = api.request(
        f"repos/{PRIVATE_REPO}/pulls",
        {"title": SYNC_TITLE, "head": PRIVATE_BRANCH, "base": PRIVATE_BASE_BRANCH, "body": body},
        method="POST",
    )
    number = pr.get("number")
    if type(number) is not int or number <= 0:
        raise GateError("private_governance_pr_creation_failed")
    print(f"Bounded private governance sync staged as private PR #{number}.")


def merge(api: GitHub) -> None:
    _require_private_base(api)
    branch = api.request(f"repos/{PRIVATE_REPO}/branches/{urllib.parse.quote(PRIVATE_BRANCH, safe='')}")
    head_sha = branch.get("commit", {}).get("sha")
    if not re.fullmatch(r"[0-9a-f]{40}", head_sha or ""):
        raise GateError("private_governance_branch_missing")
    _verify_branch_files(api)

    query = urllib.parse.urlencode({
        "state": "open", "head": "staryocean0:" + PRIVATE_BRANCH, "base": PRIVATE_BASE_BRANCH, "per_page": 10
    })
    pulls = api.request(f"repos/{PRIVATE_REPO}/pulls?{query}")
    if not isinstance(pulls, list) or len(pulls) != 1:
        raise GateError("private_governance_pr_identity_failed")
    pr = pulls[0]
    number = pr.get("number")
    if type(number) is not int or pr.get("title") != SYNC_TITLE:
        raise GateError("private_governance_pr_identity_failed")
    files = api.request(f"repos/{PRIVATE_REPO}/pulls/{number}/files?per_page=100")
    if not isinstance(files, list) or {row.get("filename") for row in files} != set(TARGET_NAMES):
        raise GateError("private_governance_pr_scope_drift")

    result = api.request(
        f"repos/{PRIVATE_REPO}/pulls/{number}/merge",
        {
            "sha": head_sha,
            "merge_method": "merge",
            "commit_title": SYNC_TITLE,
            "commit_message": f"Reviewed public source sync id {SYNC_ID}; production authority remains false.",
        },
        method="PUT",
    )
    if result.get("merged") is not True or not re.fullmatch(r"[0-9a-f]{40}", result.get("sha", "")):
        raise GateError("private_governance_merge_failed")
    merged_sha = result["sha"]
    for row in TARGETS:
        target_q = urllib.parse.quote(row["target"], safe="/")
        returned = api.request(f"repos/{PRIVATE_REPO}/contents/{target_q}?ref={merged_sha}")
        if base64.b64decode(returned["content"]) != _source_bytes(row):
            raise GateError("private_governance_merge_readback_failed")
    print(f"Bounded private governance sync merged as private PR #{number}.")


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
