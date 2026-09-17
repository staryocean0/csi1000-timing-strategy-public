"""Public source checkpoint checks. Not an execution-registration test."""
import hashlib,json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'docs/research/TWO_WAVE_R3_CLOCK_AUDIT_SOURCE_CHECKPOINT_V1.json'

def blob(p):
    raw=Path(p).read_bytes();return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

class SourceClosureTests(unittest.TestCase):
    def test_all_nineteen_source_identities(self):
        m=json.loads(MANIFEST.read_text());self.assertEqual(len(m['sources']),19)
        for name,meta in m['sources'].items():self.assertEqual(blob(ROOT/'executor'/name),meta['git_blob_sha1'])

    def test_stage_import_without_original_checkout(self):
        m=json.loads(MANIFEST.read_text())
        package_dirs=sorted({str(Path(p).resolve()) for p in sys.path if p and
            ('site-packages' in Path(p).parts or 'dist-packages' in Path(p).parts)})
        with tempfile.TemporaryDirectory() as d:
            stage=Path(d)/'stage';stage.mkdir()
            for name in m['sources']:shutil.copy2(ROOT/'executor'/name,stage/name)
            code="import sys,json;from pathlib import Path;p=Path(sys.argv[1]);sys.path[:0]=[str(p),*json.loads(sys.argv[2])];import wave_r3_clock_probe_v1 as a;import wave_r3_clock_audit_v1 as b;import wave_r3_clock_checks_v1 as c;assert all(Path(x.__file__).resolve().parent==p for x in (a,b,c));print('PURE_SOURCE_CLOSURE_PASS')"
            r=subprocess.run([sys.executable,'-I','-c',code,str(stage),json.dumps(package_dirs)],cwd=d,
                capture_output=True,text=True,check=True,timeout=30)
            self.assertEqual(r.stdout.strip(),'PURE_SOURCE_CLOSURE_PASS')

    def test_not_execution_ready_and_no_standard_registration(self):
        m=json.loads(MANIFEST.read_text())
        self.assertFalse(m['execution_ready']);self.assertFalse(m['profile_registered']);self.assertIsNone(m['real_run'])
        # This is a historical source checkpoint, not the current execution manifest.
        self.assertNotIn('wave_r3_clock_entry_v1.py',m['sources'])

    def test_existing_control_plane_and_credentials_unchanged(self):
        m=json.loads(MANIFEST.read_text())
        from r3_clock_registration_support import strip_audit_workflow,strip_audit_controller
        for path,sha in m['frozen_control_plane_blobs'].items():
            restore=strip_audit_controller if 'controller' in path else strip_audit_workflow
            raw=restore((ROOT/path).read_text()).encode()
            self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),sha)
        self.assertEqual((ROOT/'.github/workflows/public-compute.yml').read_text().count('secrets.FACTORLAB_PRIVATE_TOKEN'),2)

    def test_source_ci_requires_35_without_skips(self):
        text=(ROOT/'.github/workflows/r3-clock-audit-source-tests.yml').read_text()
        self.assertIn('result.testsRun >= 70',text);self.assertIn('not result.skipped',text)
        self.assertNotIn('FACTORLAB_PRIVATE_TOKEN',text)
        self.assertNotIn('workflow_dispatch:',text)

if __name__=='__main__':unittest.main()
