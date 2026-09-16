import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/research/TWO_WAVE_CYCLE_IDENTIFIABILITY_V1_ADJUDICATION_CHECKPOINT_20260916.json'


class CycleIdentifiabilityCheckpointTests(unittest.TestCase):
    def test_checkpoint(self):
        r = json.loads(DOC.read_text(encoding='utf-8'))
        self.assertEqual(r['formal_run'], '35084682048-1')
        self.assertEqual(r['primary_observed_failure_mode'], 'RESET_ROOT_BREAK')
        self.assertEqual(r['blind_episode_count'], 146)
        self.assertEqual(r['reset_root_break_count'], 144)
        self.assertEqual(r['Q1_blind_episode_count'], 0)
        self.assertEqual(r['Q4_blind_episode_count'], 126)
        self.assertEqual(r['hard_root_C2_blind_location'], 'UNRESOLVED')
        self.assertFalse(r['standalone_C2_phase_signal_accepted'])
        self.assertEqual(r['next_gate_issue'], 315)
        self.assertFalse(r['one_minute_same_span_requested_now'])
        self.assertTrue(r['one_minute_future_faster_base_experiment_allowed_in_principle'])
        self.assertTrue(all(v is False for v in r['authority'].values()))


if __name__ == '__main__':
    unittest.main()
