from __future__ import annotations
import argparse,base64,hashlib,importlib.util,os,re,shutil,sys,urllib.parse
from pathlib import Path
HERE=Path(__file__).resolve().parent
_s=importlib.util.spec_from_file_location("_rb_state",HERE/"research_broker.py");rb=importlib.util.module_from_spec(_s);_s.loader.exec_module(rb);GateError=rb.GateError
_c=importlib.util.spec_from_file_location("_cal_parent",HERE/"risk_weekly_calibration_streak_diagnostic_broker.py");cal=importlib.util.module_from_spec(_c);_c.loader.exec_module(cal)
PROFILE_NAME="risk-v2-15m-state-conditional-calibration-diagnostic-v1"
PARENT_BRANCH="runs/public-research/34932495109-1"
SUMMARY_PATH="research/public-runs/34932495109-1-results/SUMMARY.json";SUMMARY_BLOB="ba8be4a8655283eda1e0534d3d26770b2662a3e9";SUMMARY_BYTES=1243;SUMMARY_SHA="80e1a57e2d4585421ae1be434272a62b9489563503a1cb3009b2040c62990b42"
STREAK_PATH="research/public-runs/34932495109-1-results/LONGEST_CALIBRATION_STREAK.csv";STREAK_BLOB="12106d5440fd6869ffa5c8a31a51766380bc0f76";STREAK_BYTES=1219;STREAK_SHA="a4e19559dd3f9a03ca97887209cc2974db1fc96981a83de441232a15c55b44d6"
PROFILE={"private_ref":cal.PROFILE["private_ref"],"manifest_sha256":cal.PROFILE["manifest_sha256"],"command":["state_diag/risk_state_conditional_calibration_diagnostic.py","--inputs","/work/inputs","--out","/results/study"],"verify_command":["state_diag/risk_state_conditional_calibration_diagnostic_verifier.py","--inputs","/work/inputs","--results","/results/study"],"command_timeout_seconds":900,"verification_timeout_seconds":900,"new_training":False,"production_authority":False}
rb.COMPUTE_HOST_TIMEOUT_SECONDS=930;rb.VALIDATE_HOST_TIMEOUT_SECONDS=930

def require_context():
    e=os.environ
    if e.get("GITHUB_ACTIONS")!="true" or e.get("GITHUB_REPOSITORY")!=rb.PUBLIC_REPO or e.get("GITHUB_EVENT_NAME")!="workflow_dispatch" or e.get("GITHUB_REF")!="refs/heads/cloud-workspace-v1":raise GateError("not_approved_state_conditional_context")
    if not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ID","") or "") or not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ATTEMPT","") or ""):raise GateError("invalid_run_identity")

def fetch_exact(api,path,blob,size,digest):
    ref=urllib.parse.quote(PARENT_BRANCH,safe="");item=api.request(f"repos/{rb.PRIVATE_REPO}/contents/{path}?ref={ref}");raw=base64.b64decode(item.get("content","") or "")
    if item.get("sha")!=blob or len(raw)!=size or hashlib.sha256(raw).hexdigest()!=digest:raise GateError("state_conditional_parent_identity_failed")
    return raw

def prepare_inputs(api,root,profile):
    work=cal.prepare_inputs(api,root,profile);inputs=work/"inputs";scripts=work/"state_diag";scripts.mkdir()
    for name in ("risk_state_conditional_calibration_diagnostic.py","risk_state_conditional_calibration_diagnostic_verifier.py"):
        src=HERE/name
        if not src.is_file() or src.is_symlink():raise GateError("state_conditional_source_missing")
        shutil.copy2(src,scripts/name)
    (inputs/"PARENT_DIAGNOSTIC_SUMMARY.json").write_bytes(fetch_exact(api,SUMMARY_PATH,SUMMARY_BLOB,SUMMARY_BYTES,SUMMARY_SHA));(inputs/"PARENT_LONGEST_CALIBRATION_STREAK.csv").write_bytes(fetch_exact(api,STREAK_PATH,STREAK_BLOB,STREAK_BYTES,STREAK_SHA))
    return work

def main():
    p=argparse.ArgumentParser();p.add_argument("phase",choices=["prepare","compute","cleanup","publish"]);p.add_argument("profile",nargs="?",default=PROFILE_NAME);a=p.parse_args();require_context()
    if a.profile!=PROFILE_NAME:raise GateError("unknown_state_conditional_profile")
    rb.prepare_inputs=prepare_inputs
    if a.phase=="prepare":rb.prepare(PROFILE_NAME,PROFILE)
    elif a.phase=="compute":rb.compute()
    elif a.phase=="cleanup":rb.cleanup()
    else:rb.publish(PROFILE)

def run():
    try:main()
    except GateError as e:print("Execution stopped: "+str(e),file=sys.stderr);raise SystemExit(1)
    except Exception:print("Execution failed; no private state-conditional diagnostic content was exposed publicly.",file=sys.stderr);raise SystemExit(1)
if __name__=="__main__":run()
