"""Bounded broker for Risk Tool V3 Native-60m Phase 60-C1 causal state-score selection."""
from __future__ import annotations
import argparse, base64, hashlib, json, os, re, shutil, sys, tarfile, urllib.parse
from pathlib import Path, PurePosixPath
import research_broker as rb

GateError=rb.GateError
PROFILE_NAME="risk-v3-native60-phase60c1-state-score-selection-v1"
TASK_ID="CSI1000-RISK-V3-NATIVE60-PHASE60C1-CAUSAL-STATE-SCORE-SELECTION-V1-20260922"
PREREG_SHA256="1c3c72747b8327c10a52cf007f4d696fd374370c001e89ec989d4241a598469c"
PREREG_NAME="RISK_TOOL_V3_NATIVE60_PHASE60C1_STATE_SCORE_PREREG_20260922.json"
PRIVATE_REF="6f41091f1d29c5d6a3aaf74c49f538526c567eef"

PHASE60B_REF="runs/public-research/35057818977-1"
PHASE60B_RUN="35057818977-1"
PHASE60B_RESULT_PATH="research/public-runs/35057818977-1-native60-phase60b.json"
PHASE60B_RESULT_BLOB="287fbf999c95f34dd5b70029332d711dcc650ec2"
PHASE60B_RECEIPT_PATH="research/public-runs/35057818977-1.json"
PHASE60B_RECEIPT_BLOB="c279914d7ef5ae0ce4c3031b86eafcf8438e8e39"
PHASE60B_STATUS="NATIVE60_DESCRIPTIVE_MAP_COMPLETE"
PHASE60B_PROFILE="risk-v3-native60-phase60b-volatility-continuity-map-v1"
PHASE60B_PREREG_SHA="cc1fe933fa4339f937d01d8f1d39f7d0ba86d8d3903806008c97afcd9675973b"
PHASE60B_RELEASE_ID=389649468
PHASE60B_TAG="public-research-run-35057818977-1"
PHASE60B_ARCHIVE_BYTES=9493
PHASE60B_ARCHIVE_SHA256="b92c573c1d1c9e86ff1b6b04fb1eab4d8f2731cf34da5b361eaff8f13ee2e223"

PHASE60A_TAG="public-research-run-35053098772-1"
PHASE60A_RELEASE_ID=389624963
PHASE60A_ASSET="results.tar.gz"
PHASE60A_ARCHIVE_BYTES=133785
PHASE60A_ARCHIVE_SHA256="797507b2ceed2f8458e109e8393ad6a8bc12bf92a00e1ad619cfd919535496a2"
CANON_MEMBER="study/NATIVE60_CANONICAL_60M.parquet"
CANON_BYTES=165623
CANON_SHA256="4414d08c6e256fcb7d151018b935d26363be04920990c7b1c56880c8ec7e0467"
MAX_ARCHIVE_BYTES=1024*1024

PROFILE={"private_ref":PRIVATE_REF,"manifest_sha256":PREREG_SHA256,
"command":["native60c1/risk_v3_native60_phase60c1_state_score.py","--inputs","/work/inputs","--out","/results/study"],
"verify_command":["native60c1/risk_v3_native60_phase60c1_state_score_verifier.py","--inputs","/work/inputs","--results","/results/study"],
"command_timeout_seconds":1200,"verification_timeout_seconds":1200,"new_training":False,"production_authority":False}
rb.COMPUTE_HOST_TIMEOUT_SECONDS=1230
rb.VALIDATE_HOST_TIMEOUT_SECONDS=1230

def sha(path:Path)->str:
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def require_context():
    e=os.environ
    if e.get("GITHUB_ACTIONS")!="true" or e.get("GITHUB_REPOSITORY")!=rb.PUBLIC_REPO or e.get("GITHUB_EVENT_NAME")!="workflow_dispatch" or e.get("GITHUB_REF")!="refs/heads/cloud-workspace-v1":raise GateError("not_approved_native60c1_context")
    if not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ID","")) or not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ATTEMPT","")):raise GateError("invalid_run_identity")

