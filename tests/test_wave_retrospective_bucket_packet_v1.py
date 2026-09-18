import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'docs/research/TWO_WAVE_RETROSPECTIVE_BUCKET_PACKET_V1_PROTOCOL_20260918.json'
C=ROOT/'docs/research/TWO_WAVE_RETROSPECTIVE_BUCKET_PACKET_V1_CHECKPOINT_20260918.json'
class PacketV1(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=json.loads(P.read_text()); cls.c=json.loads(C.read_text())
 def test_packet_frozen_before_annotation(self):
  self.assertEqual(self.c['status'],'BLIND_PACKET_SOURCE_FROZEN_BEFORE_ANNOTATION')
  self.assertFalse(self.c['contamination_guards']['pass_a_started'])
  self.assertFalse(self.c['contamination_guards']['any_panel_annotation_seen_before_checkpoint'])
 def test_panel_counts_and_lag(self):
  self.assertEqual(self.c['packet']['panels'],352)
  self.assertEqual(self.c['packet']['primary'],192)
  self.assertEqual(self.c['packet']['challenge_total'],160)
  self.assertEqual(self.c['packet']['knowledge_lag_native_5m_bars'],8)
 def test_primary_is_year_balanced(self):
  self.assertEqual(set(self.c['packet']['primary_year_counts'].values()),{32})
 def test_no_old_label_or_outcome_sampling(self):
  g=self.c['contamination_guards']
  self.assertFalse(g['old_labels_visible_during_sampling']);self.assertFalse(g['recognizer_outputs_used_for_sampling']);self.assertFalse(g['outcomes_used']);self.assertFalse(g['pnl_used'])
 def test_final_gate_can_add_or_remove_bucket_before_freeze(self):
  self.assertIn('NEW_BUCKET_PROPOSAL',self.p['allowed_answers'])
  self.assertIn('TAXONOMY_UNRESOLVED',self.p['allowed_answers'])
  self.assertEqual(self.p['final_freeze_gate']['taxonomy_unresolved'],0)
  self.assertTrue(self.p['final_freeze_gate']['replay_after_any_new_bucket'])
if __name__=='__main__':unittest.main()
