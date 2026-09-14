from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import os
import re
import shutil
import sys
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path

HERE=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location("_research_broker",HERE/"research_broker.py")
rb=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(rb);GateError=rb.GateError
rb.VALIDATE_HOST_TIMEOUT_SECONDS=630
PROFILE_NAME="risk-v2-historical-000852-2015-2019-v1"
PRIVATE_REF="3879de41a5ac7c12246b811f51d16dc8586b9dae"
SOURCE_PATH="runtime/research/risk_tool_v2_severity_persistence_v1/run_study.py"
SOURCE_BLOB="7a9f238442f5a4836c6f38dcafec4bc34526fc5c"
DATA_REF="1d760ea9525eb3688b70a4aa0f2b5b207af16a17"
DATA={
2015:(368026,"9d2d84440275413623ff738ae8c25950e4b67f27"),2016:(351061,"08c24b173d259f44061e2f7ffdc572b99ede2dfc"),
2017:(347979,"31a9c0700b8d96249313738bccbf4502c0489be7"),2018:(351575,"db4b03041c673a60606b75a56e15682f42e2b7a4"),2019:(346434,"9dadff0a88a6a03f8defcf12ba28b1e6f57fd84e")}
P1=(388319643,563182909,8115479,"c201cd1b2ab18442ca49d60209b181557335595efdb6a4da5d78549b5c32b21b","study/MODEL_FREEZE.json",15921,"b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551")
P1B=(388398729,563403877,8090245,"197c15aaa725a20cbfd7b07ff639e59c400b38eaa49c0141fa6fca9d035dd3fc","study/CALIBRATION_FREEZE.json",2068,"74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909")
PROFILE={"private_ref":PRIVATE_REF,"manifest_sha256":P1[6],"command":["historical/risk_historical_000852.py","--inputs","/work/inputs","--out","/results/study"],"verify_command":["historical/risk_historical_000852_verifier.py","--inputs","/work/inputs","--results","/results/study"],"command_timeout_seconds":900,"verification_timeout_seconds":600,"new_training":False,"production_authority":False}

def blobsha(raw:bytes)->str:return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def sha(p:Path)->str:
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def require_context():
    e=os.environ
    if e.get("GITHUB_ACTIONS")!="true" or e.get("GITHUB_REPOSITORY")!=rb.PUBLIC_REPO or e.get("GITHUB_EVENT_NAME")!="workflow_dispatch" or e.get("GITHUB_REF")!="refs/heads/cloud-workspace-v1":raise GateError("not_approved_historical_context")
    if not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ID","")) or not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ATTEMPT","")):raise GateError("invalid_run_identity")

def fetch_public(year:int,target:Path):
    size,blob=DATA[year];url=f"https://raw.githubusercontent.com/staryocean0/factorlab-trend-reversion-regime-lab/{DATA_REF}/data/market/5m/000852.SH/{year}.parquet"
    req=urllib.request.Request(url,headers={"User-Agent":"csi1000-reviewed-executor"})
    with urllib.request.urlopen(req,timeout=60) as resp:
        if urllib.parse.urlparse(resp.geturl()).hostname!="raw.githubusercontent.com":raise GateError("historical_public_redirect_rejected")
        raw=resp.read(size+1)
    if len(raw)!=size or blobsha(raw)!=blob:raise GateError("historical_public_identity_failed")
    target.write_bytes(raw)

def extract_fixed(api,root:Path,spec:tuple,destination:Path):
    release_id,asset_id,asset_bytes,asset_sha,member_name,member_bytes,member_sha=spec
    rel=api.request(f"repos/{rb.PRIVATE_REPO}/releases/{release_id}")
    asset=next((x for x in rel.get("assets") or [] if x.get("id")==asset_id),None)
    if not asset or asset.get("state")!="uploaded" or asset.get("size")!=asset_bytes or asset.get("digest")!="sha256:"+asset_sha:raise GateError("historical_parent_release_identity_failed")
    arc=root/f"parent_{release_id}.tar.gz";api.request(f"repos/{rb.PRIVATE_REPO}/releases/assets/{asset_id}",binary_path=arc,max_bytes=asset_bytes)
    if arc.stat().st_size!=asset_bytes or sha(arc)!=asset_sha:raise GateError("historical_parent_archive_failed")
    with tarfile.open(arc,"r:gz") as t:
        try:m=t.getmember(member_name)
        except KeyError:raise GateError("historical_parent_member_missing") from None
        if not m.isfile() or m.size!=member_bytes:raise GateError("historical_parent_member_invalid")
        raw=t.extractfile(m).read()
    if len(raw)!=member_bytes or hashlib.sha256(raw).hexdigest()!=member_sha:raise GateError("historical_parent_member_digest_failed")
    destination.write_bytes(raw)

def prepare_inputs(api,root:Path,profile:dict):
    work=root/"work";work.mkdir();inputs=work/"inputs";inputs.mkdir();scripts=work/"historical";scripts.mkdir()
    for name in ("risk_historical_000852.py","risk_historical_000852_verifier.py"):
        src=HERE/name
        if not src.is_file() or src.is_symlink():raise GateError("historical_public_source_missing")
        shutil.copy2(src,scripts/name)
    source=api.request(f"repos/{rb.PRIVATE_REPO}/contents/{SOURCE_PATH}?ref={PRIVATE_REF}")
    raw=base64.b64decode(source.get("content","") or "")
    if source.get("sha")!=SOURCE_BLOB or blobsha(raw)!=SOURCE_BLOB:raise GateError("historical_phase1_source_identity_failed")
    (inputs/"phase1_run_study.py").write_bytes(raw)
    extract_fixed(api,root,P1,inputs/"MODEL_FREEZE.json");extract_fixed(api,root,P1B,inputs/"CALIBRATION_FREEZE.json")
    for y in DATA:fetch_public(y,inputs/f"{y}.parquet")
    return work

def main():
    p=argparse.ArgumentParser();p.add_argument("phase",choices=["prepare","compute","cleanup","publish"]);p.add_argument("profile",nargs="?",default=PROFILE_NAME);a=p.parse_args();require_context()
    if a.profile!=PROFILE_NAME:raise GateError("unknown_historical_profile")
    rb.prepare_inputs=prepare_inputs
    if a.phase=="prepare":rb.prepare(PROFILE_NAME,PROFILE)
    elif a.phase=="compute":rb.compute()
    elif a.phase=="cleanup":rb.cleanup()
    else:rb.publish(PROFILE)

def run():
    try:main()
    except GateError as e:print("Execution stopped: "+str(e),file=sys.stderr);raise SystemExit(1)
    except Exception:print("Execution failed; no private historical content was exposed publicly.",file=sys.stderr);raise SystemExit(1)
if __name__=="__main__":run()
