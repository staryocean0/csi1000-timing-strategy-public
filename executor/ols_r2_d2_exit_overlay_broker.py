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
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_research_broker", HERE / "research_broker.py")
rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rb)
GateError = rb.GateError

PROFILE_NAME = "ols-r2-d2-exit-overlay-v1"
PRIVATE_REF = "67effb80f51228f6129dca5c4f7971a0bb6c7f15"
DATA_REF = "1d760ea9525eb3688b70a4aa0f2b5b207af16a17"
D1_AUTHORITATIVE_RUN = "34964393250"
D1_RESULT_BRANCH = "runs/public-research/34964393250-1"
D1_RESULT_PATH = "research/public-runs/34964393250-1/ols-d1/study/RESULTS.json"
D1_RESULT_BLOB = "f35ae2ff402c90b54d318b49bd678c5398a60493"
PROFILE_SHA256 = "04b7f048b32b49d804d51a5b3fbd0b787d2796465cfe939d1d22dbd7f1756ecc"
DATA = {
    2020: (353781, "c45ef84c123ae9f4ca1843b2816a4f413742547e"),
    2021: (347162, "aba298f940c7992ec8814dd8ece197477d106fa9"),
    2022: (351753, "fe6eed805f7237091813c32d25011848fc29b705"),
    2023: (342750, "0b17d76b150bfd15d45158f100748898e72089b1"),
    2024: (349739, "ba45837375d8a3ca64cb3faa7750bf51e9760796"),
    2025: (353882, "85159b9fa1b2b6854b1a0f04faa9f963e9d04c13"),
}
PUBLIC_UPSTREAM_BLOBS = {
    "ols_drawdown_d0.py": "b50cd14dccbd895082a1ff8915a70edf8645d828",
    "ols_drawdown_d0_session_adapter.py": "2af497297e47628a1efec7bea6117767a766b530",
    "ols_r2_d1.py": "a0c26ec302ea6561d9a2b88a075d5fccb1f2bfc6",
}
SOURCE_BLOBS = {
    "runtime/src/factor_lab/market_state/ols_explosive_channel_v1.py": "538d24172a0f7518f393543522b1990f6d9a398b",
    "runtime/src/factor_lab/market_state/context_free_explosive_channel.py": "3e36419f3bf09cfb1c812e12583d93bb475cbed5",
    "runtime/src/factor_lab/strategy/services/risk_off_v59_large_channel_parent.py": "c9ed25d592e13e0b14f8df63f24b7ca80bb9240a",
    "runtime/src/factor_lab/strategy/services/risk_off_v56_steep_crash_specialist.py": "0c3df76ad4a93b0bd10a198fd204cbba5253859f",
    "runtime/src/factor_lab/filtering/cloudridge_v6_crash_channel_confirmation.py": "c38f4d1d30bfdcdb9bdbb39b26e937c8e2961ece",
    "runtime/src/factor_lab/filtering/_cloudridge_causal_channel_math.py": "22a54f0dd1b1da850e189830a4b4f79599d21681",
}
PROFILE = {
    "private_ref": PRIVATE_REF,
    "manifest_sha256": PROFILE_SHA256,
    "command": ["d2/ols_r2_d2_exit_overlay.py", "--inputs", "/work/inputs", "--out", "/results/study"],
    "verify_command": ["d2/ols_r2_d2_exit_overlay_verifier.py", "--inputs", "/work/inputs", "--results", "/results/study"],
    "command_timeout_seconds": 900,
    "verification_timeout_seconds": 300,
    "new_training": False,
    "production_authority": False,
}
rb.COMPUTE_HOST_TIMEOUT_SECONDS = 930
rb.VALIDATE_HOST_TIMEOUT_SECONDS = 330

_SAFE_CODE = re.compile(r"\bols_d2_[a-z0-9_:-]+\b")
_SAFE_EXCEPTION = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception))(?::|$)", re.MULTILINE)
_SAFE_LOCATION = re.compile(r'File "/work/d2/(ols_r2_d2_exit_overlay(?:_verifier)?\.py|ols_r2_d1\.py|ols_drawdown_d0(?:_session_adapter)?\.py)", line ([0-9]+)')
_PRIVATE_TEXT_MIRROR = (
    "study/RESULTS.json",
    "study/mode_comparison.csv",
    "study/qualification_reset_warned_segments.csv",
    "study/first_opposite_close_warned_segments.csv",
    "study/two_opposite_closes_warned_segments.csv",
    "study/prior_extreme_break_warned_segments.csv",
    "study/frozen_midline_break_warned_segments.csv",
)


