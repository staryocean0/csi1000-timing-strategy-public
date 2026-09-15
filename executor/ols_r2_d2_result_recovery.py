from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import re
import tarfile
import tempfile
import urllib.parse
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_broker", HERE / "broker.py")
broker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(broker)
GateError = broker.GateError

PRIVATE_REPO = broker.PRIVATE_REPO
ORIGINAL_RUN_ID = "34969649919-1"
ORIGINAL_BRANCH = "runs/public-research/34969649919-1"
ORIGINAL_TIP = "a43e65d641d45c4ec7a797b36c62001b94ae180d"
ORIGINAL_TREE = "fc8d2cd2ff90a38e30e9c2f601cbb445df26e04d"
ORIGINAL_RECEIPT_PATH = f"research/public-runs/{ORIGINAL_RUN_ID}.json"
ORIGINAL_RECEIPT_BLOB = "92a61dbe07bf53e6394b8a0cd088d1a8f110aa12"
RELEASE_TAG = "public-research-run-34969649919-1"
RELEASE_ID = 389130644
ASSET_ID = 565672996
ASSET_NAME = "results.tar.gz"
ASSET_BYTES = 26230
ASSET_SHA256 = "8be2c6e25346765c1f1e3968f8e3e3f44dcefd64b0b84b311b1ef96800b65b9c"
RECOVERED_FILES = {
    "study/RESULTS.json": {
        "bytes": 8894,
        "sha256": "684b6382952b3f66e9915f9e07c8590d4af419212e208b924c892f8d2f9a8eaf",
    },
    "study/mode_comparison.csv": {
        "bytes": 2231,
        "sha256": "2df48ebdc08badedc6e0fc8668f9c6dc405c758b6d636ce8c5aeaca33d30308a",
    },
}
MIRROR_ROOT = f"research/public-runs/{ORIGINAL_RUN_ID}/ols-d2"
RECOVERY_RECEIPT_PATH = f"{MIRROR_ROOT}/RECOVERY_RECEIPT.json"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _fixed_digest(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"bytes", "sha256"}
        and type(value["bytes"]) is int
        and value["bytes"] >= 0
        and isinstance(value["sha256"], str)
        and bool(_SHA256_RE.fullmatch(value["sha256"]))
    )


def _read_private_text(api, path: str, branch: str, expected_blob: str | None = None) -> bytes:
    quoted_path = urllib.parse.quote(path, safe="/")
    quoted_branch = urllib.parse.quote(branch, safe="")
    meta = api.request(f"repos/{PRIVATE_REPO}/contents/{quoted_path}?ref={quoted_branch}")
    if meta.get("type") != "file" or meta.get("encoding") != "base64":
        raise GateError("ols_d2_recovery_private_text_identity_failed")
    if expected_blob is not None and meta.get("sha") != expected_blob:
        raise GateError("ols_d2_recovery_private_text_blob_failed")
    try:
        raw = base64.b64decode(meta.get("content", "") or "", validate=True)
        raw.decode("utf-8")
    except Exception:
        raise GateError("ols_d2_recovery_private_text_decode_failed") from None
    if git_blob_sha(raw) != meta.get("sha"):
        raise GateError("ols_d2_recovery_private_text_git_blob_failed")
    return raw


