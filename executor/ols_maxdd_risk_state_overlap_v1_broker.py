from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tarfile
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_ols_d0_broker", HERE / "ols_drawdown_d0_broker.py")
d0b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(d0b)
rb = d0b.rb
GateError = rb.GateError

PROFILE_NAME = "ols-maxdd-risk-state-overlap-v1"
PROFILE_SHA256 = "0291435962fbc94e5f21d51db1a41fa8b072d13e1b8fe0294daf750babc8f1ea"
RISK_PRIVATE_REF = "3879de41a5ac7c12246b811f51d16dc8586b9dae"
RISK_SOURCE_PATH = "runtime/research/risk_tool_v2_severity_persistence_v1/run_study.py"
RISK_SOURCE_BLOB = "7a9f238442f5a4836c6f38dcafec4bc34526fc5c"
P1 = (
    388319643, 563182909, 8115479,
    "c201cd1b2ab18442ca49d60209b181557335595efdb6a4da5d78549b5c32b21b",
    "study/MODEL_FREEZE.json", 15921,
    "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551",
)
P1B = (
    388398729, 563403877, 8090245,
    "197c15aaa725a20cbfd7b07ff639e59c400b38eaa49c0141fa6fca9d035dd3fc",
    "study/CALIBRATION_FREEZE.json", 2068,
    "74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909",
)
PROFILE = {
    "private_ref": d0b.PRIVATE_REF,
    "manifest_sha256": PROFILE_SHA256,
    "command": ["d0/ols_maxdd_risk_state_overlap_v1.py", "--inputs", "/work/inputs", "--out", "/results/study"],
    "verify_command": ["d0/ols_maxdd_risk_state_overlap_v1_verifier.py", "--inputs", "/work/inputs", "--results", "/results/study"],
    "command_timeout_seconds": 900,
    "verification_timeout_seconds": 600,
    "new_training": False,
    "production_authority": False,
}
rb.COMPUTE_HOST_TIMEOUT_SECONDS = 930
rb.VALIDATE_HOST_TIMEOUT_SECONDS = 630

PINNED_PUBLIC_D0_BLOBS = {
    "ols_drawdown_d0.py": "b50cd14dccbd895082a1ff8915a70edf8645d828",
    "ols_drawdown_d0_session_adapter.py": "2af497297e47628a1efec7bea6117767a766b530",
    "ols_maxdd_failure_atlas_v1.py": "f30e14f69d6acbdb4503df8d613673c631cdd04d",
}
_PRIVATE_TEXT_MIRROR = (
    "study/RESULTS.json",
    "study/RESULTS.md",
    "study/family_auc.csv",
    "study/year_auc.csv",
    "study/recovery_probability_summary.csv",
    "study/control_summary.csv",
    "study/data_and_semantics_receipt.json",
)
_SAFE_CODE = re.compile(r"\bols_risk_overlap_[a-z0-9_:-]+\b")
_SAFE_EXCEPTION = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception))(?::|$)", re.MULTILINE)
_SAFE_PUBLIC_FRAME = re.compile(
    r'File "[^"\r\n]*/(ols_maxdd_risk_state_overlap_v1(?:_features|_analysis|_verifier)?\.py)", '
    r'line ([0-9]{1,6}), in ([A-Za-z_][A-Za-z0-9_]*)'
)


def _blobsha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def require_context() -> None:
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
        or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
    ):
        raise GateError("not_approved_ols_risk_overlap_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "") or "") or not re.fullmatch(
        r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "") or ""
    ):
        raise GateError("invalid_run_identity")


