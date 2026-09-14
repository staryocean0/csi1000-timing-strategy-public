"""Stage exactly three reviewed Phase-1b sources on one fixed private branch.

Control-plane only: this module never executes research or reads market data.
"""
from __future__ import annotations

import argparse
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
if _spec is None or _spec.loader is None:
    raise RuntimeError("broker unavailable")
broker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(broker)

GateError = broker.GateError
GitHub = broker.GitHub
PUBLIC_REPO = broker.PUBLIC_REPO
PRIVATE_REPO = broker.PRIVATE_REPO

REQUEST_PATH = ROOT / "governance/risk_phase1b_source_v1/request.json"
PRIVATE_BASE_SHA = "c45c0f991d9d6872bf312bbf0e1f220b98958d75"
PRIVATE_BASE_BRANCH = "main"
SYNC_ID = "risk-v2-phase1b-ordering-calibration-v1"
PRIVATE_BRANCH = "research/frozen/risk-v2-phase1b-ordering-calibration-v1"
FILES = (
    {
        "source": "executor/risk_phase1b_platt.py",
        "target": "runtime/research/risk_tool_v2_phase1b_ordering_calibration_v1/run_study.py",
        "bytes": 17626,
        "git_blob_sha1": "b8c33e196512dc032756102b73b2247254dd3fbe",
    },
    {
        "source": "executor/risk_phase1b_verifier.py",
        "target": "runtime/research/risk_tool_v2_phase1b_ordering_calibration_v1/verify_study.py",
        "bytes": 15694,
        "git_blob_sha1": "668cc8fadc2153a916fe4ab493ba75adfc3b6c76",
    },
    {
        "source": "docs/research/RISK_TOOL_V2_PHASE1B_ORDERING_CALIBRATION_PROTOCOL_20260914.json",
        "target": "docs/research/RISK_TOOL_V2_PHASE1B_ORDERING_CALIBRATION_PROTOCOL_20260914.json",
        "bytes": 5508,
        "git_blob_sha1": "78528896dbe424af9396e478f114d66b68e7f786",
    },
)


def git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def source_bytes(row: dict) -> bytes:
    path = ROOT / row["source"]
    if path.is_symlink() or not path.is_file() or path.stat().st_size != row["bytes"]:
        raise GateError("phase1b_source_identity_failed")
    raw = path.read_bytes()
    if git_blob_sha1(raw) != row["git_blob_sha1"]:
        raise GateError("phase1b_source_digest_failed")
    return raw


def load_request() -> dict:
    try:
        value = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        raise GateError("phase1b_sync_request_invalid") from None
    expected_keys = {"schema_id", "sync_id", "phase", "private_base_sha", "target_branch", "files"}
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise GateError("phase1b_sync_request_invalid")
    if value["schema_id"] != "csi1000.risk_phase1b_source_sync_request@1.1":
        raise GateError("phase1b_sync_request_invalid")
    if value["sync_id"] != SYNC_ID or value["phase"] != "stage":
        raise GateError("phase1b_sync_request_identity_drift")
    if value["private_base_sha"] != PRIVATE_BASE_SHA or value["target_branch"] != PRIVATE_BRANCH:
        raise GateError("phase1b_sync_request_identity_drift")
    if value["files"] != list(FILES):
        raise GateError("phase1b_sync_request_file_drift")
    return value


def require_context() -> None:
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != PUBLIC_REPO
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
        or env.get("GITHUB_EVENT_NAME") not in {"push", "workflow_dispatch"}
    ):
        raise GateError("not_approved_phase1b_sync_event")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")):
        raise GateError("invalid_run_identity")


def api() -> GitHub:
    token = os.environ.get("FACTORLAB_PRIVATE_TOKEN")
    if not token:
        raise GateError("private_token_missing")
    value = GitHub(token)
    value.private_identity()
    return value


def require_private_base(client: GitHub) -> None:
    main = client.request(f"repos/{PRIVATE_REPO}/branches/{PRIVATE_BASE_BRANCH}")
    if main.get("commit", {}).get("sha") != PRIVATE_BASE_SHA:
        raise GateError("phase1b_private_base_moved_re_freeze_required")