def _validate_original_anchor(api) -> tuple[dict, str]:
    branch_name = urllib.parse.quote(ORIGINAL_BRANCH, safe="")
    branch = api.request(f"repos/{PRIVATE_REPO}/branches/{branch_name}")
    if branch.get("name") != ORIGINAL_BRANCH or (branch.get("commit") or {}).get("sha") != ORIGINAL_TIP:
        raise GateError("ols_d2_recovery_branch_tip_drift")

    commit = api.request(f"repos/{PRIVATE_REPO}/git/commits/{ORIGINAL_TIP}")
    if ((commit.get("tree") or {}).get("sha")) != ORIGINAL_TREE:
        raise GateError("ols_d2_recovery_tree_identity_failed")

    raw = _read_private_text(api, ORIGINAL_RECEIPT_PATH, ORIGINAL_BRANCH, ORIGINAL_RECEIPT_BLOB)
    try:
        receipt = json.loads(raw)
    except Exception:
        raise GateError("ols_d2_recovery_receipt_json_failed") from None
    if not isinstance(receipt, dict):
        raise GateError("ols_d2_recovery_receipt_shape_failed")
    if (
        receipt.get("public_run_id") != ORIGINAL_RUN_ID
        or receipt.get("delivery_status") != "archive_uploaded_and_verified"
        or receipt.get("profile") != "ols-r2-d2-exit-overlay-v1"
        or receipt.get("new_training") is not False
        or receipt.get("production_authority") is not False
    ):
        raise GateError("ols_d2_recovery_receipt_identity_failed")

    archive = receipt.get("archive")
    if not isinstance(archive, dict) or (
        archive.get("release_id") != RELEASE_ID
        or archive.get("tag") != RELEASE_TAG
        or archive.get("bytes") != ASSET_BYTES
        or archive.get("sha256") != ASSET_SHA256
    ):
        raise GateError("ols_d2_recovery_receipt_archive_failed")

    files = receipt.get("files")
    if not isinstance(files, dict) or not files:
        raise GateError("ols_d2_recovery_receipt_files_failed")
    for name, digest in files.items():
        if not isinstance(name, str) or not _fixed_digest(digest):
            raise GateError("ols_d2_recovery_receipt_files_failed")
    for name, expected in RECOVERED_FILES.items():
        if files.get(name) != expected:
            raise GateError("ols_d2_recovery_result_identity_not_receipted")
    return receipt, ORIGINAL_TREE


def _download_verified_archive(api, root: Path) -> Path:
    release = api.request(f"repos/{PRIVATE_REPO}/releases/tags/{RELEASE_TAG}")
    assets = release.get("assets") or []
    if (
        release.get("id") != RELEASE_ID
        or release.get("tag_name") != RELEASE_TAG
        or release.get("draft") is not False
        or len(assets) != 1
    ):
        raise GateError("ols_d2_recovery_release_identity_failed")
    asset = assets[0]
    if (
        asset.get("id") != ASSET_ID
        or asset.get("name") != ASSET_NAME
        or asset.get("state") != "uploaded"
        or asset.get("size") != ASSET_BYTES
        or asset.get("digest") != "sha256:" + ASSET_SHA256
    ):
        raise GateError("ols_d2_recovery_asset_identity_failed")

    archive = root / ASSET_NAME
    api.request(
        f"repos/{PRIVATE_REPO}/releases/assets/{ASSET_ID}",
        binary_path=archive,
        max_bytes=ASSET_BYTES,
    )
    if archive.stat().st_size != ASSET_BYTES or broker.sha(archive) != ASSET_SHA256:
        raise GateError("ols_d2_recovery_downloaded_archive_failed")
    return archive


def _verify_archive_and_select(archive: Path, receipt: dict) -> dict[str, bytes]:
    expected_files = receipt["files"]
    seen: set[str] = set()
    recovered: dict[str, bytes] = {}
    try:
        handle = tarfile.open(archive, "r:gz")
    except Exception:
        raise GateError("ols_d2_recovery_archive_open_failed") from None
    with handle as tar:
        for member in tar.getmembers():
            part = PurePosixPath(member.name)
            if part.is_absolute() or ".." in part.parts or "\\" in member.name:
                raise GateError("ols_d2_recovery_archive_unsafe_path")
            name = str(part)
            if member.isdir():
                continue
            if not member.isfile() or name in seen or name not in expected_files:
                raise GateError("ols_d2_recovery_archive_member_failed")
            expected = expected_files[name]
            if member.size != expected["bytes"]:
                raise GateError("ols_d2_recovery_archive_member_size_failed")
            stream = tar.extractfile(member)
            if stream is None:
                raise GateError("ols_d2_recovery_archive_member_failed")
            raw = stream.read(expected["bytes"] + 1)
            if len(raw) != expected["bytes"] or sha256_bytes(raw) != expected["sha256"]:
                raise GateError("ols_d2_recovery_archive_member_digest_failed")
            seen.add(name)
            if name in RECOVERED_FILES:
                try:
                    raw.decode("utf-8")
                except UnicodeDecodeError:
                    raise GateError("ols_d2_recovery_result_not_utf8") from None
                recovered[name] = raw
    if seen != set(expected_files):
        raise GateError("ols_d2_recovery_archive_member_set_failed")
    if set(recovered) != set(RECOVERED_FILES):
        raise GateError("ols_d2_recovery_required_result_missing")
    for name, expected in RECOVERED_FILES.items():
        raw = recovered[name]
        if len(raw) != expected["bytes"] or sha256_bytes(raw) != expected["sha256"]:
            raise GateError("ols_d2_recovery_selected_result_identity_failed")
    return recovered


