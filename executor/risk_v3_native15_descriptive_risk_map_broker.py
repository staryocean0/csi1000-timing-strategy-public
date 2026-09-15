"""Bounded broker for Risk Tool V3 Native-15m Phase-B descriptive risk map."""
from __future__ import annotations
import argparse, base64, hashlib, json, os, re, shutil, sys, tarfile, urllib.parse
from pathlib import Path, PurePosixPath
import research_broker as rb
import risk_phase1b_carrier_inventory_core_v1 as inv

GateError=rb.GateError
PROFILE_NAME="risk-v3-native15-descriptive-risk-map-v1"
TASK_ID="CSI1000-RISK-V3-NATIVE15-PHASE-B-DESCRIPTIVE-MAP-V1-20260915"
PREREG_SHA256="40226ae2681d34de6479e9589e18a99825a863cb64ad6b6167d36d8a0376d2b6"
PREREG_NAME="RISK_TOOL_V3_NATIVE15_PHASE_B_DESCRIPTIVE_MAP_PREREG_20260915.json"
PRIVATE_REF="6f41091f1d29c5d6a3aaf74c49f538526c567eef"
CARRIER_SUFFIX="data/index/15m_offset_5.parquet"
SOURCE_SUFFIX="data/index/SOURCE_MANIFEST.json"
CARRIER_BYTES=1669752
CARRIER_SHA256="d69e87662d9e525396ed776b754ff43fca58dd021df4a84f96b60a6a5e4864d6"
SOURCE_BYTES=52711
SOURCE_SHA256="c46f2da6c3df016ca054e183e37267dc472097450fcdd6644c22aa0084c15749"
PARENT_REF="runs/public-research/34982948347-1"
PARENT_RESULT_PATH="research/public-runs/34982948347-1-native15-phase-a.json"
PARENT_BLOB_SHA="f92fd121990caefc97cde7037ea5dad72541981c"
PARENT_STATUS="NATIVE15_CARRIER_SEMANTICS_VALID"
MAX_CARRIER_BYTES=64*1024*1024

PROFILE={
 "private_ref":PRIVATE_REF,
 "manifest_sha256":PREREG_SHA256,
 "command":["native15b/risk_v3_native15_descriptive_risk_map.py","--inputs","/work/inputs","--out","/results/study"],
 "verify_command":["native15b/risk_v3_native15_descriptive_risk_map_verifier.py","--inputs","/work/inputs","--results","/results/study"],
 "command_timeout_seconds":1200,
 "verification_timeout_seconds":1200,
 "new_training":False,
 "production_authority":False,
}
rb.COMPUTE_HOST_TIMEOUT_SECONDS=1230
rb.VALIDATE_HOST_TIMEOUT_SECONDS=1230

def sha(path:Path)->str:
    with path.open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()

def require_context():
    e=os.environ
    if e.get("GITHUB_ACTIONS")!="true" or e.get("GITHUB_REPOSITORY")!=rb.PUBLIC_REPO or e.get("GITHUB_EVENT_NAME")!="workflow_dispatch" or e.get("GITHUB_REF")!="refs/heads/cloud-workspace-v1":
        raise GateError("not_approved_native15b_context")
    if not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ID","")) or not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ATTEMPT","")):
        raise GateError("invalid_run_identity")

def safe(name:str)->bool:
    p=PurePosixPath(name)
    return bool(p.parts) and not p.is_absolute() and ".." not in p.parts and "\\" not in name

def verify_parent(api)->dict:
    route=f"repos/{rb.PRIVATE_REPO}/contents/{PARENT_RESULT_PATH}?ref={urllib.parse.quote(PARENT_REF,safe='')}"
    got=api.request(route)
    if got.get("sha")!=PARENT_BLOB_SHA: raise GateError("native15b_parent_blob_mismatch")
    try:
        raw=base64.b64decode(got["content"]); v=json.loads(raw.decode())
    except Exception as e:
        raise GateError("native15b_parent_decode_failed") from e
    carrier=v.get("carrier") or {}
    if v.get("status")!=PARENT_STATUS or v.get("next_phase_authorized") is not True:
        raise GateError("native15b_parent_not_authorized")
    if carrier.get("bytes")!=CARRIER_BYTES or carrier.get("sha256")!=CARRIER_SHA256:
        raise GateError("native15b_parent_carrier_mismatch")
    controls=v.get("controls") or {}
    if controls.get("production_authority") is not False or controls.get("threshold_search") is not False:
        raise GateError("native15b_parent_control_mismatch")
    return v

def stage_bundle(api,root:Path):
    profile=inv.load_profile()
    release=api.request(f"repos/{rb.PRIVATE_REPO}/releases/tags/{profile['data_release_tag']}")
    assets={x["name"]:x for x in release.get("assets") or []}
    compressed=root/profile["data_asset_name"]
    with compressed.open("xb") as out:
        for i,part in enumerate(profile["asset_parts"]):
            asset=assets.get(part["name"])
            if not asset or asset.get("state")!="uploaded" or asset.get("size")!=part["bytes"] or asset.get("digest")!="sha256:"+part["sha256"]:
                raise GateError("native15b_transport_identity_failed")
            tmp=root/f"native15b-part-{i:03d}.bin"
            api.request(f"repos/{rb.PRIVATE_REPO}/releases/assets/{asset['id']}",binary_path=tmp,max_bytes=part["bytes"])
            if tmp.stat().st_size!=part["bytes"] or sha(tmp)!=part["sha256"]:
                raise GateError("native15b_transport_download_failed")
            with tmp.open("rb") as s: shutil.copyfileobj(s,out)
            tmp.unlink()
    if compressed.stat().st_size!=profile["data_asset_bytes"] or sha(compressed)!=profile["data_asset_sha256"]:
        raise GateError("native15b_archive_digest_failed")
    unpacked=root/"native15b-unpacked"; unpacked.mkdir()
    b=profile["bundle_member"]
    inv.unpack(compressed,unpacked,expected={b["name"]:{"bytes":b["bytes"],"sha256":b["sha256"]}})
    compressed.unlink()
    return unpacked/b["name"]