def branch_head(client: GitHub) -> str | None:
    path = f"repos/{PRIVATE_REPO}/branches/" + urllib.parse.quote(PRIVATE_BRANCH, safe="")
    try:
        branch = client.request(path)
    except GateError as error:
        if str(error) == "github_http_404":
            return None
        raise
    head = branch.get("commit", {}).get("sha")
    if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise GateError("phase1b_private_branch_identity_failed")
    return head


def verify_branch_files(client: GitHub) -> None:
    for row in FILES:
        target_q = urllib.parse.quote(row["target"], safe="/")
        result = client.request(
            f"repos/{PRIVATE_REPO}/contents/{target_q}?ref=" + urllib.parse.quote(PRIVATE_BRANCH, safe="")
        )
        if result.get("type") != "file" or result.get("sha") != row["git_blob_sha1"]:
            raise GateError("phase1b_private_source_identity_failed")
        try:
            raw = base64.b64decode(result["content"])
        except Exception:
            raise GateError("phase1b_private_source_readback_failed") from None
        if raw != source_bytes(row):
            raise GateError("phase1b_private_source_readback_failed")


def verify_exact_compare(client: GitHub, head: str) -> None:
    result = client.request(f"repos/{PRIVATE_REPO}/compare/{PRIVATE_BASE_SHA}...{head}")
    if (
        result.get("status") != "ahead"
        or result.get("behind_by") != 0
        or result.get("merge_base_commit", {}).get("sha") != PRIVATE_BASE_SHA
    ):
        raise GateError("phase1b_private_history_drift")
    files = result.get("files")
    expected = {row["target"] for row in FILES}
    if not isinstance(files, list) or {row.get("filename") for row in files} != expected:
        raise GateError("phase1b_private_diff_scope_drift")
    if any(row.get("status") != "added" for row in files):
        raise GateError("phase1b_private_diff_scope_drift")


def stage(client: GitHub) -> None:
    require_private_base(client)
    existing = branch_head(client)
    if existing is not None:
        verify_branch_files(client)
        verify_exact_compare(client, existing)
        print("Bounded Phase-1b source branch already exists and matches the frozen request.")
        return

    client.request(
        f"repos/{PRIVATE_REPO}/git/refs",
        {"ref": "refs/heads/" + PRIVATE_BRANCH, "sha": PRIVATE_BASE_SHA},
        method="POST",
    )
    for row in FILES:
        target_q = urllib.parse.quote(row["target"], safe="/")
        client.request(
            f"repos/{PRIVATE_REPO}/contents/{target_q}",
            {
                "message": "Stage reviewed Risk Tool Phase-1b source [skip ci]",
                "branch": PRIVATE_BRANCH,
                "content": base64.b64encode(source_bytes(row)).decode("ascii"),
            },
            method="PUT",
        )
    head = branch_head(client)
    if head is None:
        raise GateError("phase1b_private_branch_missing_after_stage")
    verify_branch_files(client)
    verify_exact_compare(client, head)
    print("Bounded Phase-1b source branch staged and verified; no research was executed.")


def self_test() -> None:
    if PRIVATE_REPO != "staryocean0/csi1000-timing-strategy-private":
        raise GateError("private_identity_drift")
    if not re.fullmatch(r"[0-9a-f]{40}", PRIVATE_BASE_SHA):
        raise GateError("phase1b_private_base_not_immutable")
    if len(FILES) != 3 or len({row["target"] for row in FILES}) != 3:
        raise GateError("phase1b_sync_scope_drift")
    load_request()
    for row in FILES:
        source_bytes(row)
    print("Bounded Phase-1b source sync contract is structurally valid.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    require_context()
    self_test()
    stage(api())


if __name__ == "__main__":
    try:
        main()
    except GateError as error:
        print("Phase-1b source sync stopped: " + str(error), file=os.sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Phase-1b source sync failed without executing research.", file=os.sys.stderr)
        raise SystemExit(1)
