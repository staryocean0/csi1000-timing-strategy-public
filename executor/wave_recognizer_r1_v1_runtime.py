"""Credential-free isolated runtime for recognizer R1 study."""
import json,os,socket,subprocess,sys
from pathlib import Path
COMMAND=['recognizer_r1/wave_recognizer_r1_v1_entry.py','--inputs','/work/inputs','--out','/results/study']
VERIFY=['recognizer_r1/wave_recognizer_r1_v1_verifier.py','--inputs','/work/inputs','--results','/results/study']
def validate(p):
 if p.get('command')!=COMMAND or p.get('verify_command')!=VERIFY or p.get('new_training') is not False or p.get('production_authority') is not False:raise ValueError('scope drift')
 if p.get('command_timeout_seconds')!=900 or p.get('verification_timeout_seconds')!=900:raise ValueError('timeout drift')
def main():
 if any(any(k in n.upper() for k in ('TOKEN','SECRET','PASSWORD','PRIVATE_KEY')) for n in os.environ):raise ValueError('credential leak')
 if [n for _,n in socket.if_nameindex()]!=['lo']:raise ValueError('network not isolated')
 p=json.loads(Path('/execution/profile.json').read_text());validate(p)
 if sys.argv[1:]==['validate-research']:
  r=subprocess.run([sys.executable,*VERIFY],cwd='/work',capture_output=True,timeout=900);sys.stdout.buffer.write(r.stdout);sys.stderr.buffer.write(r.stderr);raise SystemExit(r.returncode)
 if sys.argv[1:]:raise ValueError('mode')
 with Path('/results/compute.log').open('xb') as log:
  try:c=subprocess.run([sys.executable,*COMMAND],cwd='/work',stdout=log,stderr=subprocess.STDOUT,timeout=900).returncode
  except subprocess.TimeoutExpired:c=124
 Path('/results/compute_receipt.json').write_text(json.dumps({'status':'passed' if c==0 else 'failed','exit_code':c,'new_training':False,'production_authority':False})+'\n');raise SystemExit(0 if c==0 else 1)
if __name__=='__main__':main()
