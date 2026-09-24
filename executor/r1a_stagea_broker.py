"""Bounded broker for the fixed R1_A Stage A outcome-blind profile.

Prepare uses only reviewed public files and the pinned public source checkout.
The private token is forbidden in prepare/compute/cleanup and is used only after
cleanup to publish the bounded result package to a dedicated private run branch.
"""
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_base_broker", HERE / "broker.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("base_broker_unavailable")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

GateError = base.GateError
PROFILE_NAME = "r1a-parent-continuation-stagea-v1"
PROFILE_SCHEMA = "csi1000.r1a_parent_continuation_stagea_profile@1.0"
PROFILE_FILE = HERE / "r1a_stagea_profile.json"
PRIVATE_BASE = "6b6505aaa2aa0d29ac340f6ebcdc4f4e68cd2426"
PRIVATE_AUTHORITY_BRANCH = "research/r1a-parent-continuation-20260914"
SOURCE_REPO = "staryocean0/factorlab-trend-reversion-regime-lab"
SOURCE_COMMIT = "ab4979b224d8ee97f89b75ac428ddd71887fecf1"
IMAGE = "factorlab-r1a-stagea:local"
CONTAINER_NAME = "factorlab-r1a-stagea"
RESULT_FILE = "study/stagea_result.json"
AUDIT_FILES = (
    "r1a_stagea_feature_audit.py",
    "r1a_stagea_baseline_audit.py",
    "r1a_stagea_strict_acceptance.py",
    "r1a_stagea_profile_task.py",
    "r1a_stagea_profile_verify.py",
)
PROFILE_KEYS = {
    "schema_id", "profile_name", "private_authority_branch", "private_base_ref",
    "source_repository", "source_commit", "command", "verify_command",
    "command_timeout_seconds", "verification_timeout_seconds", "cpu_limit",
    "memory_gib", "network", "new_training", "current_validation_outcomes_scored",
    "horizon_selection", "data_2026_opened", "fresh_oos", "accepted_trading_strategy",
    "stage_b_authorized", "production_authority",
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise GateError(message)


def load_feature_module():
    spec = importlib.util.spec_from_file_location(
        "_r1a_feature_audit", HERE / "r1a_stagea_feature_audit.py"
    )
    if spec is None or spec.loader is None:
        raise GateError("feature_audit_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_profile(name: str) -> dict:
    require(name == PROFILE_NAME, "unknown_profile")
    try:
        value = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    except Exception:
        raise GateError("profile_unavailable") from None
    require(isinstance(value, dict) and set(value) == PROFILE_KEYS, "profile_shape_invalid")
    require(value["schema_id"] == PROFILE_SCHEMA and value["profile_name"] == PROFILE_NAME, "profile_identity_invalid")
    require(value["private_authority_branch"] == PRIVATE_AUTHORITY_BRANCH, "private_branch_changed")
    require(value["private_base_ref"] == PRIVATE_BASE, "private_base_changed")
    require(value["source_repository"] == SOURCE_REPO and value["source_commit"] == SOURCE_COMMIT, "source_identity_changed")
    require(value["cpu_limit"] == 4 and value["memory_gib"] == 12 and value["network"] == "none", "resource_scope_changed")
    require(value["command_timeout_seconds"] == 480 and value["verification_timeout_seconds"] == 480, "timeout_changed")
    require(value["new_training"] is True, "training_semantics_changed")
    for key in (
        "current_validation_outcomes_scored", "horizon_selection", "data_2026_opened",
        "fresh_oos", "accepted_trading_strategy", "stage_b_authorized", "production_authority",
    ):
        require(value[key] is False, "scope_not_authorized:" + key)
    expected_command = [
        "r1a_stagea/r1a_stagea_profile_task.py", "--source", "/work/source",
        "--out", "/results/study",
    ]
    expected_verify = [
        "r1a_stagea/r1a_stagea_profile_verify.py", "--source", "/work/source",
        "--results", "/results/study",
    ]
    require(value["command"] == expected_command and value["verify_command"] == expected_verify, "unapproved_command")
    return value


def state_path() -> Path:
    return Path(os.environ["RUNNER_TEMP"]) / "r1a-stagea-state.json"


def write_state(value: dict) -> None:
    target = state_path()
    require(not target.is_symlink(), "state_path_is_link")
    pending = target.with_suffix(".pending")
    pending.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    pending.replace(target)


def load_state() -> tuple[dict, Path]:
    try:
        value = json.loads(state_path().read_text(encoding="utf-8"))
    except Exception:
        raise GateError("state_unavailable") from None
    root = Path(value.get("root", "")).resolve()
    temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    require(root.is_relative_to(temp) and root.name.startswith("r1a-stagea-"), "invalid_state_root")
    run_id = os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]
    require(value.get("run_id") == run_id, "state_run_identity_mismatch")
    require(value.get("public_sha") == os.environ["GITHUB_SHA"], "public_sha_changed_between_phases")
    require(value.get("profile_sha256") == base.sha(PROFILE_FILE), "profile_changed_between_phases")
    return value, root


def copy_regular(source: Path, target: Path) -> None:
    require(source.is_file() and not source.is_symlink(), "source_file_invalid")
    target.parent.mkdir(parents=True, exist_ok=True)
    require(not target.exists(), "copy_target_exists")
    shutil.copyfile(source, target)
    require(target.is_file() and not target.is_symlink(), "copied_file_invalid")


def prepare(profile: dict) -> None:
    require(not os.environ.get("FACTORLAB_PRIVATE_TOKEN"), "private_token_forbidden_in_public_prepare")
    require(not state_path().exists(), "existing_run_state")
    feature = load_feature_module()
    workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
    source_checkout = workspace / "r1a-source"
    require(source_checkout.is_dir(), "pinned_public_source_checkout_missing")
    feature.source_integrity_audit(source_checkout)

    run_id = os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]
    root = Path(tempfile.mkdtemp(prefix="r1a-stagea-", dir=os.environ["RUNNER_TEMP"]))
    work = root / "work"
    source_target = work / "source"
    code_target = work / "r1a_stagea"
    results = root / "results"
    source_target.mkdir(parents=True)
    code_target.mkdir(parents=True)
    results.mkdir()

    for relative in feature.EXPECTED_BLOBS:
        copy_regular(source_checkout / relative, source_target / relative)
    feature.source_integrity_audit(source_target)
    for name in AUDIT_FILES:
        copy_regular(HERE / name, code_target / name)
    copy_regular(PROFILE_FILE, root / "profile.json")

    write_state({
        "run_id": run_id,
        "root": str(root),
        "public_sha": os.environ["GITHUB_SHA"],
        "profile_sha256": base.sha(PROFILE_FILE),
        "prepare_ready": True,
        "compute_success": False,
        "cleanup_complete": False,
    })
    print("R1A Stage A fixed public inputs verified; no private credentials used.")