def safe(name:str)->bool:
    p=PurePosixPath(name);return bool(p.parts) and not p.is_absolute() and ".." not in p.parts and "\\" not in name

def read_json(api,path,ref,blob):
    route=f"repos/{rb.PRIVATE_REPO}/contents/{path}?ref={urllib.parse.quote(ref,safe='')}"
    got=api.request(route)
    if got.get("sha")!=blob:raise GateError("native60c1_parent_blob_mismatch:"+path)
    try:raw=base64.b64decode(got["content"]);value=json.loads(raw.decode())
    except Exception as e:raise GateError("native60c1_parent_decode_failed:"+path) from e
    if not isinstance(value,dict):raise GateError("native60c1_parent_json_invalid:"+path)
    return value

def verify_phase60b(api):
    parent=read_json(api,PHASE60B_RESULT_PATH,PHASE60B_REF,PHASE60B_RESULT_BLOB)
    receipt=read_json(api,PHASE60B_RECEIPT_PATH,PHASE60B_REF,PHASE60B_RECEIPT_BLOB)
    if parent.get("status")!=PHASE60B_STATUS or parent.get("task_id")!="CSI1000-RISK-V3-NATIVE60-PHASE60B-VOLATILITY-CONTINUITY-MAP-V1-20260916":raise GateError("native60c1_phase60b_status_invalid")
    if parent.get("prereg_sha256")!=PHASE60B_PREREG_SHA or parent.get("scientific_authority")!="descriptive_mechanistic_only":raise GateError("native60c1_phase60b_authority_invalid")
    if parent.get("next_phase_authorized") is not False or parent.get("next_phase")!="requires_separate_preregistration_after_phase60b_readback":raise GateError("native60c1_phase60b_next_phase_invalid")
    controls=parent.get("controls") or {}
    if not isinstance(controls,dict) or any(v is not False for v in controls.values()):raise GateError("native60c1_phase60b_controls_invalid")
    canon=((parent.get("parent") or {}).get("canonical") or {})
    if canon.get("bytes")!=CANON_BYTES or canon.get("rows")!=2908 or canon.get("sha256")!=CANON_SHA256:raise GateError("native60c1_phase60b_canonical_invalid")
    arc=receipt.get("archive") or {}
    if receipt.get("status")!="passed" or receipt.get("delivery_status")!="archive_uploaded_and_verified" or receipt.get("public_run_id")!=PHASE60B_RUN or receipt.get("profile")!=PHASE60B_PROFILE or receipt.get("manifest_sha256")!=PHASE60B_PREREG_SHA:raise GateError("native60c1_phase60b_receipt_invalid")
    if arc.get("release_id")!=PHASE60B_RELEASE_ID or arc.get("tag")!=PHASE60B_TAG or arc.get("bytes")!=PHASE60B_ARCHIVE_BYTES or arc.get("sha256")!=PHASE60B_ARCHIVE_SHA256:raise GateError("native60c1_phase60b_archive_invalid")
    if receipt.get("new_training") is not False or receipt.get("production_authority") is not False:raise GateError("native60c1_phase60b_receipt_controls_invalid")
    return parent,receipt

