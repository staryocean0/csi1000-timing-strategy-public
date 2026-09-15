"""Bounded future carrier-binding audit broker for Risk Tool V2."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
from pathlib import Path

import research_broker as rb
import risk_phase1b_carrier_inventory_core_v1 as inv

GateError = rb.GateError
PROFILE_NAME = "risk-v2-future-carrier-binding-audit-v1"
TASK_ID = "CSI1000-RISK-V2-FUTURE-CARRIER-BINDING-AUDIT-V1-20260915"
PREREG_SHA256 = "6158bfb13dafe8a6ffee255455320c6598d17c932115985070994cade0030540"
PRIVATE_REF = "7688ba57206dd29fbef88d8e57475255718471fe"
MEMBERS = {
    "000688.SH": "data/market/5m/000688.SH/2026.parquet",
    "000852.SH": "data/market/5m/000852.SH/2026.parquet",
}

PROFILE = {
    "private_ref": PRIVATE_REF,
    "manifest_sha256": PREREG_SHA256,
    "command": [
        "future_binding/risk_future_carrier_binding_audit.py",
        "--inputs",
        "/work/inputs",
        "--out",
        "/results/study",
    ],
    "verify_command": [
        "future_binding/risk_future_carrier_binding_audit_verifier.py",
        "--inputs",
        "/work/inputs",
        "--results",
        "/results/study",
    ],
    "command_timeout_seconds": 1200,
    "verification_timeout_seconds": 1200,
    "new_training": False,
    "production_authority": False,
}
rb.COMPUTE_HOST_TIMEOUT_SECONDS = 1230
rb.VALIDATE_HOST_TIMEOUT_SECONDS = 1230


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require_context() -> None:
    env = os.environ
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != rb.PUBLIC_REPO
        or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
    ):
        raise GateError("not_approved_future_carrier_binding_context")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")):
        raise GateError("invalid_run_identity")
    if not re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ATTEMPT", "")):
        raise GateError("invalid_run_identity")


def _stage_frozen_bundle(api, root: Path) -> tuple[Path, dict]:
    profile = inv.load_profile()
    release = api.request(f"repos/{rb.PRIVATE_REPO}/releases/tags/{profile['data_release_tag']}")
    if release.get("draft") is not False:
        raise GateError("private_data_release_not_published")
    assets = {item["name"]: item for item in release.get("assets") or []}
    compressed = root / profile["data_asset_name"]
    with compressed.open("xb") as combined:
        for index, part in enumerate(profile["asset_parts"]):
            asset = assets.get(part["name"])
            if (
                not asset
                or asset.get("state") != "uploaded"
                or asset.get("size") != part["bytes"]
                or asset.get("digest") != "sha256:" + part["sha256"]
            ):
                raise GateError("future_binding_transport_identity_failed")
            target = root / f"future-binding-part-{index:03d}.bin"
            api.request(
                f"repos/{rb.PRIVATE_REPO}/releases/assets/{asset['id']}",
                binary_path=target,
                max_bytes=part["bytes"],
            )
            if target.stat().st_size != part["bytes"] or sha256_file(target) != part["sha256"]:
                raise GateError("future_binding_transport_download_failed")
            with target.open("rb") as source:
                shutil.copyfileobj(source, combined)
            target.unlink()
    if compressed.stat().st_size != profile["data_asset_bytes"] or sha256_file(compressed) != profile["data_asset_sha256"]:
        raise GateError("future_binding_archive_digest_failed")

    unpacked = root / "future-binding-unpacked"
    unpacked.mkdir()
    bundle = profile["bundle_member"]
    inv.unpack(
        compressed,
        unpacked,
        expected={bundle["name"]: {"bytes": bundle["bytes"], "sha256": bundle["sha256"]}},
    )
    compressed.unlink()
    bundle_path = unpacked / bundle["name"]
    return bundle_path, profile


def _extract_pair(bundle_path: Path, profile: dict, inputs: Path) -> dict:
    pair_dir = inputs / "pair"
    pair_dir.mkdir()
    with tarfile.open(bundle_path, "r:") as tar:
        regular = [m for m in tar.getmembers() if m.isfile()]
        by_name = {m.name: m for m in regular}
        if len(by_name) != len(regular):
            raise GateError("future_binding_duplicate_bundle_member")
        manifest_member = by_name.get("BUNDLE_MANIFEST.json")
        if manifest_member is None or manifest_member.size > inv.MAX_MANIFEST_BYTES:
            raise GateError("future_binding_manifest_missing")
        stream = tar.extractfile(manifest_member)
        if stream is None:
            raise GateError("future_binding_manifest_unreadable")
        raw = stream.read(inv.MAX_MANIFEST_BYTES + 1)
        if len(raw) != manifest_member.size:
            raise GateError("future_binding_manifest_size_mismatch")
        try:
            manifest = json.loads(raw)
        except Exception:
            raise GateError("future_binding_manifest_invalid") from None
        files = manifest.get("files") if isinstance(manifest, dict) else None
        if not isinstance(files, dict):
            raise GateError("future_binding_manifest_files_missing")

        output_members = {}
        for symbol, suffix in MEMBERS.items():
            matches = [m for m in regular if m.name == suffix or m.name.endswith("/" + suffix)]
            if len(matches) != 1:
                raise GateError(f"future_binding_member_not_unique:{symbol}")
            member = matches[0]
            meta = files.get(member.name)
            if not isinstance(meta, dict) or set(meta) != {"bytes", "sha256"}:
                raise GateError(f"future_binding_member_manifest_missing:{symbol}")
            if member.size != meta["bytes"] or not re.fullmatch(r"[0-9a-f]{64}", str(meta["sha256"])):
                raise GateError(f"future_binding_member_manifest_invalid:{symbol}")
            source = tar.extractfile(member)
            if source is None:
                raise GateError(f"future_binding_member_unreadable:{symbol}")
            destination = pair_dir / (symbol + ".parquet")
            with destination.open("xb") as target:
                shutil.copyfileobj(source, target)
            if destination.stat().st_size != meta["bytes"] or sha256_file(destination) != meta["sha256"]:
                raise GateError(f"future_binding_member_digest_failed:{symbol}")
            output_members[symbol] = {
                "archive_path": member.name,
                "bytes": int(meta["bytes"]),
                "sha256": str(meta["sha256"]),
            }

    return {
        "schema_id": "risk_tool_v2_future_carrier_binding_input@1.0",
        "task_id": TASK_ID,
        "prereg_sha256": PREREG_SHA256,
        "source": {
            "private_ref": PRIVATE_REF,
            "release_tag": profile["data_release_tag"],
            "asset_name": profile["data_asset_name"],
            "asset_sha256": profile["data_asset_sha256"],
            "bundle_sha256": profile["bundle_member"]["sha256"],
        },
        "members": output_members,
        "market_values_exported": False,
        "new_training": False,
        "production_authority": False,
    }


def prepare_inputs(api, root: Path, profile: dict):
    work = root / "work"
    work.mkdir()
    scripts = work / "future_binding"
    scripts.mkdir()
    for name in (
        "risk_future_carrier_binding_audit.py",
        "risk_future_carrier_binding_audit_verifier.py",
    ):
        source = Path(__file__).resolve().parent / name
        if not source.is_file() or source.is_symlink():
            raise GateError("future_binding_public_source_missing")
        shutil.copy2(source, scripts / name)

    inputs = work / "inputs"
    inputs.mkdir()
    bundle_path, source_profile = _stage_frozen_bundle(api, root)
    identity = _extract_pair(bundle_path, source_profile, inputs)
    (inputs / "PAIR_INPUT_IDENTITY.json").write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n")
    bundle_path.unlink()
    return work


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "compute", "cleanup", "publish"])
    parser.add_argument("profile", nargs="?", default=PROFILE_NAME)
    args = parser.parse_args()
    require_context()
    if args.profile != PROFILE_NAME:
        raise GateError("unknown_future_carrier_binding_profile")
    os.umask(0o077)
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
        print("Execution failed; no private future-carrier market content was exposed publicly.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run()
