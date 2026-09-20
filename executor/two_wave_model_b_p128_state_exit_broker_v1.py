"""Reviewed broker for issue #635 Model B P128 state-exit increment."""
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

PROFILE_NAME = "two-wave-model-b-p128-state-exit-v1"
PRIVATE_REF = "2815f50b5a1b2925f0e0118b0af0d578605ee882"
ISSUE635_COMMAND_TIMEOUT_SECONDS = 900
ISSUE635_VERIFICATION_TIMEOUT_SECONDS = 900
ISSUE635_HOST_TIMEOUT_SECONDS = 960
SOURCE_REPO = "staryocean0/factorlab-two-wave-strategy-lab"
SOURCE_REF = "152ae1ef11a04bb3b434da25025794db7a706c81"
DATA_PATH = "data/development/5m_offset_0.parquet"
DATA_BYTES = 3_351_411
DATA_SHA256 = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"
PREREG = (
    HERE.parent / "docs" / "research"
    / "TWO_WAVE_MODEL_B_P128_STATE_EXIT_PREREG_20260920.json"
)
MANIFEST = (
    HERE.parent / "docs" / "research"
    / "TWO_WAVE_MODEL_B_P128_STATE_EXIT_SOURCE_MANIFEST_20260920.json"
)
PREREG_SHA256 = "31784bcc4d4613347b1cda2e68f332e6d02703b9fcec3f07fc92834df875f508"
MANIFEST_SHA256 = "46b83cad129ddbf5991a5b6c36ce1205dd9859d95094f53a11bd134f9e8bc70d"

SCRIPT_NAMES = (
    "run_two_wave_model_b_p128_state_exit_v1.py",
    "two_wave_model_b_p128_state_exit_v1.py",
    "two_wave_model_b_p128_state_exit_verifier_v1.py",
    "two_wave_local_state_exit_compression_v1.py",
    "two_wave_postdelay_persistence_v1.py",
    "two_wave_delayed_causal_wrapper_v1.py",
    "two_wave_current_band_recognizer_v1.py",
)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _manifest() -> dict:
    if sha256(PREREG) != PREREG_SHA256:
        raise GateError("issue635_prereg_identity_failed")
    if sha256(MANIFEST) != MANIFEST_SHA256:
        raise GateError("issue635_manifest_identity_failed")
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if value.get("profile") != PROFILE_NAME or value.get("private_result_base") != PRIVATE_REF:
        raise GateError("issue635_manifest_contract_failed")
    sources = value.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(SCRIPT_NAMES):
        raise GateError("issue635_manifest_source_scope_failed")
    for name in SCRIPT_NAMES:
        source = HERE / name
        if not source.is_file() or source.is_symlink():
            raise GateError("issue635_public_source_missing")
        if sha256(source) != sources[name]:
            raise GateError("issue635_public_source_identity_failed")
    return value


def profile() -> dict:
    _manifest()
    return {
        "private_ref": PRIVATE_REF,
        "manifest_sha256": MANIFEST_SHA256,
        "command": [
            "two_wave_issue635/run_two_wave_model_b_p128_state_exit_v1.py",
            "--data", "/work/inputs/5m_offset_0.parquet",
            "--out", "/results/study",
            "--prereg", "/work/two_wave_issue635/PREREG.json",
        ],
        "verify_command": [
            "two_wave_issue635/two_wave_model_b_p128_state_exit_verifier_v1.py",
            "--data", "/work/inputs/5m_offset_0.parquet",
            "--results", "/results/study",
            "--prereg", "/work/two_wave_issue635/PREREG.json",
        ],
        "command_timeout_seconds": ISSUE635_COMMAND_TIMEOUT_SECONDS,
        "verification_timeout_seconds": ISSUE635_VERIFICATION_TIMEOUT_SECONDS,
        "new_training": True,
        "production_authority": False,
    }
def require_context() -> None:
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
        or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
    ):
        raise GateError("not_approved_issue635_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")):
        raise GateError("invalid_run_identity")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "")):
        raise GateError("invalid_run_identity")


