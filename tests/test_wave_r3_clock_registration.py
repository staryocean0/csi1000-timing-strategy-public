"""Exact standard #345 registration tests; no live workflow or market execution."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml
from r3_clock_registration_support import PROFILE,BROKER,strip_audit_workflow,strip_audit_controller
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
import wave_r3_clock_broker_v1 as broker
import wave_r3_clock_runtime_v1 as runtime
PARENT_WORKFLOW='272605913b5df2094d8c3ed6eb4180729104e90b'
PARENT_CONTROLLER='5d0408e404fbefa4b2d460f2cfb58802fb5de31e'

def blob(raw):
    if isinstance(raw,str):raw=raw.encode()
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

class RegistrationTests(unittest.TestCase):
    def workflow(self):
        return yaml.load((ROOT/'.github/workflows/public-compute.yml').read_text(),Loader=yaml.BaseLoader)

    def test_workflow_exact_append_only(self):
        text=(ROOT/'.github/workflows/public-compute.yml').read_text()
        self.assertEqual(blob(strip_audit_workflow(text)),PARENT_WORKFLOW)
        doc=self.workflow();self.assertEqual(set(doc['on']),{'workflow_dispatch'})
        self.assertEqual(doc['on']['workflow_dispatch']['inputs']['profile']['options'].count(PROFILE),1)

    def test_controller_exact_append_only(self):
        text=(ROOT/'.github/workflows/controller-dispatch.yml').read_text()
        self.assertEqual(blob(strip_audit_controller(text)),PARENT_CONTROLLER)
        self.assertNotIn('FACTORLAB_PRIVATE_TOKEN',text)
        self.assertEqual(text.count('actions/workflows/public-compute.yml/dispatches'),1)

    def test_credentials_only_existing_prepare_and_publish(self):
        text=(ROOT/'.github/workflows/public-compute.yml').read_text()
        self.assertEqual(text.count('secrets.FACTORLAB_PRIVATE_TOKEN'),2)
        steps=[s for s in self.workflow()['jobs']['execute']['steps'] if BROKER in s.get('run','')]
        self.assertEqual(len(steps),4)
        for s in steps[1:3]:self.assertNotIn('env',s)
        self.assertIn("steps.cleanup.outcome == 'success'",steps[3]['if'])
        surfaces=[s['name'] for s in self.workflow()['jobs']['execute']['steps'] if 'FACTORLAB_PRIVATE_TOKEN' in s.get('env',{})]
        self.assertEqual(surfaces,['Prepare fixed private inputs','Return verified results privately'])

    def test_shell_selects_only_fixed_broker_and_phase(self):
        steps=[s for s in self.workflow()['jobs']['execute']['steps'] if BROKER in s.get('run','')]
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);shim=folder/'python3';log=folder/'called'
            shim.write_text('#!/bin/sh\nprintf "%s\n" "$*" >> "$CALL_LOG"\n');shim.chmod(0o700)
            for phase,s in zip(('prepare','compute','cleanup','publish'),steps):
                if log.exists():log.unlink()
                command=s['run'].replace('${{ inputs.profile }}',PROFILE)
                subprocess.run(['/bin/bash','-e','-o','pipefail','-c',command],check=True,timeout=10,
                    env={'PATH':d+os.pathsep+os.defpath,'CALL_LOG':str(log)})
                self.assertEqual(log.read_text().splitlines(),[BROKER+' '+phase+' '+PROFILE])

    def test_23_file_identity_and_isolated_import(self):
        broker.load_profile();m=json.loads(broker.MANIFEST.read_text());self.assertEqual(len(m['sources']),23)
        dirs=sorted({str(Path(p).resolve()) for p in sys.path if p and ('site-packages' in Path(p).parts or 'dist-packages' in Path(p).parts)})
        with tempfile.TemporaryDirectory() as d:
            stage=Path(d)/'stage';stage.mkdir()
            for name in m['sources']:shutil.copy2(ROOT/'executor'/name,stage/name)
            code="import sys,json;from pathlib import Path;p=Path(sys.argv[1]);sys.path[:0]=[str(p),*json.loads(sys.argv[2])];import wave_r3_clock_entry_v1 as a;import wave_r3_clock_verifier_v1 as b;import wave_r3_clock_runtime_v1 as c;assert all(Path(x.__file__).resolve().parent==p for x in (a,b,c));print('AUDIT_STAGE_PASS')"
            result=subprocess.run([sys.executable,'-I','-c',code,str(stage),json.dumps(dirs)],cwd=d,check=True,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.stdout.strip(),'AUDIT_STAGE_PASS')

    def test_runtime_binds_no_argument_entry_and_verifier(self):
        p=broker.load_profile();runtime.validate(p)
        self.assertEqual(p['command'],['r3_clock/wave_r3_clock_entry_v1.py'])
        self.assertEqual(p['verify_command'],['r3_clock/wave_r3_clock_verifier_v1.py'])
        for key,value in [('command',['anything.py']),('command_timeout_seconds',901),('production_authority',True)]:
            changed=dict(p);changed[key]=value
            with self.assertRaises(ValueError):runtime.validate(changed)

    def test_broker_keeps_private_return_scope_and_context(self):
        text=(ROOT/BROKER).read_text()
        self.assertIn('frozen.require_context()',text)
        self.assertIn("private_source_ref=PRIVATE_REF",text)
        self.assertIn("if not state.get('cleanup_complete')",text)
        self.assertEqual(text.count("for item in idx['panels'][:24]"),1)
        self.assertNotIn('CLOUD_CURRENT',text)
        self.assertNotIn('controller_dispatch',text)
        self.assertIn("if state.get('profile_name')!=PROFILE",text)

    def test_manifest_wrong_profile_rejected(self):
        m=json.loads(broker.MANIFEST.read_text());m['profile']='unapproved'
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'manifest.json';path.write_text(json.dumps(m))
            with patch.object(broker,'MANIFEST',path):
                with self.assertRaises(ValueError):broker.load_profile()

    def test_all_19_historical_source_identities_remain_unchanged(self):
        checkpoint=json.loads((ROOT/'docs/research/TWO_WAVE_R3_CLOCK_AUDIT_SOURCE_CHECKPOINT_V1.json').read_text())
        for name,meta in checkpoint['sources'].items():
            self.assertEqual(blob((ROOT/'executor'/name).read_bytes()),meta['git_blob_sha1'])
        text=(ROOT/'.github/workflows/r3-clock-audit-source-tests.yml').read_text()
        self.assertIn('result.testsRun >= 70',text)
        self.assertIn('not result.skipped',text)

if __name__=='__main__':unittest.main()