def docker_command(root: Path, profile: dict, validator: bool = False) -> list[str]:
    work = root / "work"
    results = root / "results"
    args = [
        "docker", "run", "--rm", "--name", CONTAINER_NAME,
        "--network", "none", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--user", f"{os.getuid()}:{os.getgid()}",
        "--memory", "12g", "--memory-swap", "12g", "--cpus", "4",
        "--pids-limit", "256", "--tmpfs", "/tmp:rw,noexec,nosuid,size=512m",
        "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "OMP_NUM_THREADS=1",
        "--env", "OPENBLAS_NUM_THREADS=1",
        "--mount", f"type=bind,src={work},dst=/work,readonly",
        "--mount", f"type=bind,src={root / 'profile.json'},dst=/execution/profile.json,readonly",
    ]
    if validator:
        args += ["--mount", f"type=bind,src={results},dst=/results,readonly", IMAGE, "validate"]
    else:
        args += ["--mount", f"type=bind,src={results},dst=/results", IMAGE]
    return args


def run_container(command: list[str], output, timeout: int, errors=subprocess.STDOUT) -> int:
    process = subprocess.Popen(command, stdout=output, stderr=errors, env=base.clean_env())
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        code = 124
    if code:
        subprocess.run(
            ["docker", "rm", "--force", CONTAINER_NAME], env=base.clean_env(),
            capture_output=True, text=True, timeout=30,
        )
        if process.poll() is None:
            process.kill()
            process.wait()
    return int(code)