def _fetch_private_source(api, inputs: Path) -> dict[str, object]:
    endpoint = f"repos/{rb.PRIVATE_REPO}/contents/{urllib.parse.quote(RISK_SOURCE_PATH, safe='/')}?ref={RISK_PRIVATE_REF}"
    meta = api.request(endpoint)
    if meta.get("type") != "file" or meta.get("encoding") != "base64" or meta.get("sha") != RISK_SOURCE_BLOB:
        raise GateError("ols_risk_overlap_risk_source_identity_failed")
    try:
        raw = base64.b64decode(meta.get("content", "") or "")
    except Exception:
        raise GateError("ols_risk_overlap_risk_source_decode_failed") from None
    if _blobsha(raw) != RISK_SOURCE_BLOB:
        raise GateError("ols_risk_overlap_risk_source_blob_failed")
    (inputs / "phase1_run_study.py").write_bytes(raw)
    return {
        "private_ref": RISK_PRIVATE_REF,
        "path": RISK_SOURCE_PATH,
        "git_blob_sha1": RISK_SOURCE_BLOB,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _extract_fixed(api, root: Path, spec: tuple, destination: Path) -> dict[str, object]:
    release_id, asset_id, asset_bytes, asset_sha, member_name, member_bytes, member_sha = spec
    release = api.request(f"repos/{rb.PRIVATE_REPO}/releases/{release_id}")
    asset = next((x for x in release.get("assets") or [] if x.get("id") == asset_id), None)
    if (
        not asset
        or asset.get("state") != "uploaded"
        or asset.get("size") != asset_bytes
        or asset.get("digest") != "sha256:" + asset_sha
    ):
        raise GateError("ols_risk_overlap_parent_release_identity_failed")
    archive = root / f"risk_parent_{release_id}.tar.gz"
    api.request(f"repos/{rb.PRIVATE_REPO}/releases/assets/{asset_id}", binary_path=archive, max_bytes=asset_bytes)
    if archive.stat().st_size != asset_bytes or _sha256(archive) != asset_sha:
        raise GateError("ols_risk_overlap_parent_archive_identity_failed")
    with tarfile.open(archive, "r:gz") as tar:
        try:
            member = tar.getmember(member_name)
        except KeyError:
            raise GateError("ols_risk_overlap_parent_member_missing") from None
        if not member.isfile() or member.size != member_bytes:
            raise GateError("ols_risk_overlap_parent_member_invalid")
        stream = tar.extractfile(member)
        if stream is None:
            raise GateError("ols_risk_overlap_parent_member_unreadable")
        raw = stream.read()
    if len(raw) != member_bytes or hashlib.sha256(raw).hexdigest() != member_sha:
        raise GateError("ols_risk_overlap_parent_member_digest_failed")
    destination.write_bytes(raw)
    archive.unlink(missing_ok=True)
    return {
        "release_id": release_id,
        "asset_id": asset_id,
        "archive_bytes": asset_bytes,
        "archive_sha256": asset_sha,
        "member": member_name,
        "member_bytes": member_bytes,
        "member_sha256": member_sha,
    }


def prepare_inputs(api, root: Path, profile: dict) -> Path:
    profile_path = HERE / "ols_maxdd_risk_state_overlap_v1_profile.json"
    if not profile_path.is_file() or profile_path.is_symlink() or _sha256(profile_path) != PROFILE_SHA256:
        raise GateError("ols_risk_overlap_profile_identity_failed")
    for name, expected in PINNED_PUBLIC_D0_BLOBS.items():
        source = HERE / name
        if not source.is_file() or source.is_symlink() or _blobsha(source.read_bytes()) != expected:
            raise GateError(f"ols_risk_overlap_public_source_identity_failed_{name}")

    work = d0b.prepare_inputs(api, root, d0b.PROFILE)
    inputs = work / "inputs"
    d0dir = work / "d0"
    for name in (
        "ols_maxdd_failure_atlas_v1.py",
        "ols_maxdd_risk_state_overlap_v1_features.py",
        "ols_maxdd_risk_state_overlap_v1_analysis.py",
        "ols_maxdd_risk_state_overlap_v1.py",
        "ols_maxdd_risk_state_overlap_v1_verifier.py",
    ):
        source = HERE / name
        if not source.is_file() or source.is_symlink():
            raise GateError("ols_risk_overlap_public_source_missing")
        shutil.copy2(source, d0dir / name)

    risk_source = _fetch_private_source(api, inputs)
    model = _extract_fixed(api, root, P1, inputs / "MODEL_FREEZE.json")
    calibration = _extract_fixed(api, root, P1B, inputs / "CALIBRATION_FREEZE.json")
    provenance = {
        "schema_id": "ols_maxdd_risk_state_overlap_input_provenance@1.0",
        "ols_private_ref": d0b.PRIVATE_REF,
        "market_data_ref": d0b.DATA_REF,
        "risk_source": risk_source,
        "model_freeze": model,
        "calibration_freeze": calibration,
        "year_2026_read": False,
        "new_training": False,
        "production_authority": False,
    }
    (inputs / "RISK_INPUT_PROVENANCE.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    shutil.copy2(profile_path, inputs / "EXECUTION_PROFILE.json")
    return work


def _safe_failure_diagnostic() -> None:
    try:
        state, root = rb.load_state()
    except Exception:
        print('OLS_RISK_OVERLAP_SAFE_DIAGNOSTIC={"available":false,"reason":"state_unavailable"}', file=sys.stderr)
        return
    codes: set[str] = set()
    exceptions: set[str] = set()
    frames: set[str] = set()
    for path in (root / "results" / "compute.log", root / "results" / "controller_validation.log"):
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 65536:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        codes.update(_SAFE_CODE.findall(text))
        exceptions.update(_SAFE_EXCEPTION.findall(text))
        for filename, line, function in _SAFE_PUBLIC_FRAME.findall(text):
            frames.add(f"{filename}:{int(line)}:{function}")
    print(
        "OLS_RISK_OVERLAP_SAFE_DIAGNOSTIC="
        + json.dumps(
            {
                "available": bool(codes or exceptions or frames),
                "compute_exit_code": state.get("compute_exit_code"),
                "validation_exit_code": state.get("validation_exit_code"),
                "codes": sorted(codes),
                "exception_classes": sorted(exceptions),
                "public_frames": sorted(frames)[:8],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        file=sys.stderr,
    )


def _mirror_private_text_results() -> None:
    state, root = rb.load_state()
    if not state.get("compute_success") or not state.get("cleanup_complete"):
        raise GateError("ols_risk_overlap_private_text_mirror_requires_verified_success")
    api = rb.require_private_api()
    results = root / "results"
    for relative in _PRIVATE_TEXT_MIRROR:
        source = results / relative
        if not source.is_file() or source.is_symlink() or source.stat().st_size > 256 * 1024:
            raise GateError("ols_risk_overlap_private_text_mirror_source_invalid")
        raw = source.read_bytes()
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            raise GateError("ols_risk_overlap_private_text_mirror_not_utf8") from None
        private_path = f"research/public-runs/{state['run_id']}/ols-risk-overlap/{relative}"
        endpoint = f"repos/{rb.PRIVATE_REPO}/contents/{urllib.parse.quote(private_path, safe='/')}"
        api.request(
            endpoint,
            {
                "message": "Mirror verified OLS risk-state overlap text result [skip ci]",
                "branch": state["branch"],
                "content": base64.b64encode(raw).decode(),
            },
            method="PUT",
        )
        returned = api.request(endpoint + "?ref=" + urllib.parse.quote(state["branch"], safe=""))
        if returned.get("encoding") != "base64" or base64.b64decode(returned.get("content", "") or "") != raw:
            raise GateError("ols_risk_overlap_private_text_mirror_readback_failed")
    print("Verified OLS risk-state overlap text mirror written to the private run branch.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_ols_risk_overlap_profile")
    rb.prepare_inputs = prepare_inputs
    if args.phase == "prepare":
        rb.prepare(PROFILE_NAME, PROFILE)
    elif args.phase == "compute":
        try:
            rb.compute()
        except GateError as error:
            if str(error) == "compute_failed_private_publish_step_will_report":
                _safe_failure_diagnostic()
            raise
    elif args.phase == "cleanup":
        rb.cleanup()
    else:
        rb.publish(PROFILE)
        _mirror_private_text_results()


def run() -> None:
    try:
        main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Execution failed; no private OLS risk-state overlap content was exposed publicly.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