def extract(bundle:Path,inputs:Path)->dict:
    with tarfile.open(bundle,"r:") as t:
        members=[m for m in t.getmembers() if m.isfile()]
        if any(not safe(m.name) for m in members): raise GateError("native15b_invalid_member")
        by={m.name:m for m in members}
        if len(by)!=len(members): raise GateError("native15b_duplicate_member")
        manifest=by.get("BUNDLE_MANIFEST.json")
        if manifest is None or manifest.size>inv.MAX_MANIFEST_BYTES: raise GateError("native15b_bundle_manifest_missing")
        stream=t.extractfile(manifest); bundle_manifest=json.loads(stream.read(inv.MAX_MANIFEST_BYTES+1))
        files=bundle_manifest.get("files") if isinstance(bundle_manifest,dict) else None
        if not isinstance(files,dict): raise GateError("native15b_bundle_manifest_invalid")
        def one(suffix):
            names=[n for n in by if n==suffix or n.endswith("/"+suffix)]
            if len(names)!=1: raise GateError("native15b_member_not_unique:"+suffix)
            return names[0]
        carrier_name=one(CARRIER_SUFFIX); source_name=one(SOURCE_SUFFIX)
        expected=[
            (carrier_name,files.get(carrier_name),inputs/"15m_offset_5.parquet",CARRIER_BYTES,CARRIER_SHA256,MAX_CARRIER_BYTES),
            (source_name,files.get(source_name),inputs/"SOURCE_MANIFEST.json",SOURCE_BYTES,SOURCE_SHA256,inv.MAX_MANIFEST_BYTES),
        ]
        for name,meta,dest,exp_bytes,exp_sha,maxb in expected:
            if not isinstance(meta,dict) or set(meta)!={"bytes","sha256"}: raise GateError("native15b_manifest_identity_missing")
            if meta["bytes"]!=exp_bytes or meta["sha256"]!=exp_sha: raise GateError("native15b_frozen_identity_mismatch")
            m=by[name]
            if m.size!=exp_bytes or m.size>maxb: raise GateError("native15b_member_size_mismatch")
            st=t.extractfile(m); raw=st.read(m.size+1)
            if len(raw)!=m.size or hashlib.sha256(raw).hexdigest()!=exp_sha: raise GateError("native15b_member_digest_mismatch")
            dest.write_bytes(raw)
    return {"archive_path":carrier_name,"bytes":CARRIER_BYTES,"sha256":CARRIER_SHA256}

def prepare_inputs(api,root:Path,profile:dict):
    work=root/"work"; work.mkdir(); scripts=work/"native15b"; scripts.mkdir(); here=Path(__file__).resolve().parent
    for name in ("risk_v3_native15_descriptive_risk_map.py","risk_v3_native15_descriptive_risk_map_verifier.py"):
        src=here/name
        if not src.is_file() or src.is_symlink(): raise GateError("native15b_public_source_missing")
        shutil.copy2(src,scripts/name)
    inputs=work/"inputs"; inputs.mkdir()
    prereg=Path(__file__).resolve().parents[1]/"docs"/"research"/PREREG_NAME
    if not prereg.is_file() or prereg.is_symlink() or sha(prereg)!=PREREG_SHA256: raise GateError("native15b_prereg_identity_failed")
    shutil.copy2(prereg,inputs/"PREREG.json")
    parent=verify_parent(api); (inputs/"PHASE_A_PARENT.json").write_text(json.dumps(parent,indent=2,sort_keys=True)+"\n")
    bundle=stage_bundle(api,root); carrier=extract(bundle,inputs); bundle.unlink()
    ident={"schema_id":"risk_tool_v3_native15_phase_b_input_identity@1.0","task_id":TASK_ID,"prereg_sha256":PREREG_SHA256,"parent_phase_a":{"private_ref":PARENT_REF,"result_path":PARENT_RESULT_PATH,"result_git_blob_sha":PARENT_BLOB_SHA,"required_status":PARENT_STATUS},"carrier":carrier,"development_window":{"start":"2021-01-01","end":"2023-12-31","years":[2021,2022,2023],"symbol":"000852.SH"},"controls":{"repeat_audit_years_materialized":False,"fresh_year_materialized":False,"new_training":False,"production_authority":False}}
    (inputs/"DATA_IDENTITY.json").write_text(json.dumps(ident,indent=2,sort_keys=True)+"\n")
    return work

def main():
    p=argparse.ArgumentParser(); p.add_argument("phase",choices=["prepare","compute","cleanup","publish"]); p.add_argument("profile",nargs="?",default=PROFILE_NAME); a=p.parse_args(); require_context()
    if a.profile!=PROFILE_NAME: raise GateError("unknown_native15b_profile")
    os.umask(0o077); rb.prepare_inputs=prepare_inputs
    if a.phase=="prepare": rb.prepare(PROFILE_NAME,PROFILE)
    elif a.phase=="compute": rb.compute()
    elif a.phase=="cleanup": rb.cleanup()
    else: rb.publish(PROFILE)

def run():
    try: main()
    except GateError as e:
        print("Execution stopped: "+str(e),file=sys.stderr); raise SystemExit(1)
    except Exception:
        print("Execution failed; no private Native-15m row-level values were exposed publicly.",file=sys.stderr); raise

if __name__=="__main__": run()
