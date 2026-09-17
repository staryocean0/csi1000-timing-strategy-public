"""#363 v2 fixed-route registration and history preservation."""
import hashlib,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
from tests.segmentation_carrier_registration_support import (
    PROFILE as CARRIER_PROFILE, PACKET_PROFILE as V1_PROFILE,
    PACKET_V2_PROFILE as PROFILE, PACKET_V2_BROKER as BROKER,
    strip_packet_v2_workflow, strip_packet_v2_controller,
)
import wave_scale_reference_packet_broker_v2 as broker
MANIFEST=ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_PACKET_EXECUTION_MANIFEST_V2.json'
PROTOCOL=ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_PACKET_PROTOCOL_V2_20260917.json'
REFERENCE=ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_PROTOCOL_V2_20260917.json'
CARRIER=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_CARRIER_QUALIFICATION_PROTOCOL_20260917.json'
WORKFLOW=ROOT/'.github/workflows/public-compute.yml';CONTROLLER=ROOT/'.github/workflows/controller-dispatch.yml'
BASE_WORKFLOW_BLOB='9641a96abaec6d1087d1c1ff31e16a32a9bb3429'
BASE_CONTROLLER_BLOB='16d1f6008359c4a1fa36ea84de617378f5011f26'

def blob(path):
    raw=Path(path).read_bytes();return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

