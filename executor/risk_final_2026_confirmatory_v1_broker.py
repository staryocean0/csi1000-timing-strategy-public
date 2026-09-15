from __future__ import annotations

import argparse
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
_rspec = importlib.util.spec_from_file_location("_research_broker", HERE / "research_broker.py")
rb = importlib.util.module_from_spec(_rspec); _rspec.loader.exec_module(rb); GateError = rb.GateError
_tspec = importlib.util.spec_from_file_location("_temporal_broker", HERE / "risk_temporal_stability_2015_2025_broker.py")
tb = importlib.util.module_from_spec(_tspec); _tspec.loader.exec_module(tb)

PROFILE_NAME = "risk-v2-final-2026-confirmatory-v1"
PRIVATE_REF = "3879de41a5ac7c12246b811f51d16dc8586b9dae"
STAR50_REPO = "staryocean0/factorlab-star50-filter-lab"
STAR50_REF = "56b964851f5ec6d4dc0bfd3a2342b6f24ff885d8"
TASK_ID = "CSI1000-RISK-V2-FINAL-2026-CONFIRMATORY-V1-20260915"
CARRIER_SCHEMA_ID = "risk_tool_v2_final_2026_carrier_identity@1.0"
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

# target path -> source repository path, bytes, git blob, optional SHA256
PUBLIC_FILES = {
    "fresh_1m/000688.SH/2026.parquet": (
        "data/cross_index_risk_gate_2026_v1/1m/000688.SH/2026.parquet", 584376,
        "4626fb307bbcae1c417ddcd69ac694cf322c8bbc",
        "b7e7e9a9e85b738d661583dcd3d7dab158562fddac4355362cc37597db21eca4",
    ),
    "fresh_1m/000852.SH/2026.parquet": (
        "data/cross_index_risk_gate_2026_v1/1m/000852.SH/2026.parquet", 707905,
        "8de5cd3caab99dbacae229a2c87f15c4ff2f8558",
        "60b2054d2055bef8010a9948a0589bc1c4b0bb18dd6f373a9366f97e689fdf87",
    ),
    "guard_1m/000688.SH/2023.parquet": (
        "data/cross_index_risk_gate_v1/1m/000688.SH/2023.parquet", 1156684,
        "6dc7de6de7fe04233566b2a1743de66b054df18b", None,
    ),
    "guard_1m/000852.SH/2023.parquet": (
        "data/cross_index_risk_gate_v1/1m/000852.SH/2023.parquet", 1507783,
        "a915cc9a0e9259e2660558c07ffbe1d6c37c0e8f", None,
    ),
    "guard_5m/000688.SH/2023.parquet": (
        "data/cross_index_risk_gate_v1/5m/000688.SH/2023.parquet", 309025,
        "02c3a9474dff4e5203cec12ca7a24a3b2be8994b", None,
    ),
    "guard_5m/000852.SH/2023.parquet": (
        "data/cross_index_risk_gate_v1/5m/000852.SH/2023.parquet", 342750,
        "0b17d76b150bfd15d45158f100748898e72089b1", None,
    ),
    "market/000688.SH/2025.parquet": (
        "data/cross_index_risk_gate_v1/5m/000688.SH/2025.parquet", 320754,
        "32d6d1754f965dd6298c885e30b244b877d694ed",
        "bb0b3a5747f11bf5e8908ac169185b582213fcc83a74567e683a56410ceb8511",
    ),
    "market/000852.SH/2025.parquet": (
        "data/cross_index_risk_gate_v1/5m/000852.SH/2025.parquet", 353882,
        "85159b9fa1b2b6854b1a0f04faa9f963e9d04c13",
        "5fbecf49d76cd2560e7db5af280b60c012a440a6e69ba6b8306acbbbd4e49333",
    ),
}

PROFILE = {
    "private_ref": PRIVATE_REF,
    "manifest_sha256": P1[6],
    "command": ["final/risk_final_2026_confirmatory_v1.py", "--inputs", "/work/inputs", "--out", "/results/study"],
    "verify_command": ["final/risk_final_2026_confirmatory_v1_verifier.py", "--inputs", "/work/inputs", "--results", "/results/study"],
    "command_timeout_seconds": 900,
    "verification_timeout_seconds": 900,
    "new_training": False,
    "production_authority": False,
}
rb.COMPUTE_HOST_TIMEOUT_SECONDS = 930
rb.VALIDATE_HOST_TIMEOUT_SECONDS = 930


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def require_context() -> None:
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
        or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
    ):
        raise GateError("not_approved_final_confirmatory_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "") or "") or not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "") or ""):
        raise GateError("invalid_run_identity")


def fetch_public_fixed(source_path: str, target: Path, size: int, blob: str, expected_sha256: str | None) -> dict:
    quoted = urllib.parse.quote(source_path, safe="/")
    url = f"https://raw.githubusercontent.com/{STAR50_REPO}/{STAR50_REF}/{quoted}"
    request = urllib.request.Request(url, headers={"User-Agent": "csi1000-reviewed-executor"})
    with urllib.request.urlopen(request, timeout=90) as response:
        if urllib.parse.urlparse(response.geturl()).hostname != "raw.githubusercontent.com":
            raise GateError("final_carrier_redirect_rejected")
        raw = response.read(size + 1)
    if len(raw) != size or blob_sha1(raw) != blob:
        raise GateError("final_carrier_git_identity_failed")
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise GateError("final_carrier_sha256_failed")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return {"bytes": size, "git_blob_sha1": blob, "sha256": digest, "source_path": source_path, "source_commit": STAR50_REF}


def prepare_inputs(api, root: Path, profile: dict):
    work = root / "work"; work.mkdir()
    inputs = work / "inputs"; inputs.mkdir()
    final = work / "final"; final.mkdir()

    for name in (
        "risk_phase1b_fresh_oos_eval.py",
        "risk_phase1b_fresh_oos_verifier.py",
        "risk_final_2026_confirmatory_v1.py",
        "risk_final_2026_confirmatory_v1_verifier.py",
    ):
        source = HERE / name
        if not source.is_file() or source.is_symlink():
            raise GateError("final_confirmatory_source_missing")
        shutil.copy2(source, final / name)

    tb.extract_fixed(api, root, P1, inputs / "MODEL_FREEZE.json")
    tb.extract_fixed(api, root, P1B, inputs / "CALIBRATION_FREEZE.json")

    receipt_files = {}
    for relative, spec in PUBLIC_FILES.items():
        source_path, size, blob, expected_sha256 = spec
        receipt_files[relative] = fetch_public_fixed(source_path, inputs / relative, size, blob, expected_sha256)

    receipt = {
        "schema_id": CARRIER_SCHEMA_ID,
        "task_id": TASK_ID,
        "source_repository": STAR50_REPO,
        "source_commit": STAR50_REF,
        "source_pack": "data/cross_index_risk_gate_2026_v1/1m",
        "confirmatory_as_of_end": "2026-08-21",
        "year_2026_semantic_read_before_guard": False,
        "files": receipt_files,
        "alternate_carrier_allowed": False,
        "production_authority": False,
    }
    (inputs / "CARRIER_IDENTITY.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return work


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_final_confirmatory_profile")
    rb.prepare_inputs = prepare_inputs
    if args.phase == "prepare":
        rb.prepare(PROFILE_NAME, PROFILE)
    elif args.phase == "compute":
        rb.compute()
    elif args.phase == "cleanup":
        rb.cleanup()
    else:
        rb.publish(PROFILE)


def run() -> None:
    try:
        main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Execution failed; no private final-confirmatory content was exposed publicly.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
