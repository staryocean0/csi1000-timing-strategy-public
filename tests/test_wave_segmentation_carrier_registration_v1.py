"""#352 standard-route and source-closure contracts. Synthetic/source only."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
from tests.segmentation_carrier_registration_support import PROFILE,BROKER,PACKET_PROFILE,PACKET_V2_PROFILE,PACKET_V3_PROFILE,MARKET_PROFILE,VALIDITY_PROFILE,strip_workflow,strip_controller
import wave_segmentation_carrier_broker_v1 as broker

MANIFEST=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_CARRIER_QUALIFICATION_EXECUTION_MANIFEST_V1.json'
PROTOCOL=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_CARRIER_QUALIFICATION_PROTOCOL_20260917.json'
STAGE='executor/wave_segmentation_carrier_stage_public.py'


def blob(path):
    raw=Path(path).read_bytes();return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


class RegistrationTests(unittest.TestCase):
    def workflow(self):
        return yaml.load((ROOT/'.github/workflows/public-compute.yml').read_text(),Loader=yaml.BaseLoader)

    def phases(self):
        return [step for step in self.workflow()['jobs']['execute']['steps'] if BROKER in step.get('run','')]

    def test_profile_option_exactly_once(self):
        doc=self.workflow()
        self.assertEqual(set(doc['on']),{'workflow_dispatch'})
        self.assertEqual(doc['on']['workflow_dispatch']['inputs']['profile']['options'].count(PROFILE),1)

    def test_public_stage_exactly_once_and_without_secret(self):
        steps=self.workflow()['jobs']['execute']['steps']
        stage=[s for s in steps if 'wave_segmentation_carrier_stage_public.py' in s.get('run','')]
        self.assertEqual(len(stage),1)
        self.assertEqual(stage[0]['name'],'Stage fixed public Two-Wave segmentation carriers without private credentials')
        self.assertEqual(stage[0]['if'],f"inputs.profile == '{PROFILE}' || inputs.profile == '{PACKET_PROFILE}' || inputs.profile == '{PACKET_V2_PROFILE}' || inputs.profile == '{PACKET_V3_PROFILE}' || inputs.profile == '{MARKET_PROFILE}' || inputs.profile == '{VALIDITY_PROFILE}'")
        self.assertNotIn('env',stage[0]);self.assertNotIn('FACTORLAB_PRIVATE_TOKEN',stage[0]['run'])

    def test_prepare_and_compute_allowlists_each_include_profile_once(self):
        steps=self.workflow()['jobs']['execute']['steps']
        selected=[s for s in steps if s['name'] in ('Prepare fixed private inputs','Compute without private credentials')]
        self.assertEqual(len(selected),2)
        for step in selected:self.assertEqual(step['if'].count(PROFILE),1)

    def test_four_shared_phase_branches_exactly_once(self):
        steps=self.phases();self.assertEqual(len(steps),4)
        self.assertEqual([s['name'] for s in steps],['Prepare fixed private inputs','Compute without private credentials',
            'Stop owned container before credentials return','Return verified results privately'])
        for phase,step in zip(('prepare','compute','cleanup','publish'),steps):
            self.assertEqual(step['run'].count(BROKER+' '+phase+' '+PROFILE),1)

    def test_secret_surfaces_remain_exactly_two(self):
        text=(ROOT/'.github/workflows/public-compute.yml').read_text()
        self.assertEqual(text.count('secrets.FACTORLAB_PRIVATE_TOKEN'),2)
        surfaces=[s['name'] for s in self.workflow()['jobs']['execute']['steps'] if 'FACTORLAB_PRIVATE_TOKEN' in s.get('env',{})]
        self.assertEqual(surfaces,['Prepare fixed private inputs','Return verified results privately'])

    def test_compute_and_cleanup_have_no_private_environment(self):
        for step in self.phases()[1:3]:
            self.assertNotIn('env',step)
            self.assertNotIn('FACTORLAB_PRIVATE_TOKEN',step['run'])

    def test_publish_requires_cleanup_success(self):
        self.assertIn("steps.cleanup.outcome == 'success'",self.phases()[3]['if'])

    def test_controller_exact_title_and_profile_once(self):
        text=(ROOT/'.github/workflows/controller-dispatch.yml').read_text()
        self.assertEqual(text.count("github.event.issue.title == 'controller: "+PROFILE+"'"),1)
        self.assertEqual(text.count("profile='"+PROFILE+"'"),1)
        self.assertEqual(text.count('actions/workflows/public-compute.yml/dispatches'),1)
        self.assertNotIn('FACTORLAB_PRIVATE_TOKEN',text)

    def test_later_route_strips_to_exact_parent_control_plane(self):
        workflow=(ROOT/'.github/workflows/public-compute.yml').read_text()
        controller=(ROOT/'.github/workflows/controller-dispatch.yml').read_text()
        restored=strip_workflow(workflow).encode()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(restored)).encode()+b'\0'+restored).hexdigest(),'4ff3e711c41d94039926d3115a0d90496f59dfdc')
        restored=strip_controller(controller).encode()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(restored)).encode()+b'\0'+restored).hexdigest(),'0af89aa3d5056deac95638e574346a800ae4496e')

    def test_job_timeout_covers_step_timeouts(self):
        text=(ROOT/'.github/workflows/public-compute.yml').read_text()
        values=[int(v) for v in re.findall(r'timeout-minutes: (\d+)',text)]
        self.assertLessEqual(sum(values[1:]),values[0])
        self.assertEqual(values[0],80)

    def test_execution_manifest_source_identities(self):
        m=json.loads(MANIFEST.read_text())
        self.assertEqual(m['profile'],PROFILE)
        self.assertEqual(set(m['source_blobs']),{
            'wave_segmentation_carrier_qualification_v1.py','wave_segmentation_carrier_entry_v1.py',
            'wave_segmentation_carrier_verifier_v1.py'})
        for name,sha in m['source_blobs'].items():self.assertEqual(blob(ROOT/'executor'/name),sha)
        self.assertEqual(blob(ROOT/'executor/wave_segmentation_carrier_broker_v1.py'),m['broker_blob'])
        self.assertEqual(blob(ROOT/'executor/wave_segmentation_carrier_stage_public.py'),m['stage_blob'])
        self.assertEqual(blob(PROTOCOL),m['protocol_blob'])

    def test_shared_dependency_identities_frozen(self):
        m=json.loads(MANIFEST.read_text())
        expected={'research_broker.py':'1b4968475fc91a34f53bc08b7b5fdc1bf79862c0',
            'broker.py':'299ab90424e42f76f038d3bad719cb2abeb155dc',
            'run_research_in_container.py':'38dfa9bbcf0a09b328495b4844c82e25c9b5bec8'}
        self.assertEqual(m['dependency_blobs'],expected)
        for name,sha in expected.items():self.assertEqual(blob(ROOT/'executor'/name),sha)

    def test_broker_loads_exact_manifest(self):
        p=broker.load_profile(PROFILE)
        self.assertEqual(p['command'],['segmentation_carrier/wave_segmentation_carrier_entry_v1.py'])
        self.assertEqual(p['verify_command'],['segmentation_carrier/wave_segmentation_carrier_verifier_v1.py'])
        self.assertEqual((p['command_timeout_seconds'],p['verification_timeout_seconds']),(300,300))
        self.assertFalse(p['new_training']);self.assertFalse(p['production_authority'])

    def test_protocol_pins_six_exact_public_files(self):
        p=json.loads(PROTOCOL.read_text())
        self.assertEqual(set(p['files']),{'1m_official.parquet',*(f'5m_offset_{i}.parquet' for i in range(5))})
        self.assertEqual(sum(v['bytes'] for v in p['files'].values()),29097610)
        for meta in p['files'].values():
            self.assertRegex(meta['sha256'],r'^[0-9a-f]{64}$')
            self.assertRegex(meta['git_blob_sha1'],r'^[0-9a-f]{40}$')

    def test_protocol_fixes_comparison_tolerance_and_scope(self):
        p=json.loads(PROTOCOL.read_text())
        self.assertEqual(p['comparison']['abs_tolerance'],1e-10)
        self.assertEqual(p['comparison']['rel_tolerance'],1e-12)
        self.assertFalse(p['comparison']['align_by_row_index'])
        self.assertFalse(p['aliasing_conclusion_allowed']);self.assertFalse(p['scale_dominance_conclusion_allowed'])
        self.assertFalse(p['R4_selected']);self.assertFalse(p['one_minute_strategy_admitted'])

    def test_public_stage_has_fixed_source_and_no_runtime_arguments(self):
        text=(ROOT/STAGE).read_text()
        self.assertIn("REPO='staryocean0/factorlab-two-wave-strategy-lab'",text)
        self.assertIn("REF='152ae1ef11a04bb3b434da25025794db7a706c81'",text)
        self.assertNotIn('argparse',text);self.assertNotIn('sys.argv',text)
        self.assertIn("if os.environ.get('FACTORLAB_PRIVATE_TOKEN')",text)
        self.assertNotIn('PRIVATE_REPO',text)

    def test_entry_is_fixed_path_and_no_cli(self):
        text=(ROOT/'executor/wave_segmentation_carrier_entry_v1.py').read_text()
        self.assertIn('INPUTS = Path("/work/inputs")',text)
        self.assertIn('OUT = Path("/results/study")',text)
        self.assertNotIn('argparse',text);self.assertNotIn('sys.argv',text)
        self.assertNotIn('requests',text);self.assertNotIn('urllib',text)

    def test_verifier_does_not_import_producer(self):
        text=(ROOT/'executor/wave_segmentation_carrier_verifier_v1.py').read_text()
        self.assertNotIn('wave_segmentation_carrier_qualification_v1',text)
        self.assertNotIn('wave_segmentation_carrier_entry_v1',text)
        self.assertIn('verify_reconstruction',text);self.assertIn('verify_common',text)

    def test_isolated_container_source_import_closure(self):
        m=json.loads(MANIFEST.read_text())
        package_dirs=sorted({str(Path(p).resolve()) for p in sys.path if p and
            ('site-packages' in Path(p).parts or 'dist-packages' in Path(p).parts)})
        with tempfile.TemporaryDirectory() as d:
            stage=Path(d)/'stage';stage.mkdir()
            for name in m['source_blobs']:shutil.copy2(ROOT/'executor'/name,stage/name)
            code=("import sys,json;from pathlib import Path;p=Path(sys.argv[1]);"
                  "sys.path[:0]=[str(p),*json.loads(sys.argv[2])];"
                  "import wave_segmentation_carrier_qualification_v1 as q;"
                  "import wave_segmentation_carrier_entry_v1 as e;"
                  "import wave_segmentation_carrier_verifier_v1 as v;"
                  "assert all(Path(x.__file__).resolve().parent==p for x in (q,e,v));print('S1_STAGE_PASS')")
            done=subprocess.run([sys.executable,'-I','-c',code,str(stage),json.dumps(package_dirs)],cwd=d,
                check=True,capture_output=True,text=True,timeout=30)
            self.assertEqual(done.stdout.strip(),'S1_STAGE_PASS')

    def test_broker_has_fixed_public_stage_and_no_arbitrary_private_path(self):
        text=(ROOT/BROKER).read_text()
        self.assertIn("STAGE_DIR='two-wave-segmentation-carrier-stage'",text)
        self.assertIn("PROFILE='two-wave-segmentation-carrier-qualification-v1'",text)
        self.assertNotIn('argparse',text);self.assertNotIn('CLOUD_CURRENT',text)
        self.assertNotIn('input(',text)

    def test_report_contract_is_aggregate_only(self):
        text=(ROOT/'executor/wave_segmentation_carrier_qualification_v1.py').read_text()
        for forbidden in ('timestamp_source_serialized','bar_index','occurrence_bar','candidate_occurrence_bar'):
            self.assertNotIn(forbidden,text)
        self.assertIn('file_metrics',text);self.assertIn('reconstruction',text);self.assertIn('common_support',text)

    def test_stage_and_broker_byte_budgets_are_bounded(self):
        protocol=json.loads(PROTOCOL.read_text())
        self.assertLessEqual(max(v['bytes'] for v in protocol['files'].values()),protocol['limits']['file_bytes_max'])
        self.assertLessEqual(sum(v['bytes'] for v in protocol['files'].values()),protocol['limits']['total_source_bytes_max'])
        self.assertLessEqual(protocol['limits']['result_bytes_max'],8*1024*1024)

    def test_controller_route_selects_standard_workflow_only(self):
        text=(ROOT/'.github/workflows/controller-dispatch.yml').read_text()
        self.assertIn('repos/staryocean0/csi1000-timing-strategy-public/actions/workflows/public-compute.yml/dispatches',text)
        self.assertNotIn('wave_segmentation_carrier_stage_public.py',text)
        self.assertNotIn('wave_segmentation_carrier_broker_v1.py',text)

    def test_workflow_stage_precedes_secret_prepare(self):
        steps=self.workflow()['jobs']['execute']['steps']
        names=[s['name'] for s in steps]
        self.assertLess(names.index('Stage fixed public Two-Wave segmentation carriers without private credentials'),
                        names.index('Prepare fixed private inputs'))

    def test_source_test_workflow_requires_no_skips(self):
        path=ROOT/'.github/workflows/wave-segmentation-carrier-qualification-tests.yml'
        if path.exists():
            text=path.read_text();self.assertIn('not result.skipped',text)
            self.assertNotIn('FACTORLAB_PRIVATE_TOKEN',text)


if __name__=='__main__':unittest.main()
