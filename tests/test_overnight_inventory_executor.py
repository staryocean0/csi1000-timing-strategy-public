import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTOR = ROOT / "executor"
WORKFLOW = ROOT / ".github" / "workflows" / "public-compute.yml"


def load_inventory_module():
    spec = importlib.util.spec_from_file_location("overnight_inventory", EXECUTOR / "overnight_inventory.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OvernightInventoryTests(unittest.TestCase):
    def test_runner_only_reads_bundle_manifest(self):
        text = (EXECUTOR / "overnight_inventory.py").read_text()
        self.assertNotIn("extractall", text)
        self.assertNotIn("archive.extract(", text)
        self.assertEqual(text.count("archive.extractfile("), 1)
        self.assertIn("archive.extractfile(manifest_member)", text)
        self.assertIn('MANIFEST_NAME = "BUNDLE_MANIFEST.json"', text)
        self.assertNotIn("pandas", text.lower())
        self.assertNotIn("pyarrow", text.lower())

    def test_synthetic_inventory_uses_names_metadata_only(self):
        module = load_inventory_module()
        files = {}
        for year in range(2015, 2021):
            files[f"data/runtime_text_2015_2025/factor_panel_{year}.csv"] = {
                "bytes": 13,
                "sha256": "a" * 64,
            }
            files[f"data/runtime_text_2015_2025/opening_clocks_{year}.csv"] = {
                "bytes": 17,
                "sha256": "b" * 64,
            }
            files[f"data/driver_runtime_text_2015_2020/driver_external_{year}.csv"] = {
                "bytes": 19,
                "sha256": "c" * 64,
            }
        files["unrelated/secret_market_rows.csv"] = {"bytes": 29, "sha256": "d" * 64}
        manifest = json.dumps({"schema": "csi1000_handoff_bundle@1", "files": files}).encode()
        with tempfile.TemporaryDirectory() as td:
            bundle = Path(td) / "bundle.tar"
            with tarfile.open(bundle, "w") as archive:
                info = tarfile.TarInfo("BUNDLE_MANIFEST.json")
                info.size = len(manifest)
                archive.addfile(info, io.BytesIO(manifest))
                # Member payloads deliberately contain values the inventory must never read.
                for name in files:
                    payload = b"DO_NOT_READ_MARKET_ROW_VALUES"
                    info = tarfile.TarInfo(name)
                    info.size = len(payload)
                    archive.addfile(info, io.BytesIO(payload))
            result = module.build_inventory(bundle)
        self.assertEqual(result["outcome_rows_read"], 0)
        self.assertEqual(result["market_data_files_opened"], 0)
        self.assertFalse(result["training_executed"])
        self.assertFalse(result["strategy_replayed"])
        self.assertFalse(result["production_authority"])
        self.assertEqual(result["carrier_family_status"]["csi1000_gap_and_opening_clock"], "PRESENT")
        for key in (
            "rvol20_source",
            "b1_global_risk_source",
            "b2_china_offshore_source",
            "b4_driver_coherence_source",
        ):
            self.assertEqual(result["carrier_family_status"][key], "AMBIGUOUS_FROM_NAMES_ONLY")
        self.assertFalse(result["all_required_families_present"])
        matched_paths = {row["path"] for row in result["matched_files"]}
        self.assertNotIn("unrelated/secret_market_rows.csv", matched_paths)
        serialized = json.dumps(result)
        self.assertNotIn("DO_NOT_READ_MARKET_ROW_VALUES", serialized)

    def test_profile_is_fixed_to_existing_handoff_transport(self):
        profile = json.loads((EXECUTOR / "overnight_inventory_profile.json").read_text())
        self.assertEqual(profile["profile_name"], "overnight-official-inventory-v1")
        self.assertEqual(profile["transport_profile"], "handoff-verify-v1")
        self.assertEqual(profile["private_ref"], "20b8619722a885db2c46e83cdcf1c949bdedac52")
        self.assertEqual(set(profile["private_source_files"]), {"handoff/INPUT_MANIFEST.json"})
        self.assertEqual(
            set(profile["public_source_files"]),
            {"overnight_inventory.py", "verify_overnight_inventory.py"},
        )
        self.assertIs(profile["new_training"], False)
        self.assertIs(profile["production_authority"], False)

    def test_broker_reuses_reviewed_transport_and_safe_private_writeback(self):
        text = (EXECUTOR / "overnight_inventory_broker.py").read_text()
        self.assertIn('HERE / "research_broker.py"', text)
        self.assertIn('TRANSPORT_PROFILE_NAME = "handoff-verify-v1"', text)
        self.assertIn('SOURCE_PATHS = ("handoff/INPUT_MANIFEST.json",)', text)
        self.assertIn("legacy_prepare_inputs(api, root, profile)", text)
        self.assertIn("legacy_publish(profile)", text)
        self.assertIn("-overnight-inventory.json", text)
        self.assertIn('value.get("outcome_rows_read") != 0', text)
        self.assertNotIn("data/runtime_text_2015_2025", text)
        self.assertNotIn("data/driver_runtime_text_2015_2020", text)

    def test_standard_workflow_remains_dispatch_only(self):
        text = WORKFLOW.read_text()
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("\n  push:", text)
        self.assertIn("overnight-official-inventory-v1", text)
        self.assertIn("executor/overnight_inventory_broker.py prepare", text)
        self.assertIn("executor/overnight_inventory_broker.py compute", text)
        self.assertIn("executor/overnight_inventory_broker.py cleanup", text)
        self.assertIn("executor/overnight_inventory_broker.py publish", text)

    def test_protocol_does_not_authorize_outcome_research(self):
        protocol = (ROOT / "docs" / "research" / "OVERNIGHT_OFFICIAL_SNAPSHOT_INVENTORY_PROTOCOL_20260914.md").read_text()
        self.assertIn("active_research=null", protocol)
        self.assertIn("not a successor study", protocol)
        self.assertIn("No outcome-bearing research is authorized", protocol)
        self.assertIn("2021-2025 remains reusable BLACKBOX material", protocol)


if __name__ == "__main__":
    unittest.main()
