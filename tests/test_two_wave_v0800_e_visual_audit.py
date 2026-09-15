import json
import py_compile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/research/TWO_WAVE_V0800_E_MORPHOLOGY_VISUAL_AUDIT_PROTOCOL.json"
NOTE = ROOT / "docs/research/TWO_WAVE_V0800_E_MORPHOLOGY_VISUAL_AUDIT_PROTOCOL.md"
PRODUCER = ROOT / "executor/two_wave_v0800_e_visual_audit.py"
VERIFIER = ROOT / "executor/two_wave_v0800_e_visual_audit_verifier.py"
BROKER = ROOT / "executor/two_wave_v0800_e_visual_audit_broker.py"
MIRROR = ROOT / "executor/two_wave_v0800_e_visual_audit_private_mirror.py"
WORKFLOW = ROOT / ".github/workflows/public-compute.yml"
CONTROLLER = ROOT / ".github/workflows/controller-dispatch.yml"
PROFILE = "two-wave-v0800-e-morphology-visual-audit-v1"


class TwoWaveV0800EVisualAuditTest(unittest.TestCase):
    def test_protocol_freezes_categories_sampling_and_causal_window(self):
        value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        self.assertEqual(value["study"], "V0800-E_MORPHOLOGY_VISUAL_AUDIT")
        self.assertEqual(value["frozen_semantics"]["operational_rho_symbolic"], "sqrt(2)")
        self.assertEqual(value["category_assignment"]["exclusive_priority"], ["stable_consensus", "kappa_sensitive", "tau_sensitive", "sign_conflict", "persistent_uncertain"])
        sampling = value["sampling"]
        self.assertEqual(sampling["target_per_category_year"], 2)
        self.assertEqual(sampling["years"], [2015, 2016, 2017, 2018, 2019, 2020])
        self.assertEqual(sampling["maximum_cases"], 60)
        self.assertFalse(sampling["cherry_pick_allowed"])
        self.assertFalse(value["visual_window"]["bars_after_confirmation_allowed"])
        self.assertEqual(value["visual_window"]["last_bar"], "current_A_wave_confirmation_bar")

    def test_sources_compile_without_importing_runtime_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            for source in (PRODUCER, VERIFIER, BROKER, MIRROR):
                py_compile.compile(str(source), cfile=str(Path(tmp) / (source.name + ".pyc")), doraise=True)

    def test_producer_has_deterministic_hash_sampling_and_no_future_window(self):
        text = PRODUCER.read_text(encoding="utf-8")
        self.assertIn('hashlib.sha256(f"V0800-E-v1|{category}|{year}|{pair_id}"', text)
        self.assertIn("bars.iloc[start : confirmation + 1]", text)
        self.assertIn('class="bar" data-bar-index=', text)
        self.assertIn('"tau_winner": None', text)
        self.assertIn('"kappa_winner": None', text)
        for forbidden in ("forward_return", "future_return", "transaction_cost", "position_size", "sharpe", "drawdown"):
            self.assertNotIn(forbidden, text.lower())

    def test_verifier_independently_rebuilds_pairs_categories_samples_and_svg_scope(self):
        text = VERIFIER.read_text(encoding="utf-8")
        self.assertIn("TemporalMaturityAEngine", text)
        self.assertNotIn("two_wave_v0800_e_visual_audit import", text)
        self.assertIn("expected_records", text)
        self.assertIn("expected_selection", text)
        self.assertIn("svg_bar_window_mismatch", text)
        self.assertIn("svg_future_bar_visible", text)
        self.assertIn('"selected_case_set_exact_match": True', text)

    def test_broker_pins_consumed_development_identity(self):
        text = BROKER.read_text(encoding="utf-8")
        self.assertIn(PROFILE, text)
        self.assertIn("152ae1ef11a04bb3b434da25025794db7a706c81", text)
        self.assertIn("bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48", text)
        self.assertIn("DATA_BYTES = 3351411", text)
        self.assertIn("workflow_dispatch", text)
        self.assertIn('"new_training": False', text)
        self.assertIn('"production_authority": False', text)

    def test_private_mirror_is_bounded_and_excludes_row_level_and_visual_files(self):
        text = MIRROR.read_text(encoding="utf-8")
        self.assertIn('"SUMMARY.json", "INPUT_RECEIPT.json", "AUDIT_MANIFEST.json", "AUDIT_REPORT.md"', text)
        self.assertNotIn("AUDIT_CASES.csv", text)
        self.assertNotIn("visuals/", text)
        self.assertIn("premature_parameter_winner", text)

    def test_no_parameter_or_direction_authority(self):
        value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        selection = value["selection_policy"]
        self.assertIsNone(selection["tau_winner"])
        self.assertIsNone(selection["kappa_winner"])
        self.assertFalse(selection["automatic_parameter_promotion"])
        self.assertFalse(selection["visual_audit_may_directly_install_winner"])
        authority = value["authority"]
        for key in ("future_outcome_used", "returns_used", "pnl_used", "positions_used", "year_2026_read", "direction_acceptance", "state_publication_authority", "trade_authority", "production_authority"):
            self.assertFalse(authority[key])

    def test_human_protocol_forbids_post_confirmation_and_outcome_peeking(self):
        text = NOTE.read_text(encoding="utf-8")
        self.assertIn("No bar after the confirmation bar may be displayed", text)
        self.assertIn("No future return", text)
        self.assertIn("Cherry-picking is prohibited", text)
        self.assertIn("separate post-audit adjudication", text)

    def test_source_only_stage_has_no_execution_route_yet(self):
        self.assertNotIn(PROFILE, WORKFLOW.read_text(encoding="utf-8"))
        self.assertNotIn(f"controller: {PROFILE}", CONTROLLER.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
