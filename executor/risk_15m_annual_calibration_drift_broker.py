from __future__ import annotations

import argparse
import base64
import importlib.util
import shutil
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location("_temporal_broker",HERE/"risk_temporal_stability_2015_2025_broker.py")
tb=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(tb)
rb=tb.rb;GateError=tb.GateError
PROFILE_NAME="risk-v2-15m-annual-calibration-drift-diagnostic-v1"
PARENT_RUN_REF="runs/public-research/34919074188-1"
PARENT_RECEIPT_PATH="research/public-runs/34919074188-1-results/INPUT_DATA_RECEIPT.json"
PARENT_RECEIPT_BLOB="329bfdc4c2b3bbd6dd5956963b125dc8233bb911"
PROFILE={
    "private_ref":tb.PRIVATE_REF,
    "manifest_sha256":tb.P1[6],
    "command":["diagnostic/risk_15m_annual_calibration_drift_diagnostic.py","--inputs","/work/inputs","--temporal-base","/work/temporal/risk_temporal_stability_2015_2025.py","--out","/results/study"],
    "verify_command":["diagnostic/risk_15m_annual_calibration_drift_verifier.py","--inputs","/work/inputs","--temporal-base","/work/temporal/risk_temporal_stability_2015_2025.py","--results","/results/study"],
    "command_timeout_seconds":900,
    "verification_timeout_seconds":900,
    "new_training":False,
    "production_authority":False,
}

def prepare_inputs(api,root:Path,profile:dict):
    work=tb.prepare_inputs(api,root,profile)
    diagnostic=work/"diagnostic";diagnostic.mkdir()
    for name in ("risk_15m_annual_calibration_drift_diagnostic.py","risk_15m_annual_calibration_drift_verifier.py"):
        src=HERE/name
        if not src.is_file() or src.is_symlink():raise GateError("calibration_drift_public_source_missing")
        shutil.copy2(src,diagnostic/name)
    response=api.request(f"repos/{rb.PRIVATE_REPO}/contents/{PARENT_RECEIPT_PATH}?ref={rb.urllib.parse.quote(PARENT_RUN_REF,safe='')}")
    raw=base64.b64decode(response.get("content","") or "")
    if response.get("sha")!=PARENT_RECEIPT_BLOB or tb.blobsha(raw)!=PARENT_RECEIPT_BLOB:raise GateError("parent_temporal_receipt_identity_failed")
    (work/"inputs"/"PARENT_INPUT_DATA_RECEIPT.json").write_bytes(raw)
    return work

def main():
    p=argparse.ArgumentParser();p.add_argument("phase",choices=["prepare","compute","cleanup","publish"]);p.add_argument("profile",nargs="?",default=PROFILE_NAME);a=p.parse_args()
    tb.require_context()
    if a.profile!=PROFILE_NAME:raise GateError("unknown_calibration_drift_profile")
    rb.prepare_inputs=prepare_inputs
    if a.phase=="prepare":rb.prepare(PROFILE_NAME,PROFILE)
    elif a.phase=="compute":rb.compute()
    elif a.phase=="cleanup":rb.cleanup()
    else:rb.publish(PROFILE)

def run():
    try:main()
    except GateError as error:print("Execution stopped: "+str(error),file=sys.stderr);raise SystemExit(1)
    except Exception:print("Execution failed; no private calibration-drift content was exposed publicly.",file=sys.stderr);raise SystemExit(1)
if __name__=="__main__":run()
