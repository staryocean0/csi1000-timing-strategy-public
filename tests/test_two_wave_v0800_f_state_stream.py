import json
import py_compile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "two-wave-v0800-f-state-stream-audit-v1"
TITLE = "controller: two-wave-v0800-f-state-stream-audit-v1"
PROTOCOL = ROOT / "docs/research/TWO_WAVE_V0800_F_STATE_STREAM_PROTOCOL.json"
NOTE = ROOT / "docs/research/TWO_WAVE_V0800_F_STATE_STREAM_PROTOCOL.md"
PRODUCER = ROOT / "executor/two_wave_v0800_f_state_stream.py"
VERIFIER = ROOT / "executor/two_wave_v0800_f_state_stream_verifier.py"
BROKER = ROOT / "executor/two_wave_v0800_f_state_stream_broker.py"
MIRROR = ROOT / "executor/two_wave_v0800_f_state_stream_private_mirror.py"
WORKFLOW = ROOT / ".github/workflows/public-compute.yml"
CONTROLLER = ROOT / ".github/workflows/controller-dispatch.yml"


class TwoWaveV0800FStateStreamTest(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))

    def test_protocol_freezes_post_e_operational_semantics(self):
        self.assertEqual(self.protocol["study"], "V0800-F_OPERATIONAL_STATE_STREAM_AUDIT")
        frozen = self.protocol["frozen_semantics"]
        self.assertEqual(frozen["rho_symbolic"], "sqrt(2)")
        self.assertEqual(frozen["tau"], 0.20)
        self.assertEqual(frozen["kappa"], 2.00)
        self.assertFalse(frozen["parameter_search_allowed"])
        self.assertEqual(self.protocol["parent_adjudication"]["source_run_id"], "34971340135-1")
        self.assertEqual(self.protocol["input"]["sha256"], "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48")
        self.assertFalse(self.protocol["input"]["year_2026_allowed"])

    def test_protocol_freezes_overlap_invariant_and_no_outcomes(self):
        adjacency = self.protocol["overlap_adjacency"]
        self.assertTrue(adjacency["shared_wave_descriptor_must_match"])
        self.assertEqual(adjacency["forbidden_direct_published_transitions"], ["UpTrend->DownTrend", "DownTrend->UpTrend"])
        policy = self.protocol["adjudication_policy"]
        self.assertTrue(policy["hard_structural_failure_if_shared_descriptor_mismatch"])
        self.assertTrue(policy["hard_structural_failure_if_direct_opposite_published_transition"])
        self.assertFalse(policy["automatic_state_stream_acceptance"])
        self.assertTrue(policy["post_run_semantic_adjudication_required"])
        for value in self.protocol["forbidden"].values():
            self.assertTrue(value)

    def test_sources_compile_without_runtime_imports(self):
        for path in (PRODUCER, VERIFIER, BROKER, MIRROR):
            py_compile.compile(str(path), doraise=True)

    def test_producer_is_fixed_parameter_reason_partition_only(self):
        text = PRODUCER.read_text(encoding="utf-8")
        self.assertIn("TAU = 0.20", text)
        self.assertIn("KAPPA = 2.00", text)
        self.assertIn("EXPECTED_STRICT_PAIRS = 2358", text)
        self.assertIn("EXPECTED_ELIGIBLE_PAIRS = 924", text)
        for reason in self.protocol["event_stream"]["reason_partition"]:
            self.assertIn(reason, text)
        self.assertIn("state_stream_acceptance\": None", text)
        lowered = text.lower()
        self.assertNotIn("future_return", lowered.replace("future returns", ""))
        self.assertNotIn("profit", lowered)

    def test_verifier_independently_reenumerates_strict_pairs(self):
        text = VERIFIER.read_text(encoding="utf-8")
        self.assertIn("TemporalMaturityAEngine", text)
        self.assertNotIn("PrefixReplayAEngine", text)
        self.assertIn("shared_descriptor_structural_invariant_failed", text)
        self.assertIn("direct_opposite_trend_structural_invariant_failed", text)
        self.assertIn("candidate.wave.end_bar == current.start_bar", text)

    def test_broker_pins_consumed_development_identity(self):
        text = BROKER.read_text(encoding="utf-8")
        self.assertIn(f'PROFILE_NAME = "{PROFILE}"', text)
        self.assertIn('SOURCE_REF = "152ae1ef11a04bb3b434da25025794db7a706c81"', text)
        self.assertIn('DATA_SHA256 = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"', text)
        self.assertIn('e.get("GITHUB_EVENT_NAME") != "workflow_dispatch"', text)
        self.assertIn('e.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"', text)

    def test_private_mirror_is_aggregate_only_and_unaccepted(self):
        text = MIRROR.read_text(encoding="utf-8")
        self.assertIn('TEXT_OUTPUTS = ("SUMMARY.json", "INPUT_RECEIPT.json")', text)
        self.assertNotIn("STATE_STREAM_EVENTS.csv", text)
        self.assertIn('value.get("state_stream_acceptance") is not None', text)
        self.assertIn('value.get("direct_opposite_trend_transition_count", -1)) != 0', text)

    def test_standard_workflow_routes_exact_f_profile(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(f"- {PROFILE}", text)
        for phase in ("prepare", "compute", "cleanup", "publish"):
            command = f"python3 executor/two_wave_v0800_f_state_stream_broker.py {phase} {PROFILE}"
            self.assertEqual(text.count(command), 1)
        self.assertEqual(text.count("python3 executor/two_wave_v0800_f_state_stream_private_mirror.py"), 1)

    def test_controller_routes_only_exact_f_title(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertEqual(text.count(TITLE), 2)
        self.assertEqual(text.count(f"profile='{PROFILE}'"), 1)
        self.assertIn("actions/workflows/public-compute.yml/dispatches", text)
        self.assertIn("-f ref='cloud-workspace-v1'", text)

    def test_human_protocol_keeps_next_decision_post_run_and_nonoutcome(self):
        note = NOTE.read_text(encoding="utf-8")
        self.assertIn("Direct overlap-adjacent transitions", note)
        self.assertIn("structurally impossible", note)
        self.assertIn("No numerical persistence or churn cutoff is invented", note)
        self.assertIn("state_stream_acceptance` remains unset", note)
        self.assertIn("may not read 2026 data", note)


if __name__ == "__main__":
    unittest.main()
