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
rb.COMPUTE_HOST_TIMEOUT_SECONDS=930
rb.VALIDATE_HOST_TIMEOUT_SECONDS=930
PROFILE_NAME="risk-v2-temporal-stability-2015-2025-v1"
PRIVATE_REF="3879de41a5ac7c12246b811f51d16dc8586b9dae"
SOURCE_PATH="runtime/research/risk_tool_v2_severity_persistence_v1/run_study.py"
SOURCE_BLOB="7a9f238442f5a4836c6f38dcafec4bc34526fc5c"
DATA_REF="1d760ea9525eb3688b70a4aa0f2b5b207af16a17"
DATA={
2015:(368026,"9d2d84440275413623ff738ae8c25950e4b67f27"),2016:(351061,"08c24b173d259f44061e2f7ffdc572b99ede2dfc"),
2017:(347979,"31a9c0700b8d96249313738bccbf4502c0489be7"),2018:(351575,"db4b03041c673a60606b75a56e15682f42e2b7a4"),
2019:(346434,"9dadff0a88a6a03f8defcf12ba28b1e6f57fd84e"),2020:(353781,"c45ef84c123ae9f4ca1843b2816a4f413742547e"),
2021:(347162,"aba298f940c7992ec8814dd8ece197477d106fa9"),2022:(351753,"fe6eed805f7237091813c32d25011848fc29b705"),
2023:(342750,"0b17d76b150bfd15d45158f100748898e72089b1"),2024:(349739,"ba45837375d8a3ca64cb3faa7750bf51e9760796"),
2025:(353882,"85159b9fa1b2b6854b1a0f04faa9f963e9d04c13")}
P1=(388319643,563182909,8115479,"c201cd1b2ab18442ca49d60209b181557335595efdb6a4da5d78549b5c32b21b","study/MODEL_FREEZE.json",15921,"b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551")
P1B=(388398729,563403877,8090245,"197c15aaa725a20cbfd7b07ff639e59c400b38eaa49c0141fa6fca9d035dd3fc","study/CALIBRATION_FREEZE.json",2068,"74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909")
PROFILE={"private_ref":PRIVATE_REF,"manifest_sha256":P1[6],"command":["temporal/risk_temporal_stability_2015_2025.py","--inputs","/work/inputs","--out","/results/study"],"verify_command":["temporal/risk_temporal_stability_2015_2025_verifier.py","--inputs","/work/inputs","--results","/results/study"],"command_timeout_seconds":900,"verification_timeout_seconds":900,"new_training":False,"production_authority":False}

def blobsha(raw:bytes)->str:return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def sha(path:Path)->str:
    with path.open("rb") as handle:return hashlib.file_digest(handle,"sha256").hexdigest()

def require_context():
    env=os.environ
    if env.get("GITHUB_ACTIONS")!="true" or env.get("GITHUB_REPOSITORY")!=rb.PUBLIC_REPO or env.get("GITHUB_EVENT_NAME")!="workflow_dispatch" or env.get("GITHUB_REF")!="refs/heads/cloud-workspace-v1":raise GateError("not_approved_temporal_stability_context")
    if not re.fullmatch(r"[0-9]+",env.get("GITHUB_RUN_ID","") or "") or not re.fullmatch(r"[0-9]+",env.get("GITHUB_RUN_ATTEMPT","") or ""):raise GateError("invalid_run_identity")

def fetch_public(year:int,target:Path):
    size,blob=DATA[year];url=f"https://raw.githubusercontent.com/staryocean0/factorlab-trend-reversion-regime-lab/{DATA_REF}/data/market/5m/000852.SH/{year}.parquet"
    req=urllib.request.Request(url,headers={"User-Agent":"csi1000-reviewed-executor"})
    with urllib.request.urlopen(req,timeout=60) as response:
        if urllib.parse.urlparse(response.geturl()).hostname!="raw.githubusercontent.com":raise GateError("temporal_public_redirect_rejected")
        raw=response.read(size+1)
    if len(raw)!=size or blobsha(raw)!=blob:raise GateError("temporal_public_identity_failed")
    target.write_bytes(raw)

