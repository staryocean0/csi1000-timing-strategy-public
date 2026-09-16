"""Bounded broker for Risk Tool V3 Native-60m Phase 60-B descriptive continuity map."""
from __future__ import annotations
import argparse, base64, hashlib, json, os, re, shutil, sys, tarfile, urllib.parse
from pathlib import Path, PurePosixPath
import research_broker as rb

GateError=rb.GateError
PROFILE_NAME="risk-v3-native60-phase60b-volatility-continuity-map-v1"
TASK_ID="CSI1000-RISK-V3-NATIVE60-PHASE60B-VOLATILITY-CONTINUITY-MAP-V1-20260916"
PREREG_SHA256="cc1fe933fa4339f937d01d8f1d39f7d0ba86d8d3903806008c97afcd9675973b"
PREREG_NAME="RISK_TOOL_V3_NATIVE60_PHASE60B_VOLATILITY_CONTINUITY_MAP_PREREG_20260916.json"
PRIVATE_REF="6f41091f1d29c5d6a3aaf74c49f538526c567eef"
PARENT_REF="runs/public-research/35053098772-1"
PARENT_RUN="35053098772-1"
PARENT_RESULT_PATH="research/public-runs/35053098772-1-native60-phase60a.json"
PARENT_RESULT_BLOB="b96e80bd4c1f1ec7645b62b4ca3a012b92505c9e"
PARENT_RECEIPT_PATH="research/public-runs/35053098772-1.json"
PARENT_RECEIPT_BLOB="760611e931b7e30181d569d8338fe04f4cbad114"
PARENT_STATUS="NATIVE60_CANONICAL_CARRIER_VALID"
PARENT_TAG="public-research-run-35053098772-1"
PARENT_RELEASE_ID=389624963
PARENT_ASSET="results.tar.gz"
PARENT_ARCHIVE_BYTES=133785
PARENT_ARCHIVE_SHA256="797507b2ceed2f8458e109e8393ad6a8bc12bf92a00e1ad619cfd919535496a2"
CANON_MEMBER="study/NATIVE60_CANONICAL_60M.parquet"
CANON_BYTES=165623
CANON_SHA256="4414d08c6e256fcb7d151018b935d26363be04920990c7b1c56880c8ec7e0467"
MAX_ARCHIVE_BYTES=1024*1024

PROFILE={"private_ref":PRIVATE_REF,"manifest_sha256":PREREG_SHA256,"command":["native60b/risk_v3_native60_phase60b_volatility_continuity_map.py","--inputs","/work/inputs","--out","/results/study"],"verify_command":["native60b/risk_v3_native60_phase60b_volatility_continuity_map_verifier.py","--inputs","/work/inputs","--results","/results/study"],"command_timeout_seconds":1200,"verification_timeout_seconds":1200,"new_training":False,"production_authority":False}
rb.COMPUTE_HOST_TIMEOUT_SECONDS=1230
rb.VALIDATE_HOST_TIMEOUT_SECONDS=1230

def sha(path:Path)->str:
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def require_context():
    e=os.environ
    if e.get("GITHUB_ACTIONS")!="true" or e.get("GITHUB_REPOSITORY")!=rb.PUBLIC_REPO or e.get("GITHUB_EVENT_NAME")!="workflow_dispatch" or e.get("GITHUB_REF")!="refs/heads/cloud-workspace-v1":raise GateError("not_approved_native60b_context")
    if not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ID","")) or not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ATTEMPT","")):raise GateError("invalid_run_identity")

def safe(name:str)->bool:
    p=PurePosixPath(name);return bool(p.parts) and not p.is_absolute() and ".." not in p.parts and "\\" not in name

def read_parent_json(api,path,blob):
    route=f"repos/{rb.PRIVATE_REPO}/contents/{path}?ref={urllib.parse.quote(PARENT_REF,safe='')}";got=api.request(route)
    if got.get("sha")!=blob:raise GateError("native60b_parent_blob_mismatch:"+path)
    try:raw=base64.b64decode(got["content"]);value=json.loads(raw.decode())
    except Exception as e:raise GateError("native60b_parent_decode_failed:"+path) from e
    if not isinstance(value,dict):raise GateError("native60b_parent_json_invalid:"+path)
    return value

def verify_parent(api):
    parent=read_parent_json(api,PARENT_RESULT_PATH,PARENT_RESULT_BLOB);receipt=read_parent_json(api,PARENT_RECEIPT_PATH,PARENT_RECEIPT_BLOB);p=(parent.get("canonical") or {}).get("private_parquet") or {};controls=parent.get("controls") or {}
    if parent.get("status")!=PARENT_STATUS or parent.get("next_phase_authorized") is not True:raise GateError("native60b_parent_not_authorized")
    if p.get("bytes")!=CANON_BYTES or p.get("sha256")!=CANON_SHA256 or p.get("rows")!=2908:raise GateError("native60b_parent_canonical_mismatch")
    if controls.get("production_authority") is not False or controls.get("risk_threshold_search") is not False:raise GateError("native60b_parent_control_mismatch")
    arc=receipt.get("archive") or {};files=receipt.get("files") or {};cf=files.get(CANON_MEMBER) or {}
    if receipt.get("status")!="passed" or receipt.get("delivery_status")!="archive_uploaded_and_verified" or receipt.get("public_run_id")!=PARENT_RUN or receipt.get("profile")!="risk-v3-native60-phase60a-canonical-carrier-v1":raise GateError("native60b_parent_receipt_not_passed")
    if arc.get("release_id")!=PARENT_RELEASE_ID or arc.get("tag")!=PARENT_TAG or arc.get("bytes")!=PARENT_ARCHIVE_BYTES or arc.get("sha256")!=PARENT_ARCHIVE_SHA256:raise GateError("native60b_parent_archive_receipt_mismatch")
    if cf.get("bytes")!=CANON_BYTES or cf.get("sha256")!=CANON_SHA256:raise GateError("native60b_parent_file_receipt_mismatch")
    if receipt.get("new_training") is not False or receipt.get("production_authority") is not False:raise GateError("native60b_parent_receipt_control_mismatch")
    return parent,receipt

