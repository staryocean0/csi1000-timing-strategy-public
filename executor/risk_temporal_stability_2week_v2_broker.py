from __future__ import annotations
import argparse,importlib.util,os,re,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location("_rb",HERE/"research_broker.py");rb=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(rb);GateError=rb.GateError
_tspec=importlib.util.spec_from_file_location("_tb",HERE/"risk_temporal_stability_2015_2025_broker.py");tb=importlib.util.module_from_spec(_tspec);_tspec.loader.exec_module(tb)
PROFILE_NAME="risk-v2-temporal-stability-2week-v2"
PROFILE={"private_ref":tb.PRIVATE_REF,"manifest_sha256":tb.P1[6],"command":["temporal2/risk_temporal_stability_2week_v2.py","--inputs","/work/inputs","--out","/results/study"],"verify_command":["temporal2/risk_temporal_stability_2week_v2_verifier.py","--inputs","/work/inputs","--results","/results/study"],"command_timeout_seconds":900,"verification_timeout_seconds":900,"new_training":False,"production_authority":False}
rb.COMPUTE_HOST_TIMEOUT_SECONDS=930;rb.VALIDATE_HOST_TIMEOUT_SECONDS=930

def require_context():
    e=os.environ
    if e.get("GITHUB_ACTIONS")!="true" or e.get("GITHUB_REPOSITORY")!=rb.PUBLIC_REPO or e.get("GITHUB_EVENT_NAME")!="workflow_dispatch" or e.get("GITHUB_REF")!="refs/heads/cloud-workspace-v1":raise GateError("not_approved_2week_temporal_context")
    if not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ID","") or "") or not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ATTEMPT","") or ""):raise GateError("invalid_run_identity")

def prepare_inputs(api,root:Path,profile:dict):
    work=tb.prepare_inputs(api,root,profile);inputs=work/"inputs";scripts=work/"temporal2";scripts.mkdir()
    for name in ("risk_temporal_stability_2week_v2.py","risk_temporal_stability_2week_v2_verifier.py"):
        src=HERE/name
        if not src.is_file() or src.is_symlink():raise GateError("2week_source_missing")
        shutil.copy2(src,scripts/name)
    shutil.copy2(HERE/"risk_temporal_stability_2015_2025.py",inputs/"temporal_base.py")
    profile_src=HERE.parent/"docs/acceptance/risk_tool_v2/temporal_stability_profile_hierarchical_v2.json"
    if not profile_src.is_file() or profile_src.is_symlink():raise GateError("2week_profile_missing")
    shutil.copy2(profile_src,inputs/"TEMPORAL_PROFILE.json")
    return work

def main():
    p=argparse.ArgumentParser();p.add_argument("phase",choices=["prepare","compute","cleanup","publish"]);p.add_argument("profile",nargs="?",default=PROFILE_NAME);a=p.parse_args();require_context()
    if a.profile!=PROFILE_NAME:raise GateError("unknown_2week_temporal_profile")
    rb.prepare_inputs=prepare_inputs
    if a.phase=="prepare":rb.prepare(PROFILE_NAME,PROFILE)
    elif a.phase=="compute":rb.compute()
    elif a.phase=="cleanup":rb.cleanup()
    else:rb.publish(PROFILE)

def run():
    try:main()
    except GateError as e:print("Execution stopped: "+str(e),file=sys.stderr);raise SystemExit(1)
    except Exception:print("Execution failed; no private 2-week temporal content was exposed publicly.",file=sys.stderr);raise SystemExit(1)
if __name__=="__main__":run()
