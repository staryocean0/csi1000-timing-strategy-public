"""Bounded broker for Risk Tool V3 Native-15m Phase-A carrier/semantic audit."""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, sys, tarfile
from pathlib import Path, PurePosixPath
import research_broker as rb
import risk_phase1b_carrier_inventory_core_v1 as inv

GateError=rb.GateError
PROFILE_NAME="risk-v3-native15-carrier-semantic-audit-v1"
TASK_ID="CSI1000-RISK-V3-NATIVE15-PHASE-A-CARRIER-SEMANTIC-AUDIT-V1-20260915"
PREREG_SHA256="d8bd50b694256379a07289c1f4587b3428cc36ba9d0e285bde2aa97fc0c8cd09"
PREREG_NAME="RISK_TOOL_V3_NATIVE15_PHASE_A_PREREG_20260915.json"
PRIVATE_REF="6f41091f1d29c5d6a3aaf74c49f538526c567eef"
CARRIER_SUFFIX="data/index/15m_offset_5.parquet"
SOURCE_SUFFIX="data/index/SOURCE_MANIFEST.json"
MAX_CARRIER_BYTES=64*1024*1024

PROFILE={
 "private_ref":PRIVATE_REF,
 "manifest_sha256":PREREG_SHA256,
 "command":["native15/risk_v3_native15_carrier_semantic_audit.py","--inputs","/work/inputs","--out","/results/study"],
 "verify_command":["native15/risk_v3_native15_carrier_semantic_audit_verifier.py","--inputs","/work/inputs","--results","/results/study"],
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
        raise GateError("not_approved_native15_context")
    if not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ID","")) or not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ATTEMPT","")):
        raise GateError("invalid_run_identity")

def safe(name:str)->bool:
    p=PurePosixPath(name)
    return bool(p.parts) and not p.is_absolute() and ".." not in p.parts and "\\" not in name

def stage_bundle(api,root:Path):
    profile=inv.load_profile()
    release=api.request(f"repos/{rb.PRIVATE_REPO}/releases/tags/{profile['data_release_tag']}")
    assets={x["name"]:x for x in release.get("assets") or []}
    compressed=root/profile["data_asset_name"]
    with compressed.open("xb") as out:
        for i,part in enumerate(profile["asset_parts"]):
            asset=assets.get(part["name"])
            if not asset or asset.get("state")!="uploaded" or asset.get("size")!=part["bytes"] or asset.get("digest")!="sha256:"+part["sha256"]:
                raise GateError("native15_transport_identity_failed")
            tmp=root/f"native15-part-{i:03d}.bin"
            api.request(f"repos/{rb.PRIVATE_REPO}/releases/assets/{asset['id']}",binary_path=tmp,max_bytes=part["bytes"])
            if tmp.stat().st_size!=part["bytes"] or sha(tmp)!=part["sha256"]:
                raise GateError("native15_transport_download_failed")
            with tmp.open("rb") as s: shutil.copyfileobj(s,out)
            tmp.unlink()
    if compressed.stat().st_size!=profile["data_asset_bytes"] or sha(compressed)!=profile["data_asset_sha256"]:
        raise GateError("native15_archive_digest_failed")
    unpacked=root/"native15-unpacked"; unpacked.mkdir()
    b=profile["bundle_member"]
    inv.unpack(compressed,unpacked,expected={b["name"]:{"bytes":b["bytes"],"sha256":b["sha256"]}})
    compressed.unlink()
    return unpacked/b["name"],profile

