import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTOR = ROOT / "executor"


class RiskPublicInputTransportTests(unittest.TestCase):
    def test_manifest_is_exact_immutable_canonical_set(self):
        cfg = json.loads((EXECUTOR / "risk_canonical_public_data.json").read_text())
        self.assertEqual(cfg["schema_id"], "risk_tool_v2_canonical_public_data@1.0")
        self.assertEqual(cfg["repository"], "staryocean0/factorlab-trend-reversion-regime-lab")
        self.assertRegex(cfg["ref"], r"^[0-9a-f]{40}$")
        expected = {
            f"data/market/5m/{symbol}/{year}.parquet"
            for symbol in ("000688.SH", "000852.SH")
            for year in range(2020, 2026)
        }
        self.assertEqual(set(cfg["files"]), expected)
        self.assertEqual(len(cfg["files"]), 12)
        for meta in cfg["files"].values():
            self.assertEqual(set(meta), {"bytes", "git_blob_sha1"})
            self.assertGreater(meta["bytes"], 0)
            self.assertRegex(meta["git_blob_sha1"], r"^[0-9a-f]{40}$")

    def test_transport_is_public_unauthenticated_and_blob_verified(self):
        text = (EXECUTOR / "risk_public_data_transport.py").read_text()
        self.assertIn("raw.githubusercontent.com", text)
        self.assertIn("_git_blob_sha1(raw)", text)
        self.assertIn("SOURCE_RECEIPT.json", text)
        self.assertNotIn("Authorization", text)
        self.assertNotIn("FACTORLAB_PRIVATE_TOKEN", text)

    def test_adapter_only_replaces_physical_input_loading(self):
        text = (EXECUTOR / "risk_public_input_adapter.py").read_text()
        self.assertIn("private.v2.base.load_selected_5m = load_selected_5m", text)
        self.assertIn("private.v2.run(inputs, out)", text)
        self.assertIn("other_5m_views_allowed\": False", text)
        for forbidden in ("HIGHVOL_RATIO", "RECOVERY_NORMAL_RATIO", "SHOCK_SIGMA", "RIDGE", "BOOTSTRAP_REPS"):
            self.assertNotIn(forbidden, text)

    def test_profile_routes_adapter_but_keeps_private_verifier(self):
        profile = json.loads((EXECUTOR / "risk_profile.json").read_text())
        self.assertEqual(profile["command"][0], "risk_public_input_adapter.py")
        self.assertEqual(
            profile["verify_command"][0],
            "runtime/research/risk_tool_v2_severity_persistence_v1/verify_study_v2.py",
        )
        self.assertFalse(profile["new_training"])
        self.assertFalse(profile["production_authority"])


if __name__ == "__main__":
    unittest.main()
