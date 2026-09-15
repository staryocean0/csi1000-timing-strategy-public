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
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_ols_d0_broker", HERE / "ols_drawdown_d0_broker.py")
d0b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(d0b)
rb = d0b.rb
GateError = rb.GateError

PROFILE_NAME = "ols-maxdd-reentry-identification-v1"
PROFILE_SHA256 = "2b4b8e43a70f521cbd9909470084ce1a6940b2e9db5fac834fcb37aa7c7cd93c"
PROFILE = {
    "private_ref": d0b.PRIVATE_REF,
    "manifest_sha256": PROFILE_SHA256,
    "command": ["d0/ols_maxdd_reentry_identification_v1.py", "--inputs", "/work/inputs", "--out", "/results/study"],
    "verify_command": ["d0/ols_maxdd_reentry_identification_v1_verifier.py", "--inputs", "/work/inputs", "--results", "/results/study"],
    "command_timeout_seconds": 900,
    "verification_timeout_seconds": 300,
    "new_training": False,
    "production_authority": False,
}
rb.COMPUTE_HOST_TIMEOUT_SECONDS = 930
rb.VALIDATE_HOST_TIMEOUT_SECONDS = 330

PINNED_D0_BLOBS = {
    "ols_drawdown_d0.py": "b50cd14dccbd895082a1ff8915a70edf8645d828",
    "ols_drawdown_d0_session_adapter.py": "2af497297e47628a1efec7bea6117767a766b530",
}
_PRIVATE_TEXT_MIRROR = (
    "study/RESULTS.json",
    "study/candidate_summary.csv",
    "study/year_stability.csv",
    "study/reentry_vs_initial.csv",
    "study/RESULTS.md",
)
_SAFE_CODE = re.compile(r"\bols_maxdd_b_[a-z0-9_:-]+\b")
_SAFE_EXCEPTION = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception))(?::|$)", re.MULTILINE)


def _blobsha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def require_context() -> None:
    env = os.environ
    if env.get("GITHUB_ACTIONS") != "true" or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch" or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1":
        raise GateError("not_approved_ols_maxdd_b_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "") or "") or not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "") or ""):
        raise GateError("invalid_run_identity")


def prepare_inputs(api, root: Path, profile: dict) -> Path:
    profile_path = HERE / "ols_maxdd_reentry_identification_v1_profile.json"
    if not profile_path.is_file() or profile_path.is_symlink() or _sha256(profile_path) != PROFILE_SHA256:
        raise GateError("ols_maxdd_b_profile_identity_failed")
    for name, expected in PINNED_D0_BLOBS.items():
        source = HERE / name
        if not source.is_file() or source.is_symlink() or _blobsha(source.read_bytes()) != expected:
            raise GateError("ols_maxdd_b_d0_identity_failed_" + name)
    work = d0b.prepare_inputs(api, root, d0b.PROFILE)
    d0dir = work / "d0"
    for name in ("ols_maxdd_reentry_identification_v1.py", "ols_maxdd_reentry_identification_v1_verifier.py"):
        source = HERE / name
        if not source.is_file() or source.is_symlink():
            raise GateError("ols_maxdd_b_public_source_missing")
        shutil.copy2(source, d0dir / name)
    shutil.copy2(profile_path, work / "inputs" / "EXECUTION_PROFILE.json")
    return work


def _safe_failure_diagnostic() -> None:
    try:
        state, root = rb.load_state()
    except Exception:
        print('OLS_MAXDD_B_SAFE_DIAGNOSTIC={"available":false,"reason":"state_unavailable"}', file=sys.stderr)
        return
    codes, exceptions = set(), set()
    for path in (root / "results" / "compute.log", root / "results" / "controller_validation.log"):
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 65536:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        codes.update(_SAFE_CODE.findall(text)); exceptions.update(_SAFE_EXCEPTION.findall(text))
    print("OLS_MAXDD_B_SAFE_DIAGNOSTIC=" + json.dumps({"available": bool(codes or exceptions), "compute_exit_code": state.get("compute_exit_code"), "validation_exit_code": state.get("validation_exit_code"), "codes": sorted(codes), "exception_classes": sorted(exceptions)}, sort_keys=True, separators=(",", ":")), file=sys.stderr)


def _mirror_private_text_results() -> None:
    state, root = rb.load_state()
    if not state.get("compute_success") or not state.get("cleanup_complete"):
        raise GateError("ols_maxdd_b_private_text_mirror_requires_verified_success")
    api = rb.require_private_api(); results = root / "results"
    for relative in _PRIVATE_TEXT_MIRROR:
        source = results / relative
        if not source.is_file() or source.is_symlink() or source.stat().st_size > 256 * 1024:
            raise GateError("ols_maxdd_b_private_text_mirror_source_invalid")
        raw = source.read_bytes(); raw.decode("utf-8")
        private_path = f"research/public-runs/{state['run_id']}/ols-maxdd-b/{relative}"
        endpoint = f"repos/{rb.PRIVATE_REPO}/contents/{urllib.parse.quote(private_path, safe='/')}"
        api.request(endpoint, {"message": "Mirror verified OLS MaxDD Phase B text result [skip ci]", "branch": state["branch"], "content": base64.b64encode(raw).decode()}, method="PUT")
        returned = api.request(endpoint + "?ref=" + urllib.parse.quote(state["branch"], safe=""))
        if returned.get("encoding") != "base64" or base64.b64decode(returned.get("content", "") or "") != raw:
            raise GateError("ols_maxdd_b_private_text_mirror_readback_failed")
    print("Verified OLS MaxDD Phase B text mirror written to the private run branch.")


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"]); parser.add_argument("profile", nargs="?", default=PROFILE_NAME); args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_ols_maxdd_b_profile")
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
        rb.publish(PROFILE); _mirror_private_text_results()


def run() -> None:
    try:
        main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr); raise SystemExit(1)
    except Exception:
        print("Execution failed; no private OLS MaxDD Phase B content was exposed publicly.", file=sys.stderr); raise SystemExit(1)


if __name__ == "__main__":
    run()
