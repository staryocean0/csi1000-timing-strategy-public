from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location("_research_broker",HERE/"research_broker.py");rb=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(rb);GateError=rb.GateError
_tspec=importlib.util.spec_from_file_location("_temporal_broker",HERE/"risk_temporal_stability_2015_2025_broker.py");tb=importlib.util.module_from_spec(_tspec);_tspec.loader.exec_module(tb)
PROFILE_NAME="risk-v2-15m-annual-calibration-diagnostic-v1"
PROFILE={"private_ref":tb.PRIVATE_REF,"manifest_sha256":tb.P1[6],"command":["diagnostic/risk_annual_calibration_diagnostic.py","--inputs","/work/inputs","--out","/results/study"],"verify_command":["diagnostic/risk_annual_calibration_diagnostic_verifier.py","--inputs","/work/inputs","--results","/results/study"],"command_timeout_seconds":300,"verification_timeout_seconds":300,"new_training":False,"production_authority":False}
rb.COMPUTE_HOST_TIMEOUT_SECONDS=330;rb.VALIDATE_HOST_TIMEOUT_SECONDS=330

def require_context():
    e=os.environ
    if e.get("GITHUB_ACTIONS")!="true" or e.get("GITHUB_REPOSITORY")!=rb.PUBLIC_REPO or e.get("GITHUB_EVENT_NAME")!="workflow_dispatch" or e.get("GITHUB_REF")!="refs/heads/cloud-workspace-v1":raise GateError("not_approved_annual_calibration_context")
    if not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ID","") or "") or not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ATTEMPT","") or ""):raise GateError("invalid_run_identity")

def prepare_inputs(api,root:Path,profile:dict):
    work=tb.prepare_inputs(api,root,profile);inputs=work/"inputs";diagnostic=work/"diagnostic";diagnostic.mkdir()
    shutil.copy2(HERE/"risk_temporal_stability_2015_2025.py",inputs/"temporal_base.py")
    for name in ("risk_annual_calibration_diagnostic.py","risk_annual_calibration_diagnostic_verifier.py"):
        source=HERE/name
        if not source.is_file() or source.is_symlink():raise GateError("annual_calibration_source_missing")
        shutil.copy2(source,diagnostic/name)
    return work

def main():
    ap=argparse.ArgumentParser();ap.add_argument("phase",choices=["prepare","compute","cleanup","publish"]);ap.add_argument("profile",nargs="?",default=PROFILE_NAME);a=ap.parse_args();require_context()
    if a.profile!=PROFILE_NAME:raise GateError("unknown_annual_calibration_profile")
    rb.prepare_inputs=prepare_inputs
    if a.phase=="prepare":rb.prepare(PROFILE_NAME,PROFILE)
    elif a.phase=="compute":rb.compute()
    elif a.phase=="cleanup":rb.cleanup()
    else:rb.publish(PROFILE)

def run():
    try:main()
    except GateError as error:print("Execution stopped: "+str(error),file=sys.stderr);raise SystemExit(1)
    except Exception:print("Execution failed; no private annual-calibration content was exposed publicly.",file=sys.stderr);raise SystemExit(1)
if __name__=="__main__":run()
