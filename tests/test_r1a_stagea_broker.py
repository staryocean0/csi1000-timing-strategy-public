from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "r1a_stagea_broker", ROOT / "executor" / "r1a_stagea_broker.py"
)
BROKER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(BROKER)


class R1AStageABrokerTests(unittest.TestCase):
    def test_fixed_profile_contract(self):
        profile = BROKER.load_profile(BROKER.PROFILE_NAME)
        self.assertEqual(profile["private_base_ref"], BROKER.PRIVATE_BASE)
        self.assertEqual(profile["source_commit"], BROKER.SOURCE_COMMIT)
        self.assertIs(profile["new_training"], True)
        self.assertIs(profile["current_validation_outcomes_scored"], False)
        self.assertIs(profile["stage_b_authorized"], False)
        self.assertIs(profile["production_authority"], False)

    def test_prepare_rejects_private_token_before_touching_inputs(self):
        profile = BROKER.load_profile(BROKER.PROFILE_NAME)
        with mock.patch.dict(
            os.environ,
            {"FACTORLAB_PRIVATE_TOKEN": "sentinel", "RUNNER_TEMP": tempfile.gettempdir()},
            clear=False,
        ):
            with self.assertRaises(BROKER.GateError) as caught:
                BROKER.prepare(profile)
        self.assertEqual(str(caught.exception), "private_token_forbidden_in_public_prepare")

    def test_container_command_is_fixed_and_offline(self):
        profile = BROKER.load_profile(BROKER.PROFILE_NAME)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "work").mkdir()
            (root / "results").mkdir()
            (root / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
            command = BROKER.docker_command(root, profile)
        self.assertIn("--network", command)
        self.assertEqual(command[command.index("--network") + 1], "none")
        self.assertEqual(command[command.index("--cpus") + 1], "4")
        self.assertEqual(command[command.index("--memory") + 1], "12g")
        self.assertEqual(command[-1], BROKER.IMAGE)
        self.assertNotIn("FACTORLAB_PRIVATE_TOKEN", command)

    def test_safe_result_rejects_stage_b_or_outcome_scope(self):
        base = {
            "schema": "r1a_parent_continuation_stagea_private_result_v1",
            "profile_name": BROKER.PROFILE_NAME,
            "status": "STAGEA_BASELINE_IDENTIFIED",
            "new_training": True,
            "stage_b_authorized": False,
            "current_validation_outcomes_constructed_or_scored": False,
            "prediction_error_computed": False,
            "pnl_computed": False,
            "horizon_selected": False,
            "data_2026_opened": False,
            "accepted_trading_strategy": False,
            "fresh_oos": False,
            "production_authority": False,
            "feature_domain_anomalies": {"example": 0},
            "coverage": {"coverage": 1.0, "pass": True},
            "gates": {"all": True},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text(json.dumps(base), encoding="utf-8")
            self.assertEqual(BROKER.safe_result(path), path.read_bytes())
            base["stage_b_authorized"] = True
            path.write_text(json.dumps(base), encoding="utf-8")
            with self.assertRaises(BROKER.GateError):
                BROKER.safe_result(path)


if __name__ == "__main__":
    unittest.main()
