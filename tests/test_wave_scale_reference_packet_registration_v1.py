"""#359 fixed standard-route registration and source closure."""
import hashlib,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
from tests.segmentation_carrier_registration_support import (
    PROFILE as CARRIER_PROFILE, PACKET_PROFILE as PROFILE,
    PACKET_BROKER as BROKER, PACKET_V2_PROFILE,PACKET_V3_PROFILE, strip_packet_workflow, strip_packet_controller,
)
import wave_scale_reference_packet_broker_v1 as broker

MANIFEST=ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_PACKET_EXECUTION_MANIFEST_V1.json'
PROTOCOL=ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_PACKET_PROTOCOL_20260917.json'
CARRIER_PROTOCOL=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_CARRIER_QUALIFICATION_PROTOCOL_20260917.json'
WORKFLOW=ROOT/'.github/workflows/public-compute.yml'
CONTROLLER=ROOT/'.github/workflows/controller-dispatch.yml'
BASE_WORKFLOW_BLOB='e674f0573a05e27f3c058ff5d681747fad0b6ea6'
BASE_CONTROLLER_BLOB='664511cdd219c5fb88d9fd4bec719074185f61e9'


def blob(path):
    raw=Path(path).read_bytes()
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


class PacketRegistrationTests(unittest.TestCase):
    def workflow(self):
        return yaml.load(WORKFLOW.read_text(),Loader=yaml.BaseLoader)

    def test_profile_option_and_shared_public_stage(self):
        doc=self.workflow();options=doc['on']['workflow_dispatch']['inputs']['profile']['options']
        self.assertEqual(options.count(PROFILE),1)
        steps=doc['jobs']['execute']['steps']
        stage=[s for s in steps if 'wave_segmentation_carrier_stage_public.py' in s.get('run','')]
        self.assertEqual(len(stage),1)
        self.assertEqual(stage[0]['if'],f"inputs.profile == '{CARRIER_PROFILE}' || inputs.profile == '{PROFILE}' || inputs.profile == '{PACKET_V2_PROFILE}' || inputs.profile == '{PACKET_V3_PROFILE}'")
        self.assertNotIn('env',stage[0]);self.assertNotIn('FACTORLAB_PRIVATE_TOKEN',stage[0]['run'])

    def test_prepare_compute_allowlists_and_four_routes(self):
        steps=self.workflow()['jobs']['execute']['steps']
        for name in ('Prepare fixed private inputs','Compute without private credentials'):
            step=next(s for s in steps if s['name']==name)
            self.assertEqual(step['if'].count(PROFILE),1)
        routed=[s for s in steps if BROKER in s.get('run','')]
        self.assertEqual([s['name'] for s in routed],['Prepare fixed private inputs','Compute without private credentials',
            'Stop owned container before credentials return','Return verified results privately'])
        for phase,step in zip(('prepare','compute','cleanup','publish'),routed):
            self.assertEqual(step['run'].count(BROKER+' '+phase+' '+PROFILE),1)

    def test_secret_surface_stays_exactly_two(self):
        text=WORKFLOW.read_text()
        self.assertEqual(text.count('secrets.FACTORLAB_PRIVATE_TOKEN'),2)
        surfaces=[s['name'] for s in self.workflow()['jobs']['execute']['steps']
                  if 'FACTORLAB_PRIVATE_TOKEN' in s.get('env',{})]
        self.assertEqual(surfaces,['Prepare fixed private inputs','Return verified results privately'])
        routed=[s for s in self.workflow()['jobs']['execute']['steps'] if BROKER in s.get('run','')]
        for step in routed[1:3]:
            self.assertNotIn('env',step);self.assertNotIn('FACTORLAB_PRIVATE_TOKEN',step['run'])

    def test_controller_exact_title_standard_workflow_only(self):
        text=CONTROLLER.read_text()
        self.assertEqual(text.count("github.event.issue.title == 'controller: "+PROFILE+"'"),1)
        self.assertEqual(text.count("profile='"+PROFILE+"'"),1)
        self.assertEqual(text.count('actions/workflows/public-compute.yml/dispatches'),1)
        self.assertNotIn('FACTORLAB_PRIVATE_TOKEN',text)
        self.assertNotIn('wave_scale_reference_packet_broker_v1.py',text)

    def test_packet_route_strips_exactly_to_merged_parent(self):
        restored=strip_packet_workflow(WORKFLOW.read_text()).encode()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(restored)).encode()+b'\0'+restored).hexdigest(),BASE_WORKFLOW_BLOB)
        restored=strip_packet_controller(CONTROLLER.read_text()).encode()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(restored)).encode()+b'\0'+restored).hexdigest(),BASE_CONTROLLER_BLOB)

    def test_execution_manifest_and_source_identities(self):
        m=json.loads(MANIFEST.read_text())
        self.assertEqual(m['profile'],PROFILE);self.assertEqual(m['private_ref'],'7688ba57206dd29fbef88d8e57475255718471fe')
        expected={
            'wave_scale_reference_packet_v1.py','wave_scale_reference_packet_entry_v1.py',
            'wave_scale_reference_packet_verifier_v1.py','wave_scale_reference_sampling_v1.py',
            'wave_scale_reference_visuals_v1.py','wave_scale_reference_verifier_v1.py',
            'wave_segmentation_carrier_qualification_v1.py','wave_segmentation_carrier_verifier_v1.py'}
        self.assertEqual(set(m['source_blobs']),expected)
        for name,sha in m['source_blobs'].items():self.assertEqual(blob(ROOT/'executor'/name),sha,name)
        self.assertEqual(blob(ROOT/'executor/wave_scale_reference_packet_broker_v1.py'),m['broker_blob'])
        self.assertEqual(blob(ROOT/'executor/wave_segmentation_carrier_stage_public.py'),m['stage_blob'])
        self.assertEqual(blob(PROTOCOL),m['protocol_blob']);self.assertEqual(blob(CARRIER_PROTOCOL),m['carrier_protocol_blob'])

    def test_manifest_commands_and_profile_are_bounded(self):
        m=json.loads(MANIFEST.read_text())
        self.assertEqual(m['command'],['scale_reference_packet/wave_scale_reference_packet_entry_v1.py'])
        self.assertEqual(m['verify_command'],['scale_reference_packet/wave_scale_reference_packet_verifier_v1.py'])
        self.assertEqual((m['command_timeout_seconds'],m['verification_timeout_seconds']),(600,600))
        self.assertFalse(m['new_training']);self.assertFalse(m['production_authority'])
        profile=broker.load_profile(PROFILE)
        self.assertEqual(profile['command'],m['command']);self.assertEqual(profile['verify_command'],m['verify_command'])
        self.assertFalse(profile['new_training']);self.assertFalse(profile['production_authority'])

    def test_protocol_reuses_exact_six_qualified_carriers(self):
        p=json.loads(PROTOCOL.read_text());c=json.loads(CARRIER_PROTOCOL.read_text())
        self.assertEqual(p['files'],c['files'])
        self.assertEqual(p['external_repository'],c['external_repository'])
        self.assertEqual(p['external_ref'],c['external_ref'])
        self.assertEqual(sum(v['bytes'] for v in p['files'].values()),29097610)
        self.assertEqual(p['expected_common_complete_eligible_days'],1458)
        self.assertEqual(p['carrier_qualification_run'],'35191936364-1')

    def test_protocol_freezes_packet_without_labels_scores_or_future_suffix(self):
        p=json.loads(PROTOCOL.read_text());r=p['reference_contract'];b=p['blindness']
        self.assertEqual(r['primary_panels'],192);self.assertEqual(r['contexts_trading_minutes'],[150,300])
        self.assertFalse(r['future_suffix_generated']);self.assertFalse(r['replace_unsupported_anchor'])
        self.assertTrue(r['fail_on_causal_flat_fill_in_context'])
        for key in ('calendar_date_in_blind_outputs','candidate_outputs','diagnostic_scores','R_version_identity',
                    'PnL_or_outcomes','numeric_amplitude_pass_A','smoothing_or_candidate_line'):
            self.assertFalse(b[key],key)
        self.assertFalse(p['primary_labels_frozen']);self.assertIsNone(p['numeric_state_thresholds'])
        for key in ('outcomes_used','R4_selected','one_minute_strategy_admitted','router_pnl','new_training','production_authority'):
            self.assertFalse(p[key],key)

    def test_isolated_stage_import_closure(self):
        m=json.loads(MANIFEST.read_text())
        package_dirs=sorted({str(Path(x).resolve()) for x in sys.path if x and
                             ('site-packages' in Path(x).parts or 'dist-packages' in Path(x).parts)})
        with tempfile.TemporaryDirectory() as d:
            stage=Path(d)/'stage';stage.mkdir()
            for name in m['source_blobs']:shutil.copy2(ROOT/'executor'/name,stage/name)
            code=("import sys,json;from pathlib import Path;p=Path(sys.argv[1]);"
                  "sys.path[:0]=[str(p),*json.loads(sys.argv[2])];"
                  "import wave_scale_reference_packet_v1 as a;import wave_scale_reference_packet_entry_v1 as b;"
                  "import wave_scale_reference_packet_verifier_v1 as c;"
                  "assert all(Path(x.__file__).resolve().parent==p for x in (a,b,c));print('PACKET_STAGE_PASS')")
            done=subprocess.run([sys.executable,'-I','-c',code,str(stage),json.dumps(package_dirs)],
                                cwd=d,check=True,capture_output=True,text=True,timeout=30)
            self.assertEqual(done.stdout.strip(),'PACKET_STAGE_PASS')

    def test_independent_verifier_import_boundary(self):
        text=(ROOT/'executor/wave_scale_reference_packet_verifier_v1.py').read_text()
        for forbidden in ('wave_scale_reference_packet_v1','wave_scale_reference_packet_entry_v1.py',
                          'wave_scale_reference_visuals_v1','wave_scale_dominance_diagnostics'):
            self.assertNotIn(forbidden,text)
        self.assertIn('wave_segmentation_carrier_verifier_v1',text)
        self.assertIn('wave_scale_reference_verifier_v1',text)

    def test_broker_publish_surface_is_summary_only_after_generic_archive(self):
        text=(ROOT/'executor/wave_scale_reference_packet_broker_v1.py').read_text()
        self.assertIn('original_publish(profile)',text)
        self.assertIn("'packet_summary.json'",text)
        self.assertNotIn("'full_inventory.json'",text)
        self.assertNotIn("'blind_inventory.json'",text)
        self.assertNotIn("'panel_manifest.json'",text)
        self.assertNotIn('CLOUD_CURRENT',text);self.assertNotIn('argparse',text)

    def test_shared_stage_and_dependencies_are_unchanged(self):
        m=json.loads(MANIFEST.read_text())
        self.assertEqual(m['stage_blob'],'c0e737d93278273f5180ae3cd60e66c75aec80cc')
        expected={'research_broker.py':'1b4968475fc91a34f53bc08b7b5fdc1bf79862c0',
                  'broker.py':'299ab90424e42f76f038d3bad719cb2abeb155dc',
                  'run_research_in_container.py':'38dfa9bbcf0a09b328495b4844c82e25c9b5bec8'}
        self.assertEqual(m['dependency_blobs'],expected)
        for name,sha in expected.items():self.assertEqual(blob(ROOT/'executor'/name),sha)


    def test_registration_checkpoint_preserves_prior_sixteen_lineage_rows(self):
        cp=json.loads((ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_PACKET_REGISTRATION_CHECKPOINT_20260917.json').read_text())
        lineage=json.loads((ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json').read_text())
        raw=json.dumps(lineage['ordered_lineage'][:16],sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),cp['history_guard']['prior_16_lineage_sha256'])
        self.assertEqual(lineage['ordered_lineage'][16]['order'],17)
        self.assertEqual(lineage['ordered_lineage'][16]['status'],'BLIND_PACKET_PROFILE_REGISTERED_NOT_RUN')
        self.assertIsNone(lineage['ordered_lineage'][16]['market_packet_run'])

    def test_thread_authority_is_registered_not_run(self):
        a=json.loads((ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json').read_text())
        lane=next(x for x in a['active_lanes'] if x['issue']==353)
        lineage=json.loads((ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json').read_text())
        # Historical v1 failure remains frozen even after the thread advances to
        # a later verified packet and annotation stage.
        self.assertEqual(lineage['ordered_lineage'][17]['formal_run'],'35205287251-1')
        self.assertIn('FAILED',lineage['ordered_lineage'][17]['status'])
        self.assertEqual(a['S2_progress']['market_packet_run'],'35209602753-1_PASSED')
        self.assertTrue(a['S2_progress']['primary_reference_labels'].startswith(('NOT_YET_FROZEN','FROZEN_192_')))
        self.assertIsNone(a['S2_progress']['market_thresholds'])
        self.assertEqual(lineage['ordered_lineage'][16]['status'],'BLIND_PACKET_PROFILE_REGISTERED_NOT_RUN')



if __name__=='__main__':unittest.main()