def blobsha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def sha256(path: Path) -> str:
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
        raise GateError("not_approved_ols_d2_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "") or "") or not re.fullmatch(
        r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "") or ""
    ):
        raise GateError("invalid_run_identity")


def fetch_public(year: int, target: Path) -> None:
    size, expected_blob = DATA[year]
    url = (
        "https://raw.githubusercontent.com/staryocean0/factorlab-trend-reversion-regime-lab/"
        f"{DATA_REF}/data/market/5m/000852.SH/{year}.parquet"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "csi1000-reviewed-executor"})
    with urllib.request.urlopen(request, timeout=60) as response:
        if urllib.parse.urlparse(response.geturl()).hostname != "raw.githubusercontent.com":
            raise GateError("ols_d2_public_redirect_rejected")
        raw = response.read(size + 1)
    if len(raw) != size or blobsha(raw) != expected_blob:
        raise GateError(f"ols_d2_public_identity_failed_{year}")
    target.write_bytes(raw)


def fetch_private_source(api, path: str, expected_blob: str, root: Path) -> dict[str, object]:
    quoted = urllib.parse.quote(path, safe="/")
    meta = api.request(f"repos/{rb.PRIVATE_REPO}/contents/{quoted}?ref={PRIVATE_REF}")
    if meta.get("type") != "file" or meta.get("encoding") != "base64" or meta.get("sha") != expected_blob:
        raise GateError("ols_d2_private_source_identity_failed")
    raw = base64.b64decode(meta.get("content", "") or "")
    if blobsha(raw) != expected_blob:
        raise GateError("ols_d2_private_source_blob_failed")
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return {"git_blob_sha1": expected_blob, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def fetch_d1_authority(api, inputs: Path) -> dict[str, object]:
    quoted_path = urllib.parse.quote(D1_RESULT_PATH, safe="/")
    quoted_ref = urllib.parse.quote(D1_RESULT_BRANCH, safe="")
    meta = api.request(f"repos/{rb.PRIVATE_REPO}/contents/{quoted_path}?ref={quoted_ref}")
    if meta.get("type") != "file" or meta.get("encoding") != "base64" or meta.get("sha") != D1_RESULT_BLOB:
        raise GateError("ols_d2_d1_result_identity_failed")
    try:
        raw = base64.b64decode(meta.get("content", "") or "")
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        raise GateError("ols_d2_d1_result_decode_failed") from None
    if blobsha(raw) != D1_RESULT_BLOB:
        raise GateError("ols_d2_d1_result_blob_failed")
    decision = payload.get("decision") or {}
    if (
        payload.get("schema_id") != "ols_r2_d1_leadlag@1.0"
        or payload.get("d2_authority") is not True
        or decision.get("status") != "SUPPORTED_FOR_D2_EXIT_OVERLAY_TEST"
        or int(decision.get("coverage_gate_modes_passed", -1)) != 5
        or int(decision.get("exit_lead_gate_modes_passed", -1)) != 5
        or int(decision.get("same_window_guard_modes_passed", -1)) != 5
        or payload.get("same_window_sensitivity") != "authority_window_equal_across_event_three_bars"
    ):
        raise GateError("ols_d2_d1_result_authority_failed")
    target = inputs / "D1_AUTHORITY.json"
    target.write_bytes(raw)
    return {
        "run": D1_AUTHORITATIVE_RUN,
        "branch": D1_RESULT_BRANCH,
        "path": D1_RESULT_PATH,
        "git_blob_sha1": D1_RESULT_BLOB,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def prepare_inputs(api, root: Path, profile: dict) -> Path:
    work = root / "work"
    work.mkdir()
    inputs = work / "inputs"
    inputs.mkdir()
    d2 = work / "d2"
    d2.mkdir()

    profile_path = HERE / "ols_r2_d2_exit_overlay_profile.json"
    if not profile_path.is_file() or profile_path.is_symlink() or sha256(profile_path) != PROFILE_SHA256:
        raise GateError("ols_d2_profile_identity_failed")

    for name, expected_blob in PUBLIC_UPSTREAM_BLOBS.items():
        source = HERE / name
        if not source.is_file() or source.is_symlink() or blobsha(source.read_bytes()) != expected_blob:
            raise GateError(f"ols_d2_public_upstream_identity_failed_{name}")
        shutil.copy2(source, d2 / name)
    for name in ("ols_r2_d2_exit_overlay.py", "ols_r2_d2_exit_overlay_verifier.py"):
        source = HERE / name
        if not source.is_file() or source.is_symlink():
            raise GateError("ols_d2_public_source_missing")
        shutil.copy2(source, d2 / name)

    source_root = work / "provenance"
    receipt = {}
    for path, expected_blob in SOURCE_BLOBS.items():
        receipt[path] = fetch_private_source(api, path, expected_blob, source_root)
    d1_receipt = fetch_d1_authority(api, inputs)
    provenance = {
        "schema_id": "ols_r2_d2_source_provenance@1.1",
        "private_ref": PRIVATE_REF,
        "source_blobs": SOURCE_BLOBS,
        "source_receipt": receipt,
        "public_upstream_blobs": PUBLIC_UPSTREAM_BLOBS,
        "d1_authority_receipt": d1_receipt,
        "production_authority": False,
    }
    (inputs / "SOURCE_PROVENANCE.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.copy2(profile_path, inputs / "EXECUTION_PROFILE.json")
    for year in DATA:
        fetch_public(year, inputs / f"{year}.parquet")
    return work


def _safe_failure_diagnostic() -> None:
    try:
        state, root = rb.load_state()
    except Exception:
        print('OLS_D2_SAFE_DIAGNOSTIC={"available":false,"reason":"state_unavailable"}', file=sys.stderr)
        return
    paths = [root / "results" / "compute.log", root / "results" / "controller_validation.log"]
    codes, exceptions, locations = set(), set(), set()
    for path in paths:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 65536:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        codes.update(_SAFE_CODE.findall(text))
        exceptions.update(_SAFE_EXCEPTION.findall(text))
        locations.update(f"{name}:{line}" for name, line in _SAFE_LOCATION.findall(text))
    payload = {
        "available": bool(codes or exceptions or locations),
        "compute_exit_code": state.get("compute_exit_code"),
        "validation_exit_code": state.get("validation_exit_code"),
        "codes": sorted(codes),
        "exception_classes": sorted(exceptions),
        "public_source_locations": sorted(locations),
    }
    print("OLS_D2_SAFE_DIAGNOSTIC=" + json.dumps(payload, sort_keys=True, separators=(",", ":")), file=sys.stderr)


def _mirror_private_text_results() -> None:
    state, root = rb.load_state()
    if not state.get("compute_success") or not state.get("cleanup_complete"):
        raise GateError("ols_d2_private_text_mirror_requires_verified_success")
    api = rb.require_private_api()
    results = root / "results"
    for relative in _PRIVATE_TEXT_MIRROR:
        source = results / relative
        if not source.is_file() or source.is_symlink() or source.stat().st_size > 256 * 1024:
            raise GateError("ols_d2_private_text_mirror_source_invalid")
        raw = source.read_bytes()
        raw.decode("utf-8")
        private_path = f"research/public-runs/{state['run_id']}/ols-d2/{relative}"
        endpoint = f"repos/{rb.PRIVATE_REPO}/contents/{urllib.parse.quote(private_path, safe='/')}"
        api.request(endpoint, {
            "message": "Mirror verified OLS D2 text result [skip ci]",
            "branch": state["branch"],
            "content": base64.b64encode(raw).decode(),
        }, method="PUT")
        returned = api.request(endpoint + "?ref=" + urllib.parse.quote(state["branch"], safe=""))
        if returned.get("encoding") != "base64" or base64.b64decode(returned.get("content", "") or "") != raw:
            raise GateError("ols_d2_private_text_mirror_readback_failed")
    print("Verified OLS D2 text mirror written to the private run branch.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_ols_d2_profile")
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
        print("Execution failed; no private OLS D2 content was exposed publicly.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
