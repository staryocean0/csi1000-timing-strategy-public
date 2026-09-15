import json
import math
import py_compile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/research/TWO_WAVE_V0800_D_DIRECTION_GRID_PROTOCOL.json"
NOTE = ROOT / "docs/research/TWO_WAVE_V0800_D_DIRECTION_GRID_PROTOCOL.md"
PRODUCER = ROOT / "executor/two_wave_v0800_d_direction_grid.py"
VERIFIER = ROOT / "executor/two_wave_v0800_d_direction_grid_verifier.py"
BROKER = ROOT / "executor/two_wave_v0800_d_direction_grid_broker.py"
MIRROR = ROOT / "executor/two_wave_v0800_d_direction_grid_private_mirror.py"
WORKFLOW = ROOT / ".github/workflows/public-compute.yml"
CONTROLLER = ROOT / ".github/workflows/controller-dispatch.yml"
PROFILE = "two-wave-v0800-d-direction-grid-v1"
CONTROLLER_TITLE = "controller: two-wave-v0800-d-direction-grid-v1"


class TwoWaveV0800DDirectionGridTest(unittest.TestCase):
    def test_protocol_freezes_upstream_semantics_and_grid(self):
        value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        self.assertEqual(value["study"], "V0800-D_TWO_WAVE_DIRECTION_GRID")
        universe = value["causal_pair_universe"]
        self.assertEqual(universe["producer"], "PrefixReplayAEngine")
        self.assertEqual(universe["knowledge_time"], "current_A_wave_confirmation_bar")
        self.assertEqual(universe["continuity"], "shared_anchor_strict_L-H-L-H-L")
        self.assertAlmostEqual(universe["same_scale_rho"], math.sqrt(2.0))
        self.assertFalse(universe["skip_based_pairs_allowed"])
        self.assertFalse(universe["legacy_rho_2_evaluated"])
        grid = value["frozen_grid"]
        self.assertEqual(grid["taus"], [0.05, 0.10, 0.15, 0.20])
        self.assertEqual(grid["kappas"], [1.25, 1.50, 2.00])
        self.assertEqual(grid["combinations"], 12)

    def test_sources_compile_without_importing_heavy_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            for source in (PRODUCER, VERIFIER, BROKER, MIRROR):
                py_compile.compile(str(source), cfile=str(Path(tmp) / (source.name + ".pyc")), doraise=True)

    def test_producer_uses_causal_engine_sqrt2_and_no_outcome_objective(self):
        text = PRODUCER.read_text(encoding="utf-8")
        self.assertIn("PrefixReplayAEngine", text)
        self.assertIn("RHO = math.sqrt(2.0)", text)
        self.assertIn("CANDIDATE_TAUS", text)
        self.assertIn("CANDIDATE_KAPPAS", text)
        self.assertIn('"tau_winner": None', text)
        self.assertIn('"kappa_winner": None', text)
        self.assertIn('"automatic_selection_used": False', text)
        for forbidden in ("forward_return", "future_return", "transaction_cost", "position_size", "sharpe", "drawdown"):
            self.assertNotIn(forbidden, text.lower())

    def test_verifier_is_independent_from_producer_pair_enumeration(self):
        text = VERIFIER.read_text(encoding="utf-8")
        self.assertIn("TemporalMaturityAEngine", text)
        self.assertNotIn("PrefixReplayAEngine", text)
        self.assertIn("expected_grid", text)
        self.assertIn("compare_grid", text)
        self.assertIn('"direction_grid_mismatches": 0', text)
        self.assertIn('"direction_acceptance": False', text)

    def test_broker_pins_consumed_development_identity(self):
        text = BROKER.read_text(encoding="utf-8")
        self.assertIn(PROFILE, text)
        self.assertIn("152ae1ef11a04bb3b434da25025794db7a706c81", text)
        self.assertIn("bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48", text)
        self.assertIn("DATA_BYTES = 3351411", text)
        self.assertIn("workflow_dispatch", text)
        self.assertIn('"new_training": False', text)
        self.assertIn('"production_authority": False', text)

    def test_mirror_is_aggregate_only_and_no_parameter_promotion(self):
        text = MIRROR.read_text(encoding="utf-8")
        self.assertIn('TEXT_OUTPUTS = ("SUMMARY.json", "INPUT_RECEIPT.json")', text)
        self.assertNotIn("DIRECTION_GRID_EVENTS.csv", text)
        self.assertIn("tau_winner", text)
        self.assertIn("kappa_winner", text)
        self.assertIn("post_run_adjudication_required", text)

    def test_protocol_forbids_automatic_winner_and_authority(self):
        value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        selection = value["selection_policy"]
        self.assertIsNone(selection["tau_winner"])
        self.assertIsNone(selection["kappa_winner"])
        for key in ("automatic_selection_by_max_coverage", "automatic_selection_by_min_uncertain", "automatic_selection_by_state_balance", "automatic_selection_by_returns_or_pnl"):
            self.assertFalse(selection[key])
        self.assertTrue(selection["separate_post_run_adjudication_required"])
        authority = value["authority"]
        self.assertFalse(authority["direction_acceptance"])
        self.assertFalse(authority["state_publication_authority"])
        self.assertFalse(authority["trade_authority"])
        self.assertFalse(authority["production_authority"])

    def test_standard_workflow_routes_exact_profile_through_all_phases(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(f"- {PROFILE}", text)
        for phase in ("prepare", "compute", "cleanup", "publish"):
            self.assertIn(
                f"python3 executor/two_wave_v0800_d_direction_grid_broker.py {phase} {PROFILE}",
                text,
            )
        self.assertIn("python3 executor/two_wave_v0800_d_direction_grid_private_mirror.py", text)
        self.assertEqual(text.count("secrets.FACTORLAB_PRIVATE_TOKEN"), 2)
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:\n", text)

    def test_controller_is_exact_owner_only_dispatch_not_compute(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn(f"github.event.issue.title == '{CONTROLLER_TITLE}'", text)
        self.assertIn(f"'{CONTROLLER_TITLE}')", text)
        self.assertIn(f"profile='{PROFILE}'", text)
        self.assertIn("github.event.issue.user.login == github.repository_owner", text)
        self.assertIn("actions/workflows/public-compute.yml/dispatches", text)
        self.assertNotIn("two_wave_v0800_d_direction_grid.py", text)
        self.assertNotIn("two_wave_v0800_d_direction_grid_broker.py", text)

    def test_human_protocol_keeps_first_d_run_morphology_only(self):
        text = NOTE.read_text(encoding="utf-8")
        self.assertIn("One wave never publishes a market state", text)
        self.assertIn("No automatic winner", text)
        self.assertIn("does not read future outcomes or returns", text)
        self.assertIn("does not by itself grant direction publication authority", text)


if __name__ == "__main__":
    unittest.main()
