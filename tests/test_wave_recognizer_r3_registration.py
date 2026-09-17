"""R3 standard-route contracts. Synthetic/source only; never dispatch research."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]
PROFILE='two-wave-recognizer-r3-mature-counter-rearm-v1'
BROKER='executor/wave_recognizer_r3_v1_broker.py'
PARENT_BLOBS={'.github/workflows/public-compute.yml': '34007eccceffd5983e6b4f2bbeec447d4215cc36', '.github/workflows/controller-dispatch.yml': '034cda738cb55a0e40a826add34955413b9880bf'}

def blob(text):
    raw=text.encode()
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

def remove_once(text,part):
    if text.count(part)!=1:
        raise AssertionError('R3 append is missing, duplicated, or altered')
    return text.replace(part,'')

def strip_workflow(text):
    text=remove_once(text,'          - '+PROFILE+'\n')
    condition=" || inputs.profile == '"+PROFILE+"'"
    if text.count(condition)!=2:raise AssertionError('R3 prepare/compute allowlist drift')
    text=text.replace(condition,'')
    for phase in ('prepare','compute','cleanup','publish'):
        addition="          elif [ '${{ inputs.profile }}' = '"+PROFILE+"' ]; then\n            python3 "+BROKER+' '+phase+' '+PROFILE+'\n'
        text=remove_once(text,addition)
    return text

def strip_controller(text):
    text=remove_once(text,"       github.event.issue.title == 'controller: "+PROFILE+"' ||\n")
    return remove_once(text,"            'controller: "+PROFILE+"')\n              profile='"+PROFILE+"'\n              ;;\n")

class R3RegistrationTests(unittest.TestCase):
    def workflow(self):
        return yaml.load((ROOT/'.github/workflows/public-compute.yml').read_text(),Loader=yaml.BaseLoader)

    def phases(self):
        return [step for step in self.workflow()['jobs']['execute']['steps'] if BROKER in step.get('run','')]

    def test_workflow_is_only_exact_R3_append(self):
        path='.github/workflows/public-compute.yml'
        self.assertEqual(blob(strip_workflow((ROOT/path).read_text())),PARENT_BLOBS[path])
        doc=self.workflow()
        self.assertEqual(set(doc['on']),{'workflow_dispatch'})
        self.assertEqual(doc['on']['workflow_dispatch']['inputs']['profile']['options'].count(PROFILE),1)

    def test_controller_is_only_exact_R3_append(self):
        path='.github/workflows/controller-dispatch.yml';text=(ROOT/path).read_text()
        self.assertEqual(blob(strip_controller(text)),PARENT_BLOBS[path])
        self.assertEqual(text.count("github.event.issue.title == 'controller: "+PROFILE+"'"),1)
        self.assertEqual(text.count("profile='"+PROFILE+"'"),1)
        self.assertEqual(text.count('actions/workflows/public-compute.yml/dispatches'),1)
        self.assertNotIn('FACTORLAB_PRIVATE_TOKEN',text)

    def test_shared_phases_keep_exactly_two_credential_boundaries(self):
        doc=self.workflow();text=(ROOT/'.github/workflows/public-compute.yml').read_text()
        self.assertEqual(text.count('secrets.FACTORLAB_PRIVATE_TOKEN'),2)
        steps=self.phases()
        self.assertEqual([s['name'] for s in steps],['Prepare fixed private inputs','Compute without private credentials','Stop owned container before credentials return','Return verified results privately'])
        all_steps=doc['jobs']['execute']['steps']
        surfaces=[s['name'] for s in all_steps if 'FACTORLAB_PRIVATE_TOKEN' in s.get('env',{})]
        self.assertEqual(surfaces,[steps[0]['name'],steps[3]['name']])
        for s in steps[1:3]:
            self.assertNotIn('env',s)
            self.assertNotIn('FACTORLAB_PRIVATE_TOKEN',s['run'])
        self.assertNotIn('FACTORLAB_PRIVATE_TOKEN',doc.get('env',{}))
        self.assertNotIn('FACTORLAB_PRIVATE_TOKEN',doc['jobs']['execute'].get('env',{}))
        self.assertIn("steps.cleanup.outcome == 'success'",steps[3]['if'])

    def test_every_phase_selects_R3_without_silent_skip(self):
        steps=self.phases();self.assertEqual(len(steps),4)
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);shim=folder/'python3';log=folder/'route.log'
            shim.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$ROUTE_LOG"\n')
            shim.chmod(0o700)
            for phase,step in zip(('prepare','compute','cleanup','publish'),steps):
                if log.exists():log.unlink()
                command=step['run'].replace('${{ inputs.profile }}',PROFILE)
                subprocess.run(['/bin/bash','-e','-o','pipefail','-c',command],check=True,timeout=10,env={'PATH':d+os.pathsep+os.defpath,'ROUTE_LOG':str(log)})
                self.assertEqual(log.read_text().splitlines(),[BROKER+' '+phase+' '+PROFILE])

    def test_all_fifteen_staged_source_identities_remain_frozen(self):
        sys.path.insert(0,str(ROOT/'executor'))
        import wave_recognizer_r3_v1_broker as broker
        fixed=broker.load_profile();manifest=json.loads(broker.MANIFEST.read_text())
        self.assertEqual(manifest['profile'],PROFILE)
        self.assertEqual(len(manifest['sources']),15)
        self.assertEqual(set(manifest['sources']),set(broker.SOURCES))
        self.assertFalse(fixed['new_training']);self.assertFalse(fixed['production_authority'])
        self.assertEqual(fixed['command_timeout_seconds'],900)
        self.assertEqual(fixed['verification_timeout_seconds'],900)

    def test_exact_stage_import_closure_without_checkout_imports(self):
        manifest=json.loads((ROOT/'docs/research/TWO_WAVE_RECOGNIZER_R3_EXECUTION_MANIFEST_V1.json').read_text())
        package_dirs=sorted({str(Path(p).resolve()) for p in sys.path if p and ('site-packages' in Path(p).parts or 'dist-packages' in Path(p).parts)})
        with tempfile.TemporaryDirectory() as d:
            stage=Path(d)/'stage';stage.mkdir()
            for name in manifest['sources']:shutil.copy2(ROOT/'executor'/name,stage/name)
            code="import sys,json;from pathlib import Path;stage=Path(sys.argv[1]);sys.path[:0]=[str(stage),*json.loads(sys.argv[2])];import wave_recognizer_r3_v1_entry as e;import wave_recognizer_r3_v1_verifier as v;import wave_recognizer_r3_v1_visuals as w;assert all(Path(m.__file__).resolve().parent==stage for m in (e,v,w));print('R3_STAGE_IMPORT_PASS')"
            done=subprocess.run([sys.executable,'-I','-c',code,str(stage),json.dumps(package_dirs)],cwd=d,check=True,capture_output=True,text=True,timeout=30)
            self.assertEqual(done.stdout.strip(),'R3_STAGE_IMPORT_PASS')

    def test_source_CI_requires_all_twenty_two_cases_without_skips(self):
        text=(ROOT/'.github/workflows/wave-recognizer-r3-source-tests.yml').read_text()
        self.assertIn("pattern='test_wave_recognizer_r3*.py'",text)
        self.assertIn('result.testsRun >= 22',text)
        self.assertIn('not result.skipped',text)
        self.assertIn('executor/wave_recognizer_r3_v1_protocol.json',text)

    def test_premerged_broker_unchanged(self):
        self.assertEqual(blob((ROOT/BROKER).read_text()),'7f9b0c9f2f0c50b655c24fe5438f4c84a54a0f86')

if __name__=='__main__':unittest.main()
