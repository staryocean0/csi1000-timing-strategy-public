import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/research/TWO_WAVE_RETROSPECTIVE_BUCKET_TAXONOMY_V1_PROTOCOL_20260918.json"
AUDIT = ROOT / "docs/research/TWO_WAVE_RETROSPECTIVE_BUCKET_TAXONOMY_FIRST_PASS_AUDIT_20260918.json"

class RetrospectiveBucketTaxonomyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = json.loads(PROTOCOL.read_text())
        cls.a = json.loads(AUDIT.read_text())

    def test_amplitude_is_not_bucket_definition(self):
        self.assertFalse(self.p["amplitude_is_bucket_definition"])

    def test_working_taxonomy_has_six_explicit_buckets(self):
        buckets = self.p["provisional_buckets"]
        self.assertEqual([b["id"] for b in buckets], ["B0","B1","B2","B3","B4","B5"])
        self.assertEqual(self.a["working_bucket_count"], 6)
        self.assertFalse(self.a["working_bucket_count_is_final"])

    def test_three_bucket_hypothesis_is_rejected_by_frozen_reference(self):
        x = self.a["frozen_reference_192"]
        self.assertEqual(x["current_scale_total"], 136)
        self.assertEqual(x["residual_total"], 56)
        self.assertEqual(x["residual_reason_counts"]["REPEATED_SHORTER_STRUCTURE"], 24)
        self.assertEqual(x["residual_reason_counts"]["MIXED_SCALE_COMPETITION"], 13)
        self.assertEqual(x["residual_reason_counts"]["DISCONTINUITY_OR_OUTLIER"], 19)
        self.assertIn("THREE_BUCKET_AMPLITUDE_TAXONOMY_REJECTED", self.a["decision"])

    def test_taxonomy_stop_gate_precedes_recognizer(self):
        g = self.p["taxonomy_stop_gate"]
        self.assertEqual(g["unresolved_final"], 0)
        self.assertEqual(g["conflict_final"], 0)
        self.assertTrue(g["exactly_one_bucket_per_interval"])
        self.assertTrue(g["two_blinded_passes_plus_adjudication"])
        self.assertFalse(g["candidate_outputs_visible"])
        self.assertFalse(g["outcomes_or_pnl_visible"])

    def test_eight_bar_delayed_identity_is_downstream_gate(self):
        r = self.p["recognizer_entry_gate"]
        self.assertEqual(r["delayed_endpoint_bars_5m"], 8)
        self.assertEqual(r["delayed_endpoint_identity_required"], 1.0)
        self.assertTrue(r["taxonomy_frozen_first"])

if __name__ == "__main__":
    unittest.main()
