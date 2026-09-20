import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEPT = (
    ROOT
    / "docs/research/TWO_WAVE_MODEL_B_P128_STATE_EXIT_EXECUTION_ACCEPTANCE_20260920.json"
)
HISTORY = ROOT / "docs/research/TWO_WAVE_STRATEGY_EVOLUTION_HISTORY_20260920.md"


class ModelBP128ExecutionAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(ACCEPT.read_text(encoding="utf-8"))

    def test_scientific_verdict_and_first_complete_identity_are_fixed(self):
        self.assertEqual(self.value["issue"], 635)
        self.assertEqual(
            self.value["scientific_verdict"],
            "MODEL_B_P128_STATE_EXIT_INCREMENT_NOT_SUPPORTED",
        )
        run = self.value["first_complete_run"]
        self.assertEqual(run["workflow_run_id"], 35500372173)
        self.assertEqual(run["verified_rows"], 29713)
        self.assertEqual(run["verified_blocks"], 38)
        release = self.value["first_complete_private_release"]
        self.assertEqual(
            release["exact_result_sha256"],
            "4ef2a23577ef782c5622df1906dde794c11656614dbf0735855db30f213d5531",
        )
        self.assertEqual(
            release["scored_ledger_sha256"],
            "eb9d1efca3e8327e5f8ba08b9e7d546c67da76d5e80595b6f314782a3863bbd1",
        )

    def test_canonical_replay_and_authority_are_bounded(self):
        replay = self.value["canonical_replay"]
        self.assertEqual(replay["workflow_run_id"], 35500929714)
        self.assertEqual(
            replay["public_source_sha"],
            "3ada17b8cad87b98574866400bc7cbed404072a8",
        )
        self.assertTrue(replay["new_training"])
        self.assertEqual(
            replay["exact_result_sha256"],
            "4ef2a23577ef782c5622df1906dde794c11656614dbf0735855db30f213d5531",
        )
        self.assertEqual(
            replay["scored_ledger_sha256"],
            "eb9d1efca3e8327e5f8ba08b9e7d546c67da76d5e80595b6f314782a3863bbd1",
        )
        self.assertTrue(replay["bytes_identical_to_first_complete_result"])
        self.assertTrue(all(v is False for v in self.value["authority"].values()))
        self.assertFalse(
            self.value["project_current_authority"]["promoted_by_this_acceptance"]
        )

    def test_history_records_negative_stopping_rule(self):
        text = HISTORY.read_text(encoding="utf-8")
        self.assertIn("MODEL_B_P128_STATE_EXIT_INCREMENT_NOT_SUPPORTED", text)
        self.assertIn("不得自动升级到更慢 context", text)
        self.assertIn("35500372173-1", text)


if __name__ == "__main__":
    unittest.main()