def stage_parent_archive(api,root:Path,inputs:Path):
    release=api.request(f"repos/{rb.PRIVATE_REPO}/releases/tags/{PARENT_TAG}")
    if release.get("id")!=PARENT_RELEASE_ID or release.get("tag_name")!=PARENT_TAG or release.get("target_commitish")!=PRIVATE_REF:raise GateError("native60b_parent_release_identity_mismatch")
    matches=[a for a in (release.get("assets") or []) if a.get("name")==PARENT_ASSET]
    if len(matches)!=1:raise GateError("native60b_parent_asset_not_unique")
    asset=matches[0]
    if asset.get("state")!="uploaded" or asset.get("size")!=PARENT_ARCHIVE_BYTES or asset.get("digest")!="sha256:"+PARENT_ARCHIVE_SHA256:raise GateError("native60b_parent_asset_identity_mismatch")
    archive=root/"phase60a-results.tar.gz";api.request(f"repos/{rb.PRIVATE_REPO}/releases/assets/{asset['id']}",binary_path=archive,max_bytes=MAX_ARCHIVE_BYTES)
    if archive.stat().st_size!=PARENT_ARCHIVE_BYTES or sha(archive)!=PARENT_ARCHIVE_SHA256:raise GateError("native60b_parent_archive_download_mismatch")
    with tarfile.open(archive,"r:gz") as t:
        members=t.getmembers()
        if any(not safe(m.name) for m in members):raise GateError("native60b_parent_archive_unsafe_path")
        targets=[m for m in members if m.name==CANON_MEMBER]
        if len(targets)!=1 or not targets[0].isfile() or targets[0].size!=CANON_BYTES:raise GateError("native60b_parent_canonical_member_invalid")
        stream=t.extractfile(targets[0]);raw=stream.read(CANON_BYTES+1)
        if len(raw)!=CANON_BYTES or hashlib.sha256(raw).hexdigest()!=CANON_SHA256:raise GateError("native60b_parent_canonical_member_digest_mismatch")
        (inputs/"NATIVE60_CANONICAL_60M.parquet").write_bytes(raw)
    archive.unlink()

def prepare_inputs(api,root:Path,profile:dict):
    work=root/"work";work.mkdir();scripts=work/"native60b";scripts.mkdir();here=Path(__file__).resolve().parent
    for name in ("risk_v3_native60_phase60b_volatility_continuity_map.py","risk_v3_native60_phase60b_volatility_continuity_map_verifier.py"):
        src=here/name
        if not src.is_file() or src.is_symlink():raise GateError("native60b_public_source_missing")
        shutil.copy2(src,scripts/name)
    inputs=work/"inputs";inputs.mkdir();prereg=Path(__file__).resolve().parents[1]/"docs"/"research"/PREREG_NAME
    if not prereg.is_file() or prereg.is_symlink() or sha(prereg)!=PREREG_SHA256:raise GateError("native60b_prereg_identity_failed")
    shutil.copy2(prereg,inputs/"PREREG.json");parent,receipt=verify_parent(api);(inputs/"PHASE60A_PARENT.json").write_text(json.dumps(parent,indent=2,sort_keys=True)+"\n");(inputs/"PHASE60A_RECEIPT.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n");stage_parent_archive(api,root,inputs)
    ident={"schema_id":"risk_tool_v3_native60_phase60b_input_identity@1.0","task_id":TASK_ID,"prereg_sha256":PREREG_SHA256,"parent_run_id":PARENT_RUN,"parent_ref":PARENT_REF,"parent_safe_result_git_blob_sha":PARENT_RESULT_BLOB,"parent_receipt_git_blob_sha":PARENT_RECEIPT_BLOB,"parent_release":{"id":PARENT_RELEASE_ID,"tag":PARENT_TAG,"archive_bytes":PARENT_ARCHIVE_BYTES,"archive_sha256":PARENT_ARCHIVE_SHA256},"canonical":{"archive_member":CANON_MEMBER,"bytes":CANON_BYTES,"sha256":CANON_SHA256,"rows":2908},"controls":{"rebuild_from_1m":False,"alternate_carrier":False,"use_2024_2025_market_values":False,"use_2026_market_values":False,"new_training":False,"production_authority":False}}
    (inputs/"DATA_IDENTITY.json").write_text(json.dumps(ident,indent=2,sort_keys=True)+"\n");return work

def main():
    p=argparse.ArgumentParser();p.add_argument("phase",choices=["prepare","compute","cleanup","publish"]);p.add_argument("profile",nargs="?",default=PROFILE_NAME);a=p.parse_args();require_context()
    if a.profile!=PROFILE_NAME:raise GateError("unknown_native60b_profile")
    os.umask(0o077);rb.prepare_inputs=prepare_inputs
    if a.phase=="prepare":rb.prepare(PROFILE_NAME,PROFILE)
    elif a.phase=="compute":rb.compute()
    elif a.phase=="cleanup":rb.cleanup()
    else:rb.publish(PROFILE)

def run():
    try:main()
    except GateError as e:print("Execution stopped: "+str(e),file=sys.stderr);raise SystemExit(1)
    except Exception:print("Execution failed; no private Native-60m row-level values were exposed publicly.",file=sys.stderr);raise
if __name__=="__main__":run()