def extract_fixed(api,root:Path,spec:tuple,destination:Path):
    release_id,asset_id,asset_bytes,asset_sha,member_name,member_bytes,member_sha=spec
    release=api.request(f"repos/{rb.PRIVATE_REPO}/releases/{release_id}")
    asset=next((item for item in release.get("assets") or [] if item.get("id")==asset_id),None)
    if not asset or asset.get("state")!="uploaded" or asset.get("size")!=asset_bytes or asset.get("digest")!="sha256:"+asset_sha:raise GateError("temporal_parent_release_identity_failed")
    archive=root/f"parent_{release_id}.tar.gz";api.request(f"repos/{rb.PRIVATE_REPO}/releases/assets/{asset_id}",binary_path=archive,max_bytes=asset_bytes)
    if archive.stat().st_size!=asset_bytes or sha(archive)!=asset_sha:raise GateError("temporal_parent_archive_failed")
    with tarfile.open(archive,"r:gz") as tar:
        try:member=tar.getmember(member_name)
        except KeyError:raise GateError("temporal_parent_member_missing") from None
        if not member.isfile() or member.size!=member_bytes:raise GateError("temporal_parent_member_invalid")
        raw=tar.extractfile(member).read()
    if len(raw)!=member_bytes or hashlib.sha256(raw).hexdigest()!=member_sha:raise GateError("temporal_parent_member_digest_failed")
    destination.write_bytes(raw)

def prepare_inputs(api,root:Path,profile:dict):
    work=root/"work";work.mkdir();inputs=work/"inputs";inputs.mkdir();scripts=work/"temporal";scripts.mkdir()
    for name in ("risk_temporal_stability_2015_2025.py","risk_temporal_stability_2015_2025_verifier.py"):
        source=HERE/name
        if not source.is_file() or source.is_symlink():raise GateError("temporal_public_source_missing")
        shutil.copy2(source,scripts/name)
    for name in ("risk_temporal_stability_acceptance.py","risk_temporal_stability_hierarchical_acceptance.py"):
        source=HERE/name
        if not source.is_file() or source.is_symlink():raise GateError("temporal_acceptance_source_missing")
        shutil.copy2(source,inputs/name)
    profile_source=HERE.parent/"docs/acceptance/risk_tool_v2/temporal_stability_profile_hierarchical_v1.json"
    if not profile_source.is_file() or profile_source.is_symlink():raise GateError("temporal_profile_missing")
    shutil.copy2(profile_source,inputs/"TEMPORAL_PROFILE.json")
    private_source=api.request(f"repos/{rb.PRIVATE_REPO}/contents/{SOURCE_PATH}?ref={PRIVATE_REF}")
    raw=base64.b64decode(private_source.get("content","") or "")
    if private_source.get("sha")!=SOURCE_BLOB or blobsha(raw)!=SOURCE_BLOB:raise GateError("temporal_phase1_source_identity_failed")
    (inputs/"phase1_run_study.py").write_bytes(raw)
    extract_fixed(api,root,P1,inputs/"MODEL_FREEZE.json");extract_fixed(api,root,P1B,inputs/"CALIBRATION_FREEZE.json")
    for year in DATA:fetch_public(year,inputs/f"{year}.parquet")
    return work

def main():
    parser=argparse.ArgumentParser();parser.add_argument("phase",choices=["prepare","compute","cleanup","publish"]);parser.add_argument("profile",nargs="?",default=PROFILE_NAME);args=parser.parse_args();require_context()
    if args.profile!=PROFILE_NAME:raise GateError("unknown_temporal_stability_profile")
    rb.prepare_inputs=prepare_inputs
    if args.phase=="prepare":rb.prepare(PROFILE_NAME,PROFILE)
    elif args.phase=="compute":rb.compute()
    elif args.phase=="cleanup":rb.cleanup()
    else:rb.publish(PROFILE)

def run():
    try:main()
    except GateError as error:print("Execution stopped: "+str(error),file=sys.stderr);raise SystemExit(1)
    except Exception:print("Execution failed; no private temporal-stability content was exposed publicly.",file=sys.stderr);raise SystemExit(1)
if __name__=="__main__":run()
