from __future__ import annotations
import argparse,importlib.util,os,re,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
_s=importlib.util.spec_from_file_location('_rb_online',HERE/'research_broker.py');rb=importlib.util.module_from_spec(_s);_s.loader.exec_module(rb);GateError=rb.GateError
_p=importlib.util.spec_from_file_location('_parent_state',HERE/'risk_state_conditional_calibration_diagnostic_broker.py');parent=importlib.util.module_from_spec(_p);_p.loader.exec_module(parent)
PROFILE_NAME='risk-v2-15m-online-prior-calibration-v3'
PROFILE={'private_ref':parent.PROFILE['private_ref'],'manifest_sha256':parent.PROFILE['manifest_sha256'],'command':['online_cal/risk_online_prior_calibration_v3.py','--inputs','/work/inputs','--out','/results/study'],'verify_command':['online_cal/risk_online_prior_calibration_v3_verifier.py','--inputs','/work/inputs','--results','/results/study'],'command_timeout_seconds':900,'verification_timeout_seconds':900,'new_training':False,'production_authority':False}
rb.COMPUTE_HOST_TIMEOUT_SECONDS=930;rb.VALIDATE_HOST_TIMEOUT_SECONDS=930

def require_context():
    e=os.environ
    if e.get('GITHUB_ACTIONS')!='true' or e.get('GITHUB_REPOSITORY')!=rb.PUBLIC_REPO or e.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or e.get('GITHUB_REF')!='refs/heads/cloud-workspace-v1': raise GateError('not_approved_online_prior_context')
    if not re.fullmatch(r'[0-9]+',e.get('GITHUB_RUN_ID','') or '') or not re.fullmatch(r'[0-9]+',e.get('GITHUB_RUN_ATTEMPT','') or ''): raise GateError('invalid_run_identity')

def prepare_inputs(api,root,profile):
    work=parent.prepare_inputs(api,root,profile);inputs=work/'inputs';scripts=work/'online_cal';scripts.mkdir()
    for name in ('risk_online_prior_calibration_v3.py','risk_online_prior_calibration_v3_verifier.py'):
        src=HERE/name
        if not src.is_file() or src.is_symlink(): raise GateError('online_prior_source_missing')
        shutil.copy2(src,scripts/name)
    for name in ('risk_temporal_stability_hierarchical_v3_acceptance.py','risk_temporal_stability_acceptance.py','risk_temporal_stability_hierarchical_acceptance.py'):
        src=HERE/name
        if not src.is_file() or src.is_symlink(): raise GateError('online_prior_acceptance_source_missing')
        shutil.copy2(src,inputs/name)
    return work

def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','compute','cleanup','publish']);p.add_argument('profile',nargs='?',default=PROFILE_NAME);a=p.parse_args();require_context()
    if a.profile!=PROFILE_NAME: raise GateError('unknown_online_prior_profile')
    rb.prepare_inputs=prepare_inputs
    if a.phase=='prepare': rb.prepare(PROFILE_NAME,PROFILE)
    elif a.phase=='compute': rb.compute()
    elif a.phase=='cleanup': rb.cleanup()
    else: rb.publish(PROFILE)

def run():
    try: main()
    except GateError as e: print('Execution stopped: '+str(e),file=sys.stderr);raise SystemExit(1)
    except Exception: print('Execution failed; no private online-prior calibration content was exposed publicly.',file=sys.stderr);raise SystemExit(1)
if __name__=='__main__':run()
