"""Bounded broker for Risk Tool V3 Native-15m Phase-C1 state-machine candidate map."""
from __future__ import annotations
import argparse, base64, hashlib, json, os, re, shutil, sys, urllib.parse
from pathlib import Path
import research_broker as rb
import risk_v3_native15_descriptive_risk_map_broker as phaseb

GateError=rb.GateError
PROFILE_NAME="risk-v3-native15-state-machine-candidates-v1"
TASK_ID="CSI1000-RISK-V3-NATIVE15-PHASE-C1-STATE-MACHINE-CANDIDATES-V1-20260916"
PREREG_SHA256="ecee5f8fbb3bd070a4e2550b9b24078fd1e0d539a90a48db0cb1d613389d8750"
PREREG_NAME="RISK_TOOL_V3_NATIVE15_PHASE_C1_STATE_MACHINE_CANDIDATES_PREREG_20260916.json"
PRIVATE_REF="6f41091f1d29c5d6a3aaf74c49f538526c567eef"
PARENT_REF="runs/public-research/34986321499-1"
PARENT_RESULT_PATH="research/public-runs/34986321499-1-native15-phase-b.json"
PARENT_BLOB_SHA="3b3d6c42014fb733c565d4318e325648c2812ca8"
PARENT_STATUS="NATIVE15_DESCRIPTIVE_MAP_COMPLETE"
CARRIER_BYTES=1669752
CARRIER_SHA256="d69e87662d9e525396ed776b754ff43fca58dd021df4a84f96b60a6a5e4864d6"
Q95_BPS=50.315745148077
Q99_BPS=77.138740520039

PROFILE={
 "private_ref":PRIVATE_REF,
 "manifest_sha256":PREREG_SHA256,
 "command":["native15c1/risk_v3_native15_state_machine_candidates.py","--inputs","/work/inputs","--out","/results/study"],
 "verify_command":["native15c1/risk_v3_native15_state_machine_candidates_verifier.py","--inputs","/work/inputs","--results","/results/study"],
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
        raise GateError("not_approved_native15c1_context")
    if not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ID","")) or not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ATTEMPT","")):
        raise GateError("invalid_run_identity")

def verify_parent(api)->dict:
    route=f"repos/{rb.PRIVATE_REPO}/contents/{PARENT_RESULT_PATH}?ref={urllib.parse.quote(PARENT_REF,safe='')}"
    got=api.request(route)
    if got.get("sha")!=PARENT_BLOB_SHA: raise GateError("native15c1_parent_blob_mismatch")
    try:
        raw=base64.b64decode(got["content"]); v=json.loads(raw.decode())
    except Exception as e:
        raise GateError("native15c1_parent_decode_failed") from e
    if v.get("status")!=PARENT_STATUS or v.get("next_phase_authorized") is not True:
        raise GateError("native15c1_parent_not_authorized")
    carrier=v.get("carrier") or {}
    if carrier.get("bytes")!=CARRIER_BYTES or carrier.get("sha256")!=CARRIER_SHA256:
        raise GateError("native15c1_parent_carrier_mismatch")
    thresholds=((v.get("descriptive_map") or {}).get("frequency") or {}).get("pooled_abs_return_threshold_bps") or {}
    if float(thresholds.get("q95",-1))!=Q95_BPS or float(thresholds.get("q99",-1))!=Q99_BPS:
        raise GateError("native15c1_parent_threshold_mismatch")
    controls=v.get("controls") or {}
    if controls.get("use_2024_2025_market_values") is not False or controls.get("use_2026_market_values") is not False or controls.get("state_machine_installation") is not False or controls.get("production_authority") is not False:
        raise GateError("native15c1_parent_control_mismatch")
    return v

def prepare_inputs(api,root:Path,profile:dict):
    work=root/"work"; work.mkdir(); scripts=work/"native15c1"; scripts.mkdir(); here=Path(__file__).resolve().parent
    for name in ("risk_v3_native15_state_machine_candidates.py","risk_v3_native15_state_machine_candidates_verifier.py"):
        src=here/name
        if not src.is_file() or src.is_symlink(): raise GateError("native15c1_public_source_missing")
        shutil.copy2(src,scripts/name)
    inputs=work/"inputs"; inputs.mkdir()
    prereg=Path(__file__).resolve().parents[1]/"docs"/"research"/PREREG_NAME
    if not prereg.is_file() or prereg.is_symlink() or sha(prereg)!=PREREG_SHA256: raise GateError("native15c1_prereg_identity_failed")
    shutil.copy2(prereg,inputs/"PREREG.json")
    parent=verify_parent(api); (inputs/"PHASE_B_PARENT.json").write_text(json.dumps(parent,indent=2,sort_keys=True)+"\n")
    bundle=phaseb.stage_bundle(api,root); carrier=phaseb.extract(bundle,inputs); bundle.unlink()
    if carrier.get("bytes")!=CARRIER_BYTES or carrier.get("sha256")!=CARRIER_SHA256: raise GateError("native15c1_extracted_carrier_mismatch")
    ident={"schema_id":"risk_tool_v3_native15_phase_c1_input_identity@1.0","task_id":TASK_ID,"prereg_sha256":PREREG_SHA256,"parent_phase_b":{"private_ref":PARENT_REF,"result_path":PARENT_RESULT_PATH,"result_git_blob_sha":PARENT_BLOB_SHA,"required_status":PARENT_STATUS},"carrier":carrier,"development_window":{"start":"2021-01-01","end":"2023-12-31","years":[2021,2022,2023],"symbol":"000852.SH"},"controls":{"repeat_audit_years_materialized":False,"fresh_year_materialized":False,"new_training":False,"state_machine_installation":False,"production_authority":False}}
    (inputs/"DATA_IDENTITY.json").write_text(json.dumps(ident,indent=2,sort_keys=True)+"\n")
    return work

def main():
    p=argparse.ArgumentParser(); p.add_argument("phase",choices=["prepare","compute","cleanup","publish"]); p.add_argument("profile",nargs="?",default=PROFILE_NAME); a=p.parse_args(); require_context()
    if a.profile!=PROFILE_NAME: raise GateError("unknown_native15c1_profile")
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