def compute(profile: dict) -> None:
    require(not os.environ.get("FACTORLAB_PRIVATE_TOKEN"), "private_token_must_not_reach_compute")
    state, root = load_state()
    require(state.get("prepare_ready") is True, "prepare_not_complete")
    results = root / "results"
    with (results / "container.log").open("xb") as stream:
        code = run_container(docker_command(root, profile), stream, 540)
    validation_code = 1
    validation_value = {}
    if code == 0:
        with (root / "validation.json").open("xb") as output, (root / "validation.log").open("xb") as errors:
            validation_code = run_container(docker_command(root, profile, validator=True), output, 540, errors)
        if validation_code == 0:
            try:
                validation_value = json.loads((root / "validation.json").read_text(encoding="utf-8"))
            except Exception:
                validation_value = {}
    success = code == 0 and validation_code == 0 and validation_value.get("status") == "passed"
    if success:
        copy_regular(root / "validation.json", results / "controller_validation.json")
    base.collect_result_files(results)
    state["compute_success"] = bool(success)
    write_state(state)
    if not success:
        raise GateError("r1a_stagea_compute_or_validation_failed")
    print("R1A Stage A compute and independent validation passed without private credentials.")


def cleanup() -> None:
    require(not os.environ.get("FACTORLAB_PRIVATE_TOKEN"), "private_token_forbidden_in_cleanup")
    removed = subprocess.run(
        ["docker", "rm", "--force", CONTAINER_NAME], env=base.clean_env(),
        capture_output=True, text=True, timeout=30,
    )
    require(removed.returncode == 0 or "No such container" in removed.stderr, "container_cleanup_not_verified")
    state, _ = load_state()
    state["cleanup_complete"] = True
    write_state(state)
    print("R1A Stage A owned container stopped; cleanup complete.")


def safe_result(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink(), "stagea_result_missing")
    require(path.stat().st_size <= 2 * 1024 * 1024, "stagea_result_oversize")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except Exception:
        raise GateError("stagea_result_invalid") from None
    require(value.get("schema") == "r1a_parent_continuation_stagea_private_result_v1", "stagea_result_schema")
    require(value.get("profile_name") == PROFILE_NAME and value.get("status") == "STAGEA_BASELINE_IDENTIFIED", "stagea_result_identity")
    require(value.get("new_training") is True and value.get("stage_b_authorized") is False, "stagea_result_scope")
    for key in (
        "current_validation_outcomes_constructed_or_scored", "prediction_error_computed",
        "pnl_computed", "horizon_selected", "data_2026_opened", "accepted_trading_strategy",
        "fresh_oos", "production_authority",
    ):
        require(value.get(key) is False, "stagea_result_scope:" + key)
    anomalies = value.get("feature_domain_anomalies")
    require(isinstance(anomalies, dict) and anomalies and all(v == 0 for v in anomalies.values()), "stagea_result_anomaly_gate")
    coverage = value.get("coverage", {})
    require(coverage.get("coverage") == 1.0 and coverage.get("pass") is True, "stagea_result_coverage_gate")
    require(all(value.get("gates", {}).values()), "stagea_result_gate_failure")
    return raw


def put_private_file(api, branch: str, path: str, raw: bytes, message: str) -> None:
    target = f"repos/{base.PRIVATE_REPO}/contents/{path}"
    api.request(target, {
        "message": message,
        "branch": branch,
        "content": base64.b64encode(raw).decode("ascii"),
    }, method="PUT")
    returned = api.request(target + "?ref=" + base.urllib.parse.quote(branch, safe=""))
    require(base64.b64decode(returned["content"]) == raw, "private_readback_failed")


