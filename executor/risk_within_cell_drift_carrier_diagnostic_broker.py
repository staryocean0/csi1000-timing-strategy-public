from __future__ import annotations
import argparse,base64,hashlib,importlib.util,os,re,shutil,sys,urllib.parse
from pathlib import Path
HERE=Path(__file__).resolve().parent
_s=importlib.util.spec_from_file_location("_rb_carrier",HERE/"research_broker.py");rb=importlib.util.module_from_spec(_s);_s.loader.exec_module(rb);GateError=rb.GateError
_p=importlib.util.spec_from_file_location("_state_parent",HERE/"risk_state_conditional_calibration_diagnostic_broker.py");state=importlib.util.module_from_spec(_p);_p.loader.exec_module(state)
PROFILE_NAME="risk-v2-15m-within-cell-drift-carrier-diagnostic-v1"
PARENT_BRANCH="runs/public-research/34935354211-1"
SUMMARY_PATH="research/public-runs/34935354211-1-results/SUMMARY.json";SUMMARY_BYTES=2167;SUMMARY_SHA="534892118a09008657c3a742ffd6c22f285a851f1bf1763eefb0a58536169777"
GROUP_PATH="research/public-runs/34935354211-1-results/STATE_GROUP_SUMMARY.csv";GROUP_BYTES=7524;GROUP_SHA="a091876a8e0065af595a64f975fefe99eb9dbb3ff8f8eab41e6b0369bf903f35"
PROFILE={"private_ref":state.PROFILE["private_ref"],"manifest_sha256":state.PROFILE["manifest_sha256"],"command":["carrier_diag/risk_within_cell_drift_carrier_diagnostic.py","--inputs","/work/inputs","--out","/results/study"],"verify_command":["carrier_diag/risk_within_cell_drift_carrier_diagnostic_verifier.py","--inputs","/work/inputs","--results","/results/study"],"command_timeout_seconds":900,"verification_timeout_seconds":900,"new_training":False,"production_authority":False}
rb.COMPUTE_HOST_TIMEOUT_SECONDS=930;rb.VALIDATE_HOST_TIMEOUT_SECONDS=930

def require_context():
    e=os.environ
    if e.get("GITHUB_ACTIONS")!="true" or e.get("GITHUB_REPOSITORY")!=rb.PUBLIC_REPO or e.get("GITHUB_EVENT_NAME")!="workflow_dispatch" or e.get("GITHUB_REF")!="refs/heads/cloud-workspace-v1":raise GateError("not_approved_within_cell_carrier_context")
    if not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ID","") or "") or not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ATTEMPT","") or ""):raise GateError("invalid_run_identity")

def fetch_exact(api,path,size,digest):
    ref=urllib.parse.quote(PARENT_BRANCH,safe="");item=api.request(f"repos/{rb.PRIVATE_REPO}/contents/{path}?ref={ref}");raw=base64.b64decode(item.get("content","") or "")
    if len(raw)!=size or hashlib.sha256(raw).hexdigest()!=digest:raise GateError("within_cell_carrier_parent_identity_failed")
    return raw

def prepare_inputs(api,root,profile):
    work=state.prepare_inputs(api,root,profile);inputs=work/"inputs";scripts=work/"carrier_diag";scripts.mkdir()
    for name in ("risk_within_cell_drift_carrier_diagnostic.py","risk_within_cell_drift_carrier_diagnostic_verifier.py"):
        src=HERE/name
        if not src.is_file() or src.is_symlink():raise GateError("within_cell_carrier_source_missing")
        shutil.copy2(src,scripts/name)
    (inputs/"PARENT_STATE_SUMMARY.json").write_bytes(fetch_exact(api,SUMMARY_PATH,SUMMARY_BYTES,SUMMARY_SHA));(inputs/"PARENT_STATE_GROUP_SUMMARY.csv").write_bytes(fetch_exact(api,GROUP_PATH,GROUP_BYTES,GROUP_SHA))
    return work

def main():
    p=argparse.ArgumentParser();p.add_argument("phase",choices=["prepare","compute","cleanup","publish"]);p.add_argument("profile",nargs="?",default=PROFILE_NAME);a=p.parse_args();require_context()
    if a.profile!=PROFILE_NAME:raise GateError("unknown_within_cell_carrier_profile")
    rb.prepare_inputs=prepare_inputs
    if a.phase=="prepare":rb.prepare(PROFILE_NAME,PROFILE)
    elif a.phase=="compute":rb.compute()
    elif a.phase=="cleanup":rb.cleanup()
    else:rb.publish(PROFILE)

def run():
    try:main()
    except GateError as e:print("Execution stopped: "+str(e),file=sys.stderr);raise SystemExit(1)
    except Exception:print("Execution failed; no private within-cell carrier diagnostic content was exposed publicly.",file=sys.stderr);raise SystemExit(1)
if __name__=="__main__":run()
