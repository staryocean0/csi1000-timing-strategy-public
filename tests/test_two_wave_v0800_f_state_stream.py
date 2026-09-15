import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/research/TWO_WAVE_V0800_F_OPERATIONAL_STATE_STREAM_AUDIT_PROTOCOL.json"
NOTE = ROOT / "docs/research/TWO_WAVE_V0800_F_OPERATIONAL_STATE_STREAM_AUDIT_PROTOCOL.md"
PRODUCER = ROOT / "executor/two_wave_v0800_f_state_stream.py"
VERIFIER = ROOT / "executor/two_wave_v0800_f_state_stream_verifier.py"
BROKER = ROOT / "executor/two_wave_v0800_f_state_stream_broker.py"
MIRROR = ROOT / "executor/two_wave_v0800_f_state_stream_private_mirror.py"
WORKFLOW = ROOT / ".github/workflows/public-compute.yml"
CONTROLLER = ROOT / ".github/workflows/controller-dispatch.yml"
PROFILE = "two-wave-v0800-f-operational-state-stream-audit-v1"
CONTROLLER_TITLE = "controller: two-wave-v0800-f-operational-state-stream-audit-v1"


class TwoWaveV0800FStateStreamTest(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))

    def test_sources_parse_without_runtime_imports(self):
        for path in (PRODUCER, VERIFIER, BROKER, MIRROR):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_parent_and_parameters_are_frozen(self):
        parent = self.protocol["parent_adjudication"]
        self.assertEqual(parent["verified_e_run"], "34971340135-1")
        self.assertEqual(parent["audit_manifest_sha256"], "c3260be7f72a12a5da0b33d1fb23deacd32d967d83e45f480d0363ca2e836ab5")
        sem = self.protocol["frozen_semantics"]
        self.assertEqual(sem["rho_symbolic"], "sqrt(2)")
        self.assertAlmostEqual(sem["tau"], 0.20)
        self.assertAlmostEqual(sem["kappa"], 2.00)
        self.assertFalse(sem["parameter_search_allowed"])

    def test_primary_stream_keeps_scale_mismatch_events_and_no_carry_forward(self):
        stream = self.protocol["event_stream_contract"]
        self.assertEqual(stream["primary_stream"], "all_strict_pair_confirmation_events")
        self.assertEqual(stream["expected_strict_pair_count"], 2358)
        self.assertEqual(stream["expected_eligible_same_scale_pair_count"], 924)
        self.assertEqual(stream["scale_mismatch_state"], "NoStateScaleMismatch")
        self.assertTrue(stream["scale_mismatch_is_not_uncertain"])
        self.assertTrue(stream["epoch_boundary_breaks_sequence"])
        self.assertFalse(stream["bar_time_carry_forward"])
        self.assertEqual(stream["between_event_state"], "undefined")
        self.assertEqual(stream["eligible_only_stream"], "secondary_diagnostic_only")
        self.assertTrue(stream["eligible_only_stream_must_report_intervening_strict_events"])

    def test_producer_implements_all_strict_primary_stream(self):
        text = PRODUCER.read_text(encoding="utf-8")
        self.assertIn('if len(ordered) != 2358', text)
        self.assertIn('!= 924', text)
        self.assertIn('state = "NoStateScaleMismatch"', text)
        self.assertIn('intervening_strict_events_since_previous_eligible', text)
        self.assertIn('"bar_time_carry_forward": False', text)
        self.assertIn('"between_event_state": "undefined"', text)
        self.assertNotIn("future_return", text.lower())
        self.assertNotIn("trade_simulation", text.lower())

    def test_verifier_reenumerates_with_independent_engine(self):
        text = VERIFIER.read_text(encoding="utf-8")
        self.assertIn("TemporalMaturityAEngine", text)
        self.assertNotIn("from two_wave_v0800_f_state_stream import", text)
        self.assertIn("strict_pair_count_mismatch", text)
        self.assertIn("eligible_pair_count_mismatch", text)
        self.assertIn("epoch_transition_boundary_verified", text)

    def test_verifier_ratio_check_is_roundtrip_safe_without_weakening_state_check(self):
        text = VERIFIER.read_text(encoding="utf-8")
        self.assertIn('float_precision="round_trip"', text)
        self.assertIn('for col in ("duration_ratio", "g_previous", "g_current")', text)
        self.assertIn('derived = slope_ratio(float(row["g_previous"]), float(row["g_current"]))', text)
        self.assertIn('math.isclose(reported, derived, rel_tol=1e-12, abs_tol=1e-12)', text)
        self.assertNotIn('for col in ("duration_ratio", "g_previous", "g_current", "slope_magnitude_ratio")', text)
        self.assertIn('"previous_descriptor", "current_descriptor", "state")', text)

    def test_broker_pins_consumed_development_identity(self):
        text = BROKER.read_text(encoding="utf-8")
        self.assertIn(f'PROFILE_NAME = "{PROFILE}"', text)
        self.assertIn('SOURCE_REF = "152ae1ef11a04bb3b434da25025794db7a706c81"', text)
        self.assertIn('DATA_BYTES = 3351411', text)
        self.assertIn('bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48', text)
        self.assertIn('GITHUB_EVENT_NAME") != "workflow_dispatch"', text)
        self.assertIn('GITHUB_REF") != "refs/heads/cloud-workspace-v1"', text)
        self.assertIn('"new_training": False', text)
        self.assertIn('"production_authority": False', text)

    def test_private_mirror_is_aggregate_only(self):
        text = MIRROR.read_text(encoding="utf-8")
        self.assertIn('TEXT_OUTPUTS = ("SUMMARY.json", "INPUT_RECEIPT.json")', text)
        self.assertNotIn('STATE_STREAM_EVENTS.csv', text)
        self.assertIn('bar_time_carry_forward', text)
        self.assertIn('post_run_adjudication_required', text)

    def test_standard_workflow_routes_exact_profile_once_per_phase(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(text.count(f"          - {PROFILE}\n"), 1)
        self.assertEqual(text.count(f"inputs.profile == '{PROFILE}'"), 2)
        self.assertEqual(text.count(f"python3 executor/two_wave_v0800_f_state_stream_broker.py prepare {PROFILE}"), 1)
        self.assertEqual(text.count(f"python3 executor/two_wave_v0800_f_state_stream_broker.py compute {PROFILE}"), 1)
        self.assertEqual(text.count(f"python3 executor/two_wave_v0800_f_state_stream_broker.py cleanup {PROFILE}"), 1)
        self.assertEqual(text.count(f"python3 executor/two_wave_v0800_f_state_stream_broker.py publish {PROFILE}"), 1)
        self.assertEqual(text.count("python3 executor/two_wave_v0800_f_state_stream_private_mirror.py"), 1)
        self.assertIn("on:\n  workflow_dispatch:", text)

    def test_controller_routes_only_exact_f_title(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertEqual(text.count(CONTROLLER_TITLE), 3)
        self.assertEqual(text.count(f"profile='{PROFILE}'"), 1)
        self.assertEqual(text.count("github.event.issue.number == 227"), 1)
        self.assertEqual(text.count("github.event.action == 'reopened'"), 1)
        self.assertIn("github.event.issue.user.login == github.repository_owner", text)
        self.assertIn("public-compute.yml/dispatches", text)
        self.assertIn("-f ref='cloud-workspace-v1'", text)

    def test_scope_remains_non_outcome_non_authoritative(self):
        self.assertFalse(self.protocol["input"]["year_2026_allowed"])
        forbidden = self.protocol["forbidden"]
        for key in ("future_returns", "pnl", "positions", "costs", "trade_simulation", "parameter_tuning", "bar_time_state_holding", "direction_acceptance", "state_publication_authority", "trade_authority", "production_authority"):
            self.assertTrue(forbidden[key])
        note = NOTE.read_text(encoding="utf-8")
        self.assertIn("does **not** install a carry-forward rule", note)
        self.assertIn("NoStateScaleMismatch", note)
        self.assertIn("separate post-run adjudication", note)


if __name__ == "__main__":
    unittest.main()
