"""Fixed credential-free runtime; all research output remains in /results."""
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

COMMAND=['dual_gate/wave_dual_gate_study_v1.py','--inputs','/work/inputs','--out','/results/study']
VERIFY=['dual_gate/wave_dual_gate_verifier_v1.py','--inputs','/work/inputs','--results','/results/study']


def validate(profile):
    if profile.get('command')!=COMMAND or profile.get('verify_command')!=VERIFY:
        raise ValueError('unapproved commands')
    if profile.get('new_training') is not True or profile.get('production_authority') is not False:
        raise ValueError('incorrect research scope')
    if profile.get('command_timeout_seconds')!=900 or profile.get('verification_timeout_seconds')!=900:
        raise ValueError('unapproved timeout')


def main():
    if any(any(k in name.upper() for k in ('TOKEN','SECRET','PASSWORD','PRIVATE_KEY')) for name in os.environ):
        raise ValueError('credential environment reached compute')
    if [n for _,n in socket.if_nameindex()]!=['lo']:raise ValueError('network not isolated')
    profile=json.loads(Path('/execution/profile.json').read_text());validate(profile)
    if sys.argv[1:]==['validate-research']:
        result=subprocess.run([sys.executable,*VERIFY],cwd='/work',capture_output=True,timeout=900,check=False)
        sys.stdout.buffer.write(result.stdout);sys.stderr.buffer.write(result.stderr);raise SystemExit(result.returncode)
    if sys.argv[1:]:raise ValueError('unapproved mode')
    with Path('/results/compute.log').open('xb') as log:
        try:code=subprocess.run([sys.executable,*COMMAND],cwd='/work',stdout=log,stderr=subprocess.STDOUT,timeout=900,check=False).returncode
        except subprocess.TimeoutExpired:code=124
    Path('/results/compute_receipt.json').write_text(json.dumps(dict(status='passed' if code==0 else 'failed',exit_code=code,new_training=True,production_authority=False))+'\n')
    raise SystemExit(0 if code==0 else 1)


if __name__=='__main__':main()