def download_public_data(target: Path) -> None:
    url = f"https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_REF}/{DATA_PATH}"
    request = urllib.request.Request(
        url, headers={"User-Agent": "csi1000-reviewed-executor"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        final = urllib.parse.urlparse(response.geturl())
        if final.scheme != "https" or final.hostname != "raw.githubusercontent.com":
            raise GateError("issue635_public_redirect_rejected")
        digest = hashlib.sha256()
        total = 0
        with target.open("xb") as output:
            while True:
                chunk = response.read(min(1024 * 1024, DATA_BYTES + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > DATA_BYTES:
                    raise GateError("issue635_public_data_oversize")
                digest.update(chunk)
                output.write(chunk)
    if total != DATA_BYTES or digest.hexdigest() != DATA_SHA256:
        raise GateError("issue635_public_data_identity_failed")


def prepare_inputs(api, root: Path, fixed_profile: dict) -> Path:
    del api, fixed_profile
    manifest = _manifest()
    work = root / "work"
    work.mkdir()
    inputs = work / "inputs"
    inputs.mkdir()
    scripts = work / "two_wave_issue635"
    scripts.mkdir()
    for name in SCRIPT_NAMES:
        source = HERE / name
        shutil.copy2(source, scripts / name)
        if sha256(scripts / name) != manifest["sources"][name]:
            raise GateError("issue635_staged_source_identity_failed")
    shutil.copy2(PREREG, scripts / "PREREG.json")
    shutil.copy2(MANIFEST, scripts / "SOURCE_MANIFEST.json")
    if sha256(scripts / "PREREG.json") != PREREG_SHA256:
        raise GateError("issue635_staged_prereg_identity_failed")
    if sha256(scripts / "SOURCE_MANIFEST.json") != MANIFEST_SHA256:
        raise GateError("issue635_staged_manifest_identity_failed")
    download_public_data(inputs / "5m_offset_0.parquet")
    return work


def configure_host_timeouts() -> None:
    # Keep the shared broker defaults untouched for every other profile.
    rb.COMPUTE_HOST_TIMEOUT_SECONDS = ISSUE635_HOST_TIMEOUT_SECONDS
    rb.VALIDATE_HOST_TIMEOUT_SECONDS = ISSUE635_HOST_TIMEOUT_SECONDS


def correct_private_receipt_new_training() -> None:
    run_id = os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]
    branch = "runs/public-research/" + run_id
    target = f"repos/{rb.PRIVATE_REPO}/contents/research/public-runs/{run_id}.json"
    api = rb.require_private_api()
    query = target + "?ref=" + urllib.parse.quote(branch, safe="")
    returned = api.request(query)
    try:
        payload = base64.b64decode(returned["content"])
        receipt = json.loads(payload)
    except Exception:
        raise GateError("issue635_private_receipt_parse_failed") from None
    if (
        receipt.get("public_run_id") != run_id
        or receipt.get("profile") != PROFILE_NAME
        or receipt.get("new_training") not in {False, True}
    ):
        raise GateError("issue635_private_receipt_identity_failed")
    receipt["new_training"] = True
    corrected = (json.dumps(receipt, indent=2) + "\n").encode()
    if corrected != payload:
        api.request(
            target,
            {
                "message": "Correct issue 635 training metadata [skip ci]",
                "branch": branch,
                "content": base64.b64encode(corrected).decode(),
                "sha": returned["sha"],
            },
            method="PUT",
        )
    readback = api.request(query)
    if base64.b64decode(readback["content"]) != corrected:
        raise GateError("issue635_private_receipt_correction_readback_failed")
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_issue635_profile")
    fixed = profile()
    rb.prepare_inputs = prepare_inputs
    if args.phase == "prepare":
        rb.prepare(PROFILE_NAME, fixed)
    elif args.phase == "compute":
        configure_host_timeouts()
        rb.compute()
    elif args.phase == "cleanup":
        rb.cleanup()
    else:
        try:
            rb.publish(fixed)
        except GateError as error:
            if str(error) == "compute_failed_consult_private_receipt":
                correct_private_receipt_new_training()
            raise
        else:
            correct_private_receipt_new_training()


def run() -> None:
    try:
        main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print(
            "Execution failed; no private issue-635 result content was exposed publicly.",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    run()
