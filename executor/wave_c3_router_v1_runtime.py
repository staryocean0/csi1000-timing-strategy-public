"""Credential-free isolated runtime for C3/router v1."""
import json,os,socket,subprocess,sys
from pathlib import Path
COMMAND=['c3_router/wave_c3_router_v1_entry.py','--inputs','/work/inputs','--out','/results/study']
VERIFY=['c3_router/wave_c3_router_v1_verifier.py','--inputs','/work/inputs','--results','/results/study']

def validate(profile):
    if profile.get('command')!=COMMAND or profile.get('verify_command')!=VERIFY:raise ValueError('command drift')
    if profile.get('new_training') is not True or profile.get('production_authority') is not False:raise ValueError('scope drift')
    if profile.get('command_timeout_seconds')!=900 or profile.get('verification_timeout_seconds')!=900:raise ValueError('timeout drift')

def main():
    if any(any(k in name.upper() for k in ('TOKEN','SECRET','PASSWORD','PRIVATE_KEY')) for name in os.environ):raise ValueError('credential environment reached compute')
    if [n for _,n in socket.if_nameindex()]!=['lo']:raise ValueError('network not isolated')
    profile=json.loads(Path('/execution/profile.json').read_text());validate(profile)
    if sys.argv[1:]==['validate-research']:
        r=subprocess.run([sys.executable,*VERIFY],cwd='/work',capture_output=True,timeout=900,check=False);sys.stdout.buffer.write(r.stdout);sys.stderr.buffer.write(r.stderr);raise SystemExit(r.returncode)
    if sys.argv[1:]:raise ValueError('unapproved mode')
    with Path('/results/compute.log').open('xb') as log:
        try:code=subprocess.run([sys.executable,*COMMAND],cwd='/work',stdout=log,stderr=subprocess.STDOUT,timeout=900,check=False).returncode
        except subprocess.TimeoutExpired:code=124
    Path('/results/compute_receipt.json').write_text(json.dumps({'status':'passed' if code==0 else 'failed','exit_code':code,'new_training':True,'production_authority':False})+'\n')
    raise SystemExit(0 if code==0 else 1)
if __name__=='__main__':main()
