"""Stage two reviewed governance files from the public repo into a private-repo PR.

This is not a research runner. It has no arbitrary path, branch, command, data,
or merge input. Chat edits public sources; this broker performs the bounded
public -> private mutation and readback verification.
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
SYNC_TITLE = "governance: enforce Chat-only-public two-repo control plane"
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


def _source_bytes(row: dict[str, str]) -> bytes:
    path = ROOT / row["source"]
    if path.is_symlink() or not path.is_file():
        raise GateError("governance_source_missing")
    raw = path.read_bytes()
    if not raw or len(raw) > 128 * 1024:
        raise GateError("governance_source_size_invalid")
    return raw


def self_test() -> None:
    if PRIVATE_REPO != "staryocean0/csi1000-timing-strategy-private":
        raise GateError("private_identity_drift")
    if not re.fullmatch(r"[0-9a-f]{40}", PRIVATE_BASE_SHA):
        raise GateError("private_base_not_immutable")
    if {row["target"] for row in TARGETS} != {"AGENTS.md", "docs/WORKFLOW.md"}:
        raise GateError("governance_target_scope_drift")
    for row in TARGETS:
        if not re.fullmatch(r"[0-9a-f]{40}", row["expected_private_blob"]):
            raise GateError("private_blob_not_immutable")
        _source_bytes(row)
    print("Bounded governance sync contract is structurally valid.")


def run_sync() -> None:
    broker.require_context(os.environ)
    self_test()
    token = os.environ.get("FACTORLAB_PRIVATE_TOKEN")
    if not token:
        raise GateError("private_token_missing")
    api = GitHub(token)
    api.private_identity()

    branch_meta = api.request(f"repos/{PRIVATE_REPO}/branches/{PRIVATE_BASE_BRANCH}")
    if branch_meta.get("commit", {}).get("sha") != PRIVATE_BASE_SHA:
        raise GateError("private_base_moved_re_freeze_required")

    run_id = os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]
    private_branch = "sync/public-governance/" + run_id
    api.request(
        f"repos/{PRIVATE_REPO}/git/refs",
        {"ref": "refs/heads/" + private_branch, "sha": PRIVATE_BASE_SHA},
        method="POST",
    )

    source_digests: dict[str, str] = {}
    for row in TARGETS:
        target_q = urllib.parse.quote(row["target"], safe="/")
        meta = api.request(f"repos/{PRIVATE_REPO}/contents/{target_q}?ref={PRIVATE_BASE_SHA}")
        if meta.get("type") != "file" or meta.get("sha") != row["expected_private_blob"]:
            raise GateError("private_governance_target_drift")
        raw = _source_bytes(row)
        source_digests[row["target"]] = hashlib.sha256(raw).hexdigest()
        api.request(
            f"repos/{PRIVATE_REPO}/contents/{target_q}",
            {
                "message": "Apply reviewed public governance sync [skip ci]",
                "branch": private_branch,
                "sha": meta["sha"],
                "content": base64.b64encode(raw).decode("ascii"),
            },
            method="PUT",
        )
        returned = api.request(
            f"repos/{PRIVATE_REPO}/contents/{target_q}?ref="
            + urllib.parse.quote(private_branch, safe="")
        )
        try:
            actual = base64.b64decode(returned["content"])
        except Exception:
            raise GateError("private_governance_readback_failed") from None
        if actual != raw:
            raise GateError("private_governance_readback_failed")

    public_sha = os.environ.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", public_sha):
        raise GateError("public_source_not_immutable")
    body = "\n".join(
        [
            "Bounded public -> private governance synchronization.",
            "",
            f"Public source: `{PUBLIC_REPO}@{public_sha}`",
            f"Frozen private base: `{PRIVATE_REPO}@{PRIVATE_BASE_SHA}`",
            "Targets: `AGENTS.md`, `docs/WORKFLOW.md` only.",
            "No research execution, private data access, arbitrary paths, or production authority.",
            "",
            "SHA256 readback:",
            *[f"- `{path}`: `{digest}`" for path, digest in sorted(source_digests.items())],
        ]
    )
    pr = api.request(
        f"repos/{PRIVATE_REPO}/pulls",
        {
            "title": SYNC_TITLE,
            "head": private_branch,
            "base": PRIVATE_BASE_BRANCH,
            "body": body,
        },
        method="POST",
    )
    number = pr.get("number")
    if type(number) is not int or number <= 0:
        raise GateError("private_governance_pr_creation_failed")
    print(f"Bounded private governance sync staged as private PR #{number}.")


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
