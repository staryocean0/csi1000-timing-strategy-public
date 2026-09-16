import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/research/TWO_WAVE_CYCLE_IDENTIFIABILITY_V1_ADJUDICATION_20260916.json'


class CycleIdentifiabilityAdjudicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = json.loads(DOC.read_text(encoding='utf-8'))

    def test_formal_run_identity(self):
        r = self.r['formal_run']
        self.assertEqual(r['run_id'], '35084682048-1')
        self.assertEqual(r['public_source_sha'], '0e98f6bfa67b8a0c1e040fb69beeaa479d6f5d88')
        self.assertEqual(r['profile'], 'two-wave-cycle-identifiability-v1')
        self.assertEqual(r['receipt_status'], 'passed')
        self.assertFalse(r['new_training'])
        self.assertFalse(r['production_authority'])

    def test_blindness_is_structural_not_tiny_noise(self):
        b = self.r['blind_episode_result']
        self.assertEqual(b['reason_counts']['RESET_ROOT_BREAK'], 144)
        self.assertEqual(b['Q1_count'], 0)
        self.assertGreater(b['Q4_fraction'], 0.85)
        self.assertGreater(b['Q3_or_Q4_fraction'], 0.96)
        self.assertGreater(b['episode_length_T0']['median'], 3.0)

    def test_current_hard_root_c2_cannot_locate_blindness(self):
        c = self.r['retrospective_C2']
        self.assertEqual(c['all_blind_episodes_C2_location'], 'UNRESOLVED')
        self.assertEqual(c['blind_bars_inside_completed_hard_root_C2_cells'], 0)
        self.assertFalse(self.r['causal_C2']['phase_signal_accepted'])

    def test_next_gate_and_authority(self):
        a = self.r['adjudication']
        self.assertTrue(a['root_fragmentation_is_primary_observed_failure_mode'])
        self.assertTrue(a['substantial_amplitude_blindness_present'])
        self.assertEqual(a['next_research_gate'], 315)
        self.assertFalse(a['detector_repair_authorized'])
        self.assertFalse(self.r['one_minute_data']['requested_now'])
        self.assertTrue(all(v is False for v in self.r['authority'].values()))


if __name__ == '__main__':
    unittest.main()
