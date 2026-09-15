"""Credential-free container wrapper for the fixed R1_A Stage A profile."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path


def require_runtime() -> None:
    forbidden = [
        name
        for name in os.environ
        if any(token in name.upper() for token in ("TOKEN", "SECRET", "PASSWORD", "PRIVATE_KEY"))
    ]
    if forbidden:
        raise RuntimeError("credential_environment_reached_compute")
    if [name for _, name in socket.if_nameindex()] != ["lo"]:
        raise RuntimeError("compute_network_not_isolated")


def load_profile() -> dict:
    value = json.loads(Path("/execution/profile.json").read_text(encoding="utf-8"))
    if value.get("profile_name") != "r1a-parent-continuation-stagea-v1":
        raise RuntimeError("profile_identity_mismatch")
    if value.get("new_training") is not True or value.get("production_authority") is not False:
        raise RuntimeError("profile_scope_mismatch")
    return value


def run_command(args: list[str], timeout: int, stdout, stderr) -> int:
    try:
        completed = subprocess.run(
            [sys.executable, *args],
            cwd="/work",
            stdout=stdout,
            stderr=stderr,
            timeout=timeout,
            check=False,
        )
        return int(completed.returncode)
    except subprocess.TimeoutExpired:
        return 124
    except Exception:
        return 1


def compute(profile: dict) -> int:
    Path("/results").mkdir(parents=True, exist_ok=True)
    with Path("/results/compute.log").open("xb") as stream:
        code = run_command(
            profile["command"], int(profile["command_timeout_seconds"]), stream, subprocess.STDOUT
        )
    Path("/results/compute_receipt.json").write_text(
        json.dumps(
            {
                "status": "passed" if code == 0 else "failed",
                "exit_code": code,
                "profile_name": profile["profile_name"],
                "new_training": True,
                "current_validation_outcomes_scored": False,
                "stage_b_authorized": False,
                "production_authority": False,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0 if code == 0 else 1


def verify(profile: dict) -> int:
    return run_command(
        profile["verify_command"],
        int(profile["verification_timeout_seconds"]),
        sys.stdout.buffer,
        sys.stderr.buffer,
    )


def main() -> None:
    try:
        require_runtime()
        profile = load_profile()
        args = sys.argv[1:]
        if args == ["validate"]:
            raise SystemExit(verify(profile))
        if args:
            raise RuntimeError("unapproved_container_mode")
        raise SystemExit(compute(profile))
    except SystemExit:
        raise
    except Exception:
        print("r1a_stagea_container_gate_failed", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
