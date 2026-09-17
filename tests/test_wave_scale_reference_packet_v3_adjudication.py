import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADJ=ROOT/"docs/research/TWO_WAVE_SCALE_REFERENCE_PACKET_V3_ADJUDICATION_20260917.json"
ANN=ROOT/"docs/research/TWO_WAVE_SCALE_REFERENCE_ANNOTATION_PROTOCOL_20260917.json"
class V3AdjudicationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.a=json.loads(ADJ.read_text());cls.p=json.loads(ANN.read_text())
 def test_formal_success_identity(self):
  self.assertEqual(self.a["formal_run"],"35209602753-1");self.assertEqual(self.a["public_source_sha"],"892cbd196f5d467921f9228e7dda6f2d6eb0f81e")
  self.assertEqual(self.a["decision"],"BLIND_PACKET_VERIFIED_READY_FOR_BLIND_ANNOTATION_LABELS_NOT_FROZEN")
  self.assertEqual(self.a["runner"]["event"],"workflow_dispatch");self.assertEqual(self.a["runner"]["status"],"success")
 def test_packet_and_verifier_counts(self):
  p=self.a["packet"];v=self.a["independent_verifier"]
  self.assertEqual((p["anchor_context_eligible_days"],p["primary_panels"],p["panel_files"]),(1414,192,576))
  self.assertEqual(p["anchor_context_exclusions"],{"context_causal_flat_fill":43,"context_support":1})
  self.assertEqual((v["status"],v["panels_verified"],v["panel_files_verified"]),("passed",192,576))
 def test_v2_packet_identity_equals_v3_but_v2_failure_preserved(self):
  self.assertTrue(self.a["history"]["v2_sample_and_packet_hashes_match_v3"]);self.assertIn("FAILED",self.a["history"]["v2_run"])
  self.assertEqual(self.a["packet"]["full_inventory_sha256"],"32f6279610def838474fb0bc4596c33dfb41f88e4fb78e4a20d6b39942446206")
 def test_no_label_or_score_promotion(self):
  self.assertFalse(self.a["labels"]["primary_reference_labels_frozen"]);self.assertFalse(self.a["labels"]["annotation_started"]);self.assertFalse(self.a["labels"]["future_suffix_revealed"]);self.assertFalse(self.a["diagnostic_scores_measured"]);self.assertIsNone(self.a["numeric_state_thresholds"]);self.assertFalse(self.a["production_authority"])
 def test_annotation_protocol_is_blind_pass_a_first(self):
  p=self.p;self.assertEqual(p["input_run"],"35209602753-1");self.assertEqual(p["pass_order"],["PASS_A_ALL_192_SEAL","PASS_B_ALL_192_FINAL_FREEZE"]);self.assertFalse(p["full_inventory_visible"]);self.assertFalse(p["calendar_date_visible"]);self.assertFalse(p["diagnostic_scores_visible"]);self.assertFalse(p["future_suffix_revealed_before_freeze"]);self.assertFalse(p["labels_frozen"])
 def test_annotation_vocabulary_and_transition(self):
  self.assertEqual(len(self.p["reference_states"]),6);self.assertEqual(len(self.p["reason_codes"]),8);self.assertEqual(self.p["max_compatible_segmentations"],2);self.assertEqual(self.p["max_turns_per_segmentation"],6);self.assertIn("DOWNGRADE",self.p["pass_b_allowed_transition"])
 def test_history_guard_and_current_authority(self):
  l=json.loads((ROOT/"docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json").read_text());raw=json.dumps(l["ordered_lineage"][:21],sort_keys=True,separators=(",",":")).encode();self.assertEqual(hashlib.sha256(raw).hexdigest(),self.a["history_guard"]["prior_21_lineage_sha256"]);self.assertEqual(l["ordered_lineage"][21]["formal_run"],"35209602753-1");self.assertEqual(l["ordered_lineage"][22]["issue"],369)
  a=json.loads((ROOT/"docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json").read_text());self.assertEqual(l["ordered_lineage"][22]["status"],"PASS_A_NOT_STARTED_LABELS_NOT_FROZEN");self.assertIsNone(a["S2_progress"]["market_thresholds"]);self.assertFalse(a["S2_progress"]["future_suffix_revealed"])
 def test_no_raw_annotation_file_published_yet(self):
  self.assertFalse((ROOT/"docs/research/TWO_WAVE_SCALE_REFERENCE_PRIMARY_LABELS_20260917.json").exists())
if __name__=="__main__":unittest.main()
