from __future__ import annotations
import argparse,base64,hashlib,importlib.util,os,re,shutil,sys,urllib.parse
from pathlib import Path
HERE=Path(__file__).resolve().parent
_s=importlib.util.spec_from_file_location('_rb_rel',HERE/'research_broker.py');rb=importlib.util.module_from_spec(_s);_s.loader.exec_module(rb);GateError=rb.GateError
PROFILE_NAME='risk-v2-15m-continuous-reliability-score-v1'
PRIVATE_REF='3879de41a5ac7c12246b811f51d16dc8586b9dae';PARENT_BRANCH='runs/public-research/34926868278-1';PARENT_PATH='research/public-runs/34926868278-1-results/TEMPORAL_METRICS_2W_V2.csv';PARENT_BLOB='478f73c1fb9ac9c91d670e67733623e1450da953';PARENT_BYTES=170908;PARENT_SHA256='455a0f0d61993a933016e111aa1386eaf4ddf3ec6aeb9e28c109f08a559fd060'
PROFILE={'private_ref':PRIVATE_REF,'manifest_sha256':'b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551','command':['reliability/risk_continuous_reliability_score_v1.py','--metrics','/work/inputs/TEMPORAL_METRICS_2W_V2.csv','--out','/results/study'],'verify_command':['reliability/risk_continuous_reliability_score_v1_verifier.py','--metrics','/work/inputs/TEMPORAL_METRICS_2W_V2.csv','--results','/results/study'],'command_timeout_seconds':120,'verification_timeout_seconds':120,'new_training':False,'production_authority':False}
rb.COMPUTE_HOST_TIMEOUT_SECONDS=150;rb.VALIDATE_HOST_TIMEOUT_SECONDS=150

def require_context():
    e=os.environ
    if e.get('GITHUB_ACTIONS')!='true' or e.get('GITHUB_REPOSITORY')!=rb.PUBLIC_REPO or e.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or e.get('GITHUB_REF')!='refs/heads/cloud-workspace-v1':raise GateError('not_approved_reliability_context')
    if not re.fullmatch(r'[0-9]+',e.get('GITHUB_RUN_ID','') or '') or not re.fullmatch(r'[0-9]+',e.get('GITHUB_RUN_ATTEMPT','') or ''):raise GateError('invalid_run_identity')
def prepare_inputs(api,root,profile):
    work=root/'work';work.mkdir();inputs=work/'inputs';inputs.mkdir();scripts=work/'reliability';scripts.mkdir()
    for name in ('risk_continuous_reliability_score_v1.py','risk_continuous_reliability_score_v1_verifier.py'):
        src=HERE/name
        if not src.is_file() or src.is_symlink():raise GateError('reliability_source_missing')
        shutil.copy2(src,scripts/name)
    ref=urllib.parse.quote(PARENT_BRANCH,safe='');item=api.request(f'repos/{rb.PRIVATE_REPO}/contents/{PARENT_PATH}?ref={ref}');raw=base64.b64decode(item.get('content','') or '')
    if item.get('sha')!=PARENT_BLOB or len(raw)!=PARENT_BYTES or hashlib.sha256(raw).hexdigest()!=PARENT_SHA256:raise GateError('reliability_parent_metrics_identity_failed')
    (inputs/'TEMPORAL_METRICS_2W_V2.csv').write_bytes(raw);return work
def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','compute','cleanup','publish']);p.add_argument('profile',nargs='?',default=PROFILE_NAME);a=p.parse_args();require_context()
    if a.profile!=PROFILE_NAME:raise GateError('unknown_reliability_profile')
    rb.prepare_inputs=prepare_inputs
    if a.phase=='prepare':rb.prepare(PROFILE_NAME,PROFILE)
    elif a.phase=='compute':rb.compute()
    elif a.phase=='cleanup':rb.cleanup()
    else:rb.publish(PROFILE)
def run():
    try:main()
    except GateError as e:print('Execution stopped: '+str(e),file=sys.stderr);raise SystemExit(1)
    except Exception:print('Execution failed; no private reliability content was exposed publicly.',file=sys.stderr);raise SystemExit(1)
if __name__=='__main__':run()