def _create_blob(api, raw: bytes) -> str:
    response = api.request(
        f"repos/{PRIVATE_REPO}/git/blobs",
        {"content": base64.b64encode(raw).decode(), "encoding": "base64"},
        method="POST",
    )
    digest = response.get("sha")
    if digest != git_blob_sha(raw):
        raise GateError("ols_d2_recovery_created_blob_identity_failed")
    return digest


def _append_recovery_commit(api, base_tree: str, recovered: dict[str, bytes]) -> tuple[str, dict[str, bytes]]:
    receipt_payload = {
        "schema_id": "ols_r2_d2_result_recovery@1.0",
        "source_run_id": ORIGINAL_RUN_ID,
        "source_branch_origin_tip": ORIGINAL_TIP,
        "source_tree": ORIGINAL_TREE,
        "source_receipt_blob_sha1": ORIGINAL_RECEIPT_BLOB,
        "source_release": {
            "id": RELEASE_ID,
            "tag": RELEASE_TAG,
            "asset_id": ASSET_ID,
            "asset_name": ASSET_NAME,
            "bytes": ASSET_BYTES,
            "sha256": ASSET_SHA256,
        },
        "recovered_files": RECOVERED_FILES,
        "operation": "byte_preserving_text_mirror_only",
        "scientific_recompute": False,
        "scientific_result_changed": False,
        "new_training": False,
        "production_authority": False,
    }
    recovery_receipt = (json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n").encode("utf-8")

    payloads: dict[str, bytes] = {}
    for relative, raw in recovered.items():
        payloads[f"{MIRROR_ROOT}/{relative}"] = raw
    payloads[RECOVERY_RECEIPT_PATH] = recovery_receipt

    tree_entries = []
    for path in sorted(payloads):
        blob_sha = _create_blob(api, payloads[path])
        tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob_sha})

    tree = api.request(
        f"repos/{PRIVATE_REPO}/git/trees",
        {"base_tree": base_tree, "tree": tree_entries},
        method="POST",
    )
    tree_sha = tree.get("sha")
    if not isinstance(tree_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", tree_sha):
        raise GateError("ols_d2_recovery_tree_create_failed")

    commit = api.request(
        f"repos/{PRIVATE_REPO}/git/commits",
        {
            "message": "Recover verified first D2 text result [skip ci]",
            "tree": tree_sha,
            "parents": [ORIGINAL_TIP],
        },
        method="POST",
    )
    commit_sha = commit.get("sha")
    if not isinstance(commit_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise GateError("ols_d2_recovery_commit_create_failed")

    ref_name = urllib.parse.quote("heads/" + ORIGINAL_BRANCH, safe="/")
    updated = api.request(
        f"repos/{PRIVATE_REPO}/git/refs/{ref_name}",
        {"sha": commit_sha, "force": False},
        method="PATCH",
    )
    if ((updated.get("object") or {}).get("sha")) != commit_sha:
        raise GateError("ols_d2_recovery_ref_update_failed")
    return commit_sha, payloads


def _verify_readback(api, payloads: dict[str, bytes]) -> None:
    for path, expected in payloads.items():
        raw = _read_private_text(api, path, ORIGINAL_BRANCH)
        if raw != expected:
            raise GateError("ols_d2_recovery_readback_failed")


def main() -> None:
    broker.require_context(os.environ)
    api = broker.require_private_api()
    receipt, base_tree = _validate_original_anchor(api)
    with tempfile.TemporaryDirectory(prefix="ols-d2-recovery-", dir=os.environ.get("RUNNER_TEMP")) as tmp:
        archive = _download_verified_archive(api, Path(tmp))
        recovered = _verify_archive_and_select(archive, receipt)
    _, payloads = _append_recovery_commit(api, base_tree, recovered)
    _verify_readback(api, payloads)
    print("Verified original OLS D2 result text recovered to the private first-run branch.")


def run() -> None:
    try:
        main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=os.sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Execution failed; no private D2 result bytes were exposed publicly.", file=os.sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
