from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / 'docs/research/TWO_WAVE_CYCLE_IDENTIFIABILITY_V1_ADJUDICATION_NOTE_20260916.md'


class CycleIdentifiabilityAdjudicationNoteTests(unittest.TestCase):
    def test_no_retuning_boundary(self):
        text = NOTE.read_text(encoding='utf-8')
        self.assertIn('35084682048-1', text)
        self.assertIn('does not authorize changing the frozen 4/48 base detector', text)
        self.assertIn('does not authorize', text)
        self.assertIn('issue #315', text)
        self.assertIn('preserving lower-level reset metadata and causal clocks', text)


if __name__ == '__main__':
    unittest.main()
