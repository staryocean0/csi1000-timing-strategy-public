"""Apply one frozen public -> private bounded synchronization request.

This is not a research runner. Each supported sync contract has a fixed identity,
private base, target set, source identity, and two phases: stage an exact private
branch, then fast-forward private main to that exact verified branch.

Chat mutates only public files. Private writes happen only inside this reviewed
workflow using the repository's restricted private-research credential.
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
REQUEST_PATH = ROOT / "governance/private_sync/v1/request.json"

CONTRACTS: dict[str, dict[str, object]] = {
    "two-repo-control-plane-hardening-v1": {
        "private_base_sha": "653fdfc232f1d877f051e05e3238d409d269f85d",
        "private_branch": "sync/public-governance/two-repo-control-plane-hardening-v1",
        "target_status": "modified",
        "targets": (
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
        ),
    },
    "layer3-ols-family-import-20260915-v1": {
        "private_base_sha": "46e818ef51618e225be2d79a516424ff16231a1d",
        "private_branch": "sync/public-import/layer3-ols-family-20260915-v1",
        "target_status": "added",
        "targets": (
            {
                "source": "docs/research/layer3/ols_family/MIGRATION_MANIFEST.json",
                "target": "docs/imports/layer3_ols_family_20260915/MIGRATION_MANIFEST.json",
                "expected_public_blob": "7ee1ade47b18418fca84577627cc4fd8457a039f",
            },
            {
                "source": "docs/research/layer3/ols_family/README.md",
                "target": "docs/imports/layer3_ols_family_20260915/README.md",
                "expected_public_blob": "9fe46624320531129741ede63f0e0e115300c499",
            },
            {
                "source": "docs/research/layer3/ols_family/source_snapshot/trend_regime_baseline.py",
                "target": "docs/imports/layer3_ols_family_20260915/source_snapshot/trend_regime_baseline.py",
                "expected_public_blob": "25309a1dfc2dd8b93e777747a24c6843e086bc7d",
            },
            {
                "source": "docs/research/layer3/ols_family/source_snapshot/trend_regime_consumer.py",
                "target": "docs/imports/layer3_ols_family_20260915/source_snapshot/trend_regime_consumer.py",
                "expected_public_blob": "6ec31839a9497ad96fd59e9503c73ed1984569fa",
            },
            {
                "source": "docs/research/layer3/ols_family/source_snapshot/trend_regime_profiles.py",
                "target": "docs/imports/layer3_ols_family_20260915/source_snapshot/trend_regime_profiles.py",
                "expected_public_blob": "6d192667434c1406bfbc5e6c8e88bc48c2bc2231",
            },
            {
                "source": "docs/research/layer3/ols_family/source_snapshot/trend_regime_representation.py",
                "target": "docs/imports/layer3_ols_family_20260915/source_snapshot/trend_regime_representation.py",
                "expected_public_blob": "677571f4a31a8e935f448cb8a5f6b05b1e5accef",
            },
        ),
    },
    "layer3-ols-external-evidence-20260915-v1": {
        "private_base_sha": "215662a7a07070a34473148e172bf56d17fefd62",
        "private_branch": "sync/public-import/layer3-ols-external-evidence-20260915-v1",
        "target_status": "added",
        "targets": (
            {
                "source": "docs/research/layer3/ols_family/external_evidence_20260915/EVIDENCE_MANIFEST.json",
                "target": "docs/imports/layer3_ols_external_evidence_20260915/EVIDENCE_MANIFEST.json",
                "expected_public_blob": "5c35bc23fc3184548361b95c6ff7d18229156265",
            },
            {
                "source": "docs/research/layer3/ols_family/external_evidence_20260915/README.md",
                "target": "docs/imports/layer3_ols_external_evidence_20260915/README.md",
                "expected_public_blob": "5f7d0ab37bae048b575019791b6f7aa63707d197",
            },
            {
                "source": "docs/research/layer3/ols_family/external_evidence_20260915/TREND_X4_POST_X5O_UPDATE_V1.json",
                "target": "docs/imports/layer3_ols_external_evidence_20260915/TREND_X4_POST_X5O_UPDATE_V1.json",
                "expected_public_blob": "d14e982954c0f3702dc15aa0894380d6b4a20541",
            },
            {
                "source": "docs/research/layer3/ols_family/external_evidence_20260915/TREND_X5M_FROZEN_ANCHORED_STRUCTURAL_VALIDATION_RESULT_V1.json",
                "target": "docs/imports/layer3_ols_external_evidence_20260915/TREND_X5M_FROZEN_ANCHORED_STRUCTURAL_VALIDATION_RESULT_V1.json",
                "expected_public_blob": "bd8cbb104eed4c0440095f98567aac684a72d3b0",
            },
            {
                "source": "docs/research/layer3/ols_family/external_evidence_20260915/TREND_X5N_STRUCTURAL_FAILURE_ATTRIBUTION_RESULT_V1.json",
                "target": "docs/imports/layer3_ols_external_evidence_20260915/TREND_X5N_STRUCTURAL_FAILURE_ATTRIBUTION_RESULT_V1.json",
                "expected_public_blob": "fc73e3406eb922a80dea886a81827a14b0405871",
            },
            {
                "source": "docs/research/layer3/ols_family/external_evidence_20260915/TREND_X5O_CAUSAL_REGIME_OBSERVABLE_IDENTIFIABILITY_PROTOCOL_V1.json",
                "target": "docs/imports/layer3_ols_external_evidence_20260915/TREND_X5O_CAUSAL_REGIME_OBSERVABLE_IDENTIFIABILITY_PROTOCOL_V1.json",
                "expected_public_blob": "8f8eb31ff4c94ebe55e8448e071f6110ac153307",
            },
            {
                "source": "docs/research/layer3/ols_family/external_evidence_20260915/TREND_X5O_CAUSAL_REGIME_OBSERVABLE_IDENTIFIABILITY_RESULT_V1.json",
                "target": "docs/imports/layer3_ols_external_evidence_20260915/TREND_X5O_CAUSAL_REGIME_OBSERVABLE_IDENTIFIABILITY_RESULT_V1.json",
                "expected_public_blob": "5df03522db412818138c2acfcc45adbb6456630f",
            },
            {
                "source": "docs/research/layer3/ols_family/external_evidence_20260915/TREND_X5O_POSTHOC_OBSERVABLE_SOURCE_AGREEMENT_V1.json",
                "target": "docs/imports/layer3_ols_external_evidence_20260915/TREND_X5O_POSTHOC_OBSERVABLE_SOURCE_AGREEMENT_V1.json",
                "expected_public_blob": "783da58689b92f5f05aa4432c26049f0a83eb122",
            },
        ),
    },
}


def _git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _source_bytes(row: dict[str, str]) -> bytes:
    path = ROOT / row["source"]
    if path.is_symlink() or not path.is_file():
        raise GateError("sync_source_missing")
    raw = path.read_bytes()
    if not raw or len(raw) > 128 * 1024:
        raise GateError("sync_source_size_invalid")
    expected_public_blob = row.get("expected_public_blob")
    if expected_public_blob and _git_blob_sha(raw) != expected_public_blob:
        raise GateError("sync_source_identity_drift")
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


def _load_request() -> tuple[dict, dict[str, object]]:
    try:
        value = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        raise GateError("invalid_governance_request") from None
    expected = {"schema_id", "sync_id", "phase", "private_base_sha", "targets"}
    if not isinstance(value, dict) or set(value) != expected:
        raise GateError("invalid_governance_request")
    if value["schema_id"] != "csi1000.private_governance_sync_request@1.0":
        raise GateError("invalid_governance_request")
    contract = CONTRACTS.get(value["sync_id"])
    if contract is None:
        raise GateError("governance_request_identity_drift")
    target_names = [row["target"] for row in contract["targets"]]
    if value["private_base_sha"] != contract["private_base_sha"]:
        raise GateError("governance_request_identity_drift")
    if value["phase"] not in {"stage", "merge"}:
        raise GateError("governance_request_phase_invalid")
    if value["targets"] != target_names:
        raise GateError("governance_request_target_drift")
    return value, contract


def self_test() -> None:
    if PRIVATE_REPO != "staryocean0/csi1000-timing-strategy-private":
        raise GateError("private_identity_drift")
    for sync_id, contract in CONTRACTS.items():
        private_base_sha = contract["private_base_sha"]
        if not re.fullmatch(r"[0-9a-f]{40}", str(private_base_sha)):
            raise GateError("private_base_not_immutable")
        branch = str(contract["private_branch"])
        if not branch.startswith("sync/"):
            raise GateError("private_branch_scope_drift")
        targets = contract["targets"]
        names = [row["target"] for row in targets]
        if len(names) != len(set(names)) or not names:
            raise GateError("governance_target_scope_drift")
        expected_status = contract["target_status"]
        if expected_status not in {"added", "modified"}:
            raise GateError("governance_target_scope_drift")
        for row in targets:
            expected_public_blob = row.get("expected_public_blob")
            expected_private_blob = row.get("expected_private_blob")
            if expected_public_blob and not re.fullmatch(r"[0-9a-f]{40}", expected_public_blob):
                raise GateError("public_blob_not_immutable")
            if expected_private_blob and not re.fullmatch(r"[0-9a-f]{40}", expected_private_blob):
                raise GateError("private_blob_not_immutable")
            if expected_status == "added" and expected_private_blob:
                raise GateError("governance_target_scope_drift")
            if expected_status == "modified" and not expected_private_blob:
                raise GateError("governance_target_scope_drift")
            _source_bytes(row)
        if sync_id == "layer3-ols-family-import-20260915-v1":
            prefix = "docs/imports/layer3_ols_family_20260915/"
            if not all(name.startswith(prefix) for name in names):
                raise GateError("governance_target_scope_drift")
        if sync_id == "layer3-ols-external-evidence-20260915-v1":
            prefix = "docs/imports/layer3_ols_external_evidence_20260915/"
            if not all(name.startswith(prefix) for name in names):
                raise GateError("governance_target_scope_drift")
    _load_request()
    print("Bounded private sync contract is structurally valid.")


def _api() -> GitHub:
    token = os.environ.get("FACTORLAB_PRIVATE_TOKEN")
    if not token:
        raise GateError("private_token_missing")
    api = GitHub(token)
    api.private_identity()
    return api


def _require_private_base(api: GitHub, contract: dict[str, object]) -> None:
    meta = api.request(f"repos/{PRIVATE_REPO}/branches/{PRIVATE_BASE_BRANCH}")
    if meta.get("commit", {}).get("sha") != contract["private_base_sha"]:
        raise GateError("private_base_moved_re_freeze_required")


def _branch_head(api: GitHub, contract: dict[str, object]) -> str:
    branch = api.request(
        f"repos/{PRIVATE_REPO}/branches/"
        + urllib.parse.quote(str(contract["private_branch"]), safe="")
    )
    head = branch.get("commit", {}).get("sha")
    if not re.fullmatch(r"[0-9a-f]{40}", head or ""):
        raise GateError("private_governance_branch_missing")
    return head


def _verify_branch_files(api: GitHub, contract: dict[str, object]) -> dict[str, str]:
    digests: dict[str, str] = {}
    for row in contract["targets"]:
        target_q = urllib.parse.quote(row["target"], safe="/")
        returned = api.request(
            f"repos/{PRIVATE_REPO}/contents/{target_q}?ref="
            + urllib.parse.quote(str(contract["private_branch"]), safe="")
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


def _verify_exact_compare(
    api: GitHub, contract: dict[str, object], head_sha: str
) -> None:
    private_base_sha = str(contract["private_base_sha"])
    compare = api.request(f"repos/{PRIVATE_REPO}/compare/{private_base_sha}...{head_sha}")
    if (
        compare.get("status") != "ahead"
        or compare.get("behind_by") != 0
        or compare.get("merge_base_commit", {}).get("sha") != private_base_sha
    ):
        raise GateError("private_governance_history_drift")
    files = compare.get("files")
    expected_names = {row["target"] for row in contract["targets"]}
    if not isinstance(files, list) or {row.get("filename") for row in files} != expected_names:
        raise GateError("private_governance_diff_scope_drift")
    expected_status = contract["target_status"]
    if any(row.get("status") != expected_status for row in files):
        raise GateError("private_governance_diff_scope_drift")


def stage(api: GitHub, contract: dict[str, object]) -> None:
    _require_private_base(api, contract)
    private_base_sha = str(contract["private_base_sha"])
    private_branch = str(contract["private_branch"])
    api.request(
        f"repos/{PRIVATE_REPO}/git/refs",
        {"ref": "refs/heads/" + private_branch, "sha": private_base_sha},
        method="POST",
    )
    for row in contract["targets"]:
        target_q = urllib.parse.quote(row["target"], safe="/")
        body = {
            "message": "Apply reviewed bounded public sync [skip ci]",
            "branch": private_branch,
            "content": base64.b64encode(_source_bytes(row)).decode("ascii"),
        }
        expected_private_blob = row.get("expected_private_blob")
        if expected_private_blob:
            meta = api.request(
                f"repos/{PRIVATE_REPO}/contents/{target_q}?ref={private_base_sha}"
            )
            if meta.get("type") != "file" or meta.get("sha") != expected_private_blob:
                raise GateError("private_governance_target_drift")
            body["sha"] = meta["sha"]
        api.request(
            f"repos/{PRIVATE_REPO}/contents/{target_q}",
            body,
            method="PUT",
        )
    head_sha = _branch_head(api, contract)
    _verify_branch_files(api, contract)
    _verify_exact_compare(api, contract, head_sha)
    print("Bounded private sync staged and verified on the fixed private branch.")


def merge(api: GitHub, contract: dict[str, object]) -> None:
    _require_private_base(api, contract)
    head_sha = _branch_head(api, contract)
    _verify_branch_files(api, contract)
    _verify_exact_compare(api, contract, head_sha)
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
    for row in contract["targets"]:
        target_q = urllib.parse.quote(row["target"], safe="/")
        returned = api.request(f"repos/{PRIVATE_REPO}/contents/{target_q}?ref={head_sha}")
        try:
            actual = base64.b64decode(returned["content"])
        except Exception:
            raise GateError("private_governance_fast_forward_readback_failed") from None
        if actual != _source_bytes(row):
            raise GateError("private_governance_fast_forward_readback_failed")
    print("Bounded private sync fast-forwarded private main after exact diff verification.")


def run_sync() -> None:
    _require_context()
    self_test()
    request, contract = _load_request()
    api = _api()
    if request["phase"] == "stage":
        stage(api, contract)
    else:
        merge(api, contract)


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