def stage_canonical(api,root:Path,inputs:Path):
    release=api.request(f"repos/{rb.PRIVATE_REPO}/releases/tags/{PHASE60A_TAG}")
    if release.get("id")!=PHASE60A_RELEASE_ID or release.get("tag_name")!=PHASE60A_TAG or release.get("target_commitish")!=PRIVATE_REF:raise GateError("native60c1_phase60a_release_identity_mismatch")
    matches=[a for a in (release.get("assets") or []) if a.get("name")==PHASE60A_ASSET]
    if len(matches)!=1:raise GateError("native60c1_phase60a_asset_not_unique")
    asset=matches[0]
    if asset.get("state")!="uploaded" or asset.get("size")!=PHASE60A_ARCHIVE_BYTES or asset.get("digest")!="sha256:"+PHASE60A_ARCHIVE_SHA256:raise GateError("native60c1_phase60a_asset_identity_mismatch")
    archive=root/"phase60a-results.tar.gz"
    api.request(f"repos/{rb.PRIVATE_REPO}/releases/assets/{asset['id']}",binary_path=archive,max_bytes=MAX_ARCHIVE_BYTES)
    if archive.stat().st_size!=PHASE60A_ARCHIVE_BYTES or sha(archive)!=PHASE60A_ARCHIVE_SHA256:raise GateError("native60c1_phase60a_archive_download_mismatch")
    with tarfile.open(archive,"r:gz") as t:
        members=t.getmembers()
        if any(not safe(m.name) for m in members):raise GateError("native60c1_phase60a_archive_unsafe_path")
        targets=[m for m in members if m.name==CANON_MEMBER]
        if len(targets)!=1 or not targets[0].isfile() or targets[0].size!=CANON_BYTES:raise GateError("native60c1_canonical_member_invalid")
        stream=t.extractfile(targets[0]);raw=stream.read(CANON_BYTES+1)
        if len(raw)!=CANON_BYTES or hashlib.sha256(raw).hexdigest()!=CANON_SHA256:raise GateError("native60c1_canonical_digest_mismatch")
        (inputs/"NATIVE60_CANONICAL_60M.parquet").write_bytes(raw)
    archive.unlink()

def prepare_inputs(api,root:Path,profile:dict):
    work=root/"work";work.mkdir();scripts=work/"native60c1";scripts.mkdir();here=Path(__file__).resolve().parent
    for name in ("risk_v3_native60_phase60c1_state_score.py","risk_v3_native60_phase60c1_state_score_verifier.py"):
        src=here/name
        if not src.is_file() or src.is_symlink():raise GateError("native60c1_public_source_missing")
        shutil.copy2(src,scripts/name)
    inputs=work/"inputs";inputs.mkdir()
    prereg=Path(__file__).resolve().parents[1]/"docs"/"research"/PREREG_NAME
    if not prereg.is_file() or prereg.is_symlink() or sha(prereg)!=PREREG_SHA256:raise GateError("native60c1_prereg_identity_failed")
    shutil.copy2(prereg,inputs/"PREREG.json")
    parent,receipt=verify_phase60b(api)
    (inputs/"PHASE60B_PARENT.json").write_text(json.dumps(parent,indent=2,sort_keys=True)+"\n")
    (inputs/"PHASE60B_RECEIPT.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    stage_canonical(api,root,inputs)
    ident={"schema_id":"risk_tool_v3_native60_phase60c1_input_identity@1.0","task_id":TASK_ID,"prereg_sha256":PREREG_SHA256,
      "phase60b_run_id":PHASE60B_RUN,"phase60b_ref":PHASE60B_REF,"phase60b_result_git_blob_sha":PHASE60B_RESULT_BLOB,"phase60b_receipt_git_blob_sha":PHASE60B_RECEIPT_BLOB,
      "canonical":{"source_release_id":PHASE60A_RELEASE_ID,"source_tag":PHASE60A_TAG,"archive_member":CANON_MEMBER,"bytes":CANON_BYTES,"sha256":CANON_SHA256,"rows":2908},
      "controls":{"rebuild_from_1m":False,"alternate_carrier":False,"use_2024_2025_market_values":False,"use_2026_market_values":False,"new_training":False,"production_authority":False}}
    (inputs/"DATA_IDENTITY.json").write_text(json.dumps(ident,indent=2,sort_keys=True)+"\n")
    return work

def main():
    p=argparse.ArgumentParser();p.add_argument("phase",choices=["prepare","compute","cleanup","publish"]);p.add_argument("profile",nargs="?",default=PROFILE_NAME);a=p.parse_args();require_context()
    if a.profile!=PROFILE_NAME:raise GateError("unknown_native60c1_profile")
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