def extract(bundle:Path,inputs:Path)->dict:
    with tarfile.open(bundle,"r:") as t:
        members=[m for m in t.getmembers() if m.isfile()]
        if any(not safe(m.name) for m in members): raise GateError("native15_invalid_member")
        by={m.name:m for m in members}
        if len(by)!=len(members): raise GateError("native15_duplicate_member")
        manifest=by.get("BUNDLE_MANIFEST.json")
        if manifest is None or manifest.size>inv.MAX_MANIFEST_BYTES: raise GateError("native15_bundle_manifest_missing")
        ms=t.extractfile(manifest)
        bundle_manifest=json.loads(ms.read(inv.MAX_MANIFEST_BYTES+1))
        files=bundle_manifest.get("files") if isinstance(bundle_manifest,dict) else None
        if not isinstance(files,dict): raise GateError("native15_bundle_manifest_invalid")

        def one(suffix):
            names=[n for n in by if n==suffix or n.endswith("/"+suffix)]
            if len(names)!=1: raise GateError("native15_member_not_unique:"+suffix)
            return names[0]

        carrier_name=one(CARRIER_SUFFIX); source_name=one(SOURCE_SUFFIX)
        carrier_meta=files.get(carrier_name); source_meta=files.get(source_name)
        if not isinstance(carrier_meta,dict) or set(carrier_meta)!={"bytes","sha256"}: raise GateError("native15_carrier_manifest_identity_missing")
        if not isinstance(source_meta,dict) or set(source_meta)!={"bytes","sha256"}: raise GateError("native15_source_manifest_identity_missing")
        if not (0<int(carrier_meta["bytes"])<=MAX_CARRIER_BYTES): raise GateError("native15_carrier_size_invalid")

        for name,meta,dest,maxb in [
            (carrier_name,carrier_meta,inputs/"15m_offset_5.parquet",MAX_CARRIER_BYTES),
            (source_name,source_meta,inputs/"SOURCE_MANIFEST.json",inv.MAX_MANIFEST_BYTES),
        ]:
            m=by[name]
            if m.size!=meta["bytes"] or m.size>maxb: raise GateError("native15_member_size_mismatch")
            st=t.extractfile(m)
            raw=st.read(m.size+1)
            if len(raw)!=m.size or hashlib.sha256(raw).hexdigest()!=meta["sha256"]:
                raise GateError("native15_member_digest_mismatch")
            dest.write_bytes(raw)

    return {
      "schema_id":"risk_tool_v3_native15_input_identity@1.0",
      "task_id":TASK_ID,
      "prereg_sha256":PREREG_SHA256,
      "carrier":{"archive_path":carrier_name,"bytes":carrier_meta["bytes"],"sha256":carrier_meta["sha256"]},
      "source_contract":{"archive_path":source_name,"bytes":source_meta["bytes"],"sha256":source_meta["sha256"]},
      "controls":{"market_values_read_in_prepare":False,"parquet_deserialization_in_prepare":False,"new_training":False,"production_authority":False},
    }

def prepare_inputs(api,root:Path,profile:dict):
    work=root/"work"; work.mkdir()
    scripts=work/"native15"; scripts.mkdir()
    here=Path(__file__).resolve().parent
    for name in ("risk_v3_native15_carrier_semantic_audit.py","risk_v3_native15_carrier_semantic_audit_verifier.py"):
        src=here/name
        if not src.is_file() or src.is_symlink(): raise GateError("native15_public_source_missing")
        shutil.copy2(src,scripts/name)
    inputs=work/"inputs"; inputs.mkdir()
    prereg=Path(__file__).resolve().parents[1]/"docs"/"research"/PREREG_NAME
    if not prereg.is_file() or prereg.is_symlink() or sha(prereg)!=PREREG_SHA256: raise GateError("native15_prereg_identity_failed")
    shutil.copy2(prereg,inputs/"PREREG.json")
    bundle,_=stage_bundle(api,root)
    ident=extract(bundle,inputs)
    (inputs/"DATA_IDENTITY.json").write_text(json.dumps(ident,indent=2,sort_keys=True)+"\n")
    bundle.unlink()
    return work

def main():
    p=argparse.ArgumentParser(); p.add_argument("phase",choices=["prepare","compute","cleanup","publish"]); p.add_argument("profile",nargs="?",default=PROFILE_NAME)
    a=p.parse_args(); require_context()
    if a.profile!=PROFILE_NAME: raise GateError("unknown_native15_profile")
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
        print("Execution failed; no private native15 market values were exposed publicly.",file=sys.stderr); raise

if __name__=="__main__": run()