class PacketV2RegistrationTests(unittest.TestCase):
    def workflow(self):
        return yaml.load(WORKFLOW.read_text(),Loader=yaml.BaseLoader)

    def test_profile_stage_and_secret_boundary(self):
        doc=self.workflow();opts=doc['on']['workflow_dispatch']['inputs']['profile']['options']
        self.assertEqual(opts.count(PROFILE),1)
        stage=next(s for s in doc['jobs']['execute']['steps'] if 'wave_segmentation_carrier_stage_public.py' in s.get('run',''))
        self.assertEqual(stage['if'],f"inputs.profile == '{CARRIER_PROFILE}' || inputs.profile == '{V1_PROFILE}' || inputs.profile == '{PROFILE}'")
        self.assertNotIn('env',stage)
        self.assertEqual(WORKFLOW.read_text().count('secrets.FACTORLAB_PRIVATE_TOKEN'),2)

    def test_prepare_compute_allowlists_and_four_routes(self):
        steps=self.workflow()['jobs']['execute']['steps']
        for name in ('Prepare fixed private inputs','Compute without private credentials'):
            self.assertEqual(next(s for s in steps if s['name']==name)['if'].count(PROFILE),1)
        routed=[s for s in steps if BROKER in s.get('run','')]
        self.assertEqual(len(routed),4)
        for phase,step in zip(('prepare','compute','cleanup','publish'),routed):
            self.assertEqual(step['run'].count(BROKER+' '+phase+' '+PROFILE),1)

    def test_controller_exact_title_and_parent_recovery(self):
        text=CONTROLLER.read_text()
        self.assertEqual(text.count("github.event.issue.title == 'controller: "+PROFILE+"'"),1)
        self.assertEqual(text.count("profile='"+PROFILE+"'"),1)
        self.assertEqual(text.count('actions/workflows/public-compute.yml/dispatches'),1)
        restored=strip_packet_v2_workflow(WORKFLOW.read_text()).encode()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(restored)).encode()+b'\0'+restored).hexdigest(),BASE_WORKFLOW_BLOB)
        restored=strip_packet_v2_controller(CONTROLLER.read_text()).encode()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(restored)).encode()+b'\0'+restored).hexdigest(),BASE_CONTROLLER_BLOB)

    def test_manifest_source_and_protocol_identities(self):
        m=json.loads(MANIFEST.read_text());self.assertEqual(m['profile'],PROFILE)
        for name,sha in m['source_blobs'].items():self.assertEqual(blob(ROOT/'executor'/name),sha,name)
        self.assertEqual(blob(ROOT/'executor/wave_scale_reference_packet_broker_v2.py'),m['broker_blob'])
        self.assertEqual(blob(PROTOCOL),m['protocol_blob']);self.assertEqual(blob(REFERENCE),m['reference_protocol_blob'])
        self.assertEqual(blob(CARRIER),m['carrier_protocol_blob'])
        self.assertEqual(m['command'],['scale_reference_packet/wave_scale_reference_packet_entry_v2.py'])
        self.assertEqual(m['verify_command'],['scale_reference_packet/wave_scale_reference_packet_verifier_v2.py'])

    def test_protocol_is_support_amendment_only(self):
        p=json.loads(PROTOCOL.read_text());r=p['reference_contract']
        self.assertEqual(p['failed_v1_run'],'35205287251-1')
        self.assertTrue(r['eligibility_before_hash_ranking'])
        self.assertIn('csi1000-s2-ref-v2',r['day_rank'])
        self.assertFalse(r['anchor_context_eligibility']['causal_flat_fill_any'])
        self.assertFalse(r['anchor_context_eligibility']['post_selection_substitution'])
        self.assertFalse(p['primary_labels_frozen']);self.assertIsNone(p['numeric_state_thresholds'])
        for key in ('outcomes_used','R4_selected','one_minute_strategy_admitted','router_pnl','new_training','production_authority'):
            self.assertFalse(p[key],key)

    def test_broker_and_verifier_boundaries(self):
        profile=broker.load_profile(PROFILE);self.assertFalse(profile['production_authority'])
        text=(ROOT/'executor/wave_scale_reference_packet_verifier_v2.py').read_text()
        for forbidden in ('wave_scale_reference_packet_v2','wave_scale_reference_packet_entry_v2','wave_scale_reference_visuals_v1','wave_scale_dominance_diagnostics'):
            self.assertNotIn(forbidden,text)
        self.assertIn('wave_segmentation_carrier_verifier_v1',text)
        self.assertIn('wave_scale_reference_verifier_v2',text)

    def test_isolated_stage_import_closure(self):
        m=json.loads(MANIFEST.read_text())
        packages=sorted({str(Path(x).resolve()) for x in sys.path if x and ('site-packages' in Path(x).parts or 'dist-packages' in Path(x).parts)})
        with tempfile.TemporaryDirectory() as d:
            stage=Path(d)/'stage';stage.mkdir()
            for name in m['source_blobs']:shutil.copy2(ROOT/'executor'/name,stage/name)
            code=("import sys,json;from pathlib import Path;p=Path(sys.argv[1]);sys.path[:0]=[str(p),*json.loads(sys.argv[2])];"
                  "import wave_scale_reference_packet_v2 as a;import wave_scale_reference_packet_entry_v2 as b;"
                  "import wave_scale_reference_packet_verifier_v2 as c;assert all(Path(x.__file__).resolve().parent==p for x in (a,b,c));print('V2_STAGE_PASS')")
            done=subprocess.run([sys.executable,'-I','-c',code,str(stage),json.dumps(packages)],cwd=d,check=True,capture_output=True,text=True,timeout=30)
            self.assertEqual(done.stdout.strip(),'V2_STAGE_PASS')

    def test_history_records_failed_v1_and_unrun_v2(self):
        cp=json.loads((ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_PACKET_V2_CHECKPOINT_20260917.json').read_text())
        line=json.loads((ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json').read_text())
        raw=json.dumps(line['ordered_lineage'][:17],sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),cp['prior_17_lineage_sha256'])
        self.assertEqual(line['ordered_lineage'][17]['formal_run'],'35205287251-1')
        self.assertFalse(line['ordered_lineage'][17]['panels_generated'])
        self.assertEqual(line['ordered_lineage'][18]['issue'],363);self.assertIsNone(line['ordered_lineage'][18]['market_packet_run'])

if __name__=='__main__':unittest.main()