def publish(profile: dict) -> None:
    state, root = load_state()
    require(state.get("cleanup_complete") is True, "cleanup_must_complete_before_publish")
    api = base.require_private_api()
    authority = api.request(
        f"repos/{base.PRIVATE_REPO}/git/ref/heads/{PRIVATE_AUTHORITY_BRANCH}"
    )
    require(authority.get("object", {}).get("sha") == PRIVATE_BASE, "private_authority_branch_drifted")

    run_branch = "runs/public-research/" + state["run_id"]
    api.request(
        f"repos/{base.PRIVATE_REPO}/git/refs",
        {"ref": "refs/heads/" + run_branch, "sha": PRIVATE_BASE},
        method="POST",
    )
    results = root / "results"
    result_raw = safe_result(results / RESULT_FILE) if state.get("compute_success") else None
    files = base.collect_result_files(results)
    archive = root / "r1a-stagea-results.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in files:
            tar.add(results / name, arcname=name, recursive=False)
    require(archive.stat().st_size <= 16 * 1024 * 1024, "stagea_archive_oversize")

    tag = "public-research-run-" + state["run_id"]
    release = api.request(
        f"repos/{base.PRIVATE_REPO}/releases",
        {
            "tag_name": tag,
            "target_commitish": PRIVATE_BASE,
            "draft": True,
            "prerelease": True,
            "name": "R1A Stage A public runner result " + state["run_id"],
            "body": "Fixed outcome-blind Stage A result; no current validation outcome scoring.",
        },
        method="POST",
    )
    uploaded = base.upload_result(api, release["id"], archive)
    expected_digest = "sha256:" + base.sha(archive)
    checked_release = api.request(f"repos/{base.PRIVATE_REPO}/releases/{release['id']}")
    require(
        len(checked_release.get("assets") or []) == 1
        and uploaded.get("digest") == expected_digest
        and checked_release["assets"][0].get("digest") == expected_digest
        and checked_release["assets"][0].get("state") == "uploaded",
        "private_result_upload_verification_failed",
    )
    api.request(f"repos/{base.PRIVATE_REPO}/releases/{release['id']}", {"draft": False}, method="PATCH")

    status = "passed" if state.get("compute_success") else "failed"
    receipt = {
        "schema_id": "csi1000.r1a_stagea_public_runner_receipt@1.0",
        "status": status,
        "delivery_status": "private_release_and_run_branch_verified",
        "profile_name": PROFILE_NAME,
        "public_run_id": state["run_id"],
        "public_repository": base.PUBLIC_REPO,
        "public_source_sha": state["public_sha"],
        "private_authority_branch": PRIVATE_AUTHORITY_BRANCH,
        "private_base_ref": PRIVATE_BASE,
        "source_repository": SOURCE_REPO,
        "source_commit": SOURCE_COMMIT,
        "execution": "public_standard_runner_network_isolated_container",
        "files": files,
        "archive": {
            "release_id": checked_release["id"], "tag": tag,
            "sha256": base.sha(archive), "bytes": archive.stat().st_size,
        },
        "new_training": True,
        "current_validation_outcomes_scored": False,
        "horizon_selected": False,
        "data_2026_opened": False,
        "fresh_oos": False,
        "accepted_trading_strategy": False,
        "stage_b_authorized": False,
        "production_authority": False,
    }
    receipt_raw = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode("utf-8")
    put_private_file(
        api, run_branch, f"research/public-runs/{state['run_id']}.json",
        receipt_raw, "Record verified R1A Stage A public runner receipt [skip ci]",
    )
    if result_raw is not None:
        put_private_file(
            api, run_branch, f"research/public-runs/{state['run_id']}-r1a-stagea-result.json",
            result_raw, "Record verified R1A Stage A private result [skip ci]",
        )
    print("R1A Stage A private release, receipt and result readback verified.")
    if not state.get("compute_success"):
        raise GateError("compute_failed_consult_private_receipt")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "compute", "cleanup", "publish"))
    parser.add_argument("profile", choices=(PROFILE_NAME,))
    args = parser.parse_args()
    base.require_context(os.environ)
    os.umask(0o077)
    profile = load_profile(args.profile)
    if args.phase == "prepare":
        prepare(profile)
    elif args.phase == "compute":
        compute(profile)
    elif args.phase == "cleanup":
        cleanup()
    else:
        publish(profile)


if __name__ == "__main__":
    try:
        main()
    except GateError as error:
        print("Execution stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("Execution failed; no private research content was printed.", file=sys.stderr)
        raise SystemExit(1)
