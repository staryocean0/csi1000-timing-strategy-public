"""Source-only route tests. No market inputs, credentials, dispatch or private writes."""
import hashlib,json
from pathlib import Path
import unittest
import yaml
ROOT=Path(__file__).resolve().parents[1]
PROFILE='two-wave-r1-residual-clock-audit-v1'
OLD='two-wave-recognizer-r1-progress-reset-v1'
LATER='two-wave-recognizer-r2-eligible-counter-v1'

def blob(text):
    raw=text.encode();return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

def strip_later_workflow(text):
    text=text.replace('          - '+LATER+'\n','').replace(" || inputs.profile == '"+LATER+"'",'')
    for phase in ('prepare','compute','cleanup','publish'):
        addition="          elif [ '${{ inputs.profile }}' = '"+LATER+"' ]; then\n            python3 executor/wave_recognizer_r2_v1_broker.py "+phase+' '+LATER+'\n'
        if text.count(addition)!=1:
            raise AssertionError('later R2 workflow route is not exact for '+phase)
        text=text.replace(addition,'')
    return text

def strip_later_controller(text):
    addition="       github.event.issue.title == 'controller: "+LATER+"' ||\n"
    if text.count(addition)!=1:raise AssertionError('later R2 controller allowlist is not exact')
    text=text.replace(addition,'')
    case="            'controller: "+LATER+"')\n              profile='"+LATER+"'\n              ;;\n"
    if text.count(case)!=1:raise AssertionError('later R2 controller case is not exact')
    return text.replace(case,'')

class ResidualRouteTests(unittest.TestCase):
    def test_standard_workflow_only_new_exact_route(self):
        text=strip_later_workflow((ROOT/'.github/workflows/public-compute.yml').read_text())
        back=text.replace('          - '+PROFILE+'\n','').replace(" || inputs.profile == '"+PROFILE+"'",'')
        for phase in ('prepare','compute','cleanup','publish'):
            addition="          elif [ '${{ inputs.profile }}' = '"+PROFILE+"' ]; then\n            python3 executor/wave_recognizer_r1_residual_broker_v1.py "+phase+' '+PROFILE+'\n'
            self.assertEqual(back.count(addition),1);back=back.replace(addition,'')
        self.assertEqual(blob(back),'89b4e5dd185e712c21d4c9aa495ac49c614ca27c')
    def test_controller_only_new_exact_title(self):
        text=strip_later_controller((ROOT/'.github/workflows/controller-dispatch.yml').read_text())
        addition="       github.event.issue.title == 'controller: "+PROFILE+"' ||\n"
        self.assertEqual(text.count(addition),1);text=text.replace(addition,'')
        case="            'controller: "+PROFILE+"')\n              profile='"+PROFILE+"'\n              ;;\n"
        self.assertEqual(text.count(case),1);text=text.replace(case,'')
        self.assertEqual(blob(text),'6a3dbc3895a391c4335750ca42c9633a63973282')
    def test_all_phases_and_no_compute_credentials(self):
        doc=yaml.load((ROOT/'.github/workflows/public-compute.yml').read_text(),Loader=yaml.BaseLoader)
        self.assertEqual(set(doc['on']),{'workflow_dispatch'})
        self.assertEqual(doc['on']['workflow_dispatch']['inputs']['profile']['options'].count(PROFILE),1)
        steps=doc['jobs']['execute']['steps']
        phases=[s for s in steps if 'wave_recognizer_r1_residual_broker_v1.py' in s.get('run','')]
        self.assertEqual(len(phases),4)
        self.assertIn(PROFILE,phases[0]['if']);self.assertIn(PROFILE,phases[1]['if'])
        self.assertNotIn('env',phases[1]);self.assertNotIn('env',phases[2])
        self.assertIn("steps.cleanup.outcome == 'success'",phases[3]['if'])
    def test_protocol_keeps_frozen_R1_and_readiness(self):
        p=json.loads((ROOT/'executor/wave_recognizer_r1_residual_protocol_v1.json').read_text())
        self.assertEqual(p['readiness_issue'],321);self.assertEqual(p['research_issue'],334)
        self.assertEqual(p['frozen_R1_blob'],'32ffb3db77a7861f88ba6332809072d00b3a78a6')
        self.assertEqual(p['frozen_population']['new_blind_bars'],92)
        self.assertFalse(p['R2_selected']);self.assertFalse(p['one_minute_admitted']);self.assertFalse(any(p['authority'].values()))

if __name__=='__main__':unittest.main()
