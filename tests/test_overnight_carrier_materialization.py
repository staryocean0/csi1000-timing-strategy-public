import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTOR = ROOT / "executor"
WORKFLOW = ROOT / ".github" / "workflows" / "public-compute.yml"
CONTROLLER = ROOT / ".github" / "workflows" / "controller-dispatch.yml"
PROTOCOL = ROOT / "docs" / "research" / "OVERNIGHT_CARRIER_MATERIALIZATION_PROTOCOL_20260914.md"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class OvernightCarrierMaterializationTests(unittest.TestCase):
    def build_fixture(self, root):
        inputs = root / "inputs"
        external = inputs / "external"
        (inputs / "private_authority").mkdir(parents=True)
        (external / "data/runtime_text_2015_2025").mkdir(parents=True)
        (external / "data/driver_runtime_text_2015_2020").mkdir(parents=True)
        years = list(range(2015, 2021))
        withheld = [2021, 2022, 2023, 2024, 2025]
        source = {
            "schema_id": "csi1000.overnight_carrier_source_manifest@1.0",
            "external_repository": "example/source",
            "external_ref": "a" * 40,
            "private_authority": {
                "private_ref": "b" * 40,
                "official_snapshot_id": "d113b42dca967bb1061c8a6115c5d934e5a41074",
                "files": {},
            },
            "required_years": years,
            "withheld_years": withheld,
            "scientific_change": False,
            "new_training": False,
            "production_authority": False,
        }
        (inputs / "source_manifest.json").write_text(json.dumps(source))
        package = {
            "schema_id": "overnight_open_cloud_theme_package_scope@1.1",
            "included": ["CSI1000_2015_2020_runtime_text_carrier"],
            "data_packs": {"runtime_text_2015_2025": "data/runtime_text_2015_2025"},
            "production_authority": False,
        }
        bindings = {
            "schema_id": "overnight_component_bindings@1.0",
            "validated_components": [
                {"component_id": name, "scientific_status": "PASS", "production_authority": False}
                for name in ("OFP-B1", "OFP-B2", "OFP-B4")
            ],
            "production_authority": False,
        }
        (inputs / "private_authority/package_scope.json").write_text(json.dumps(package))
        (inputs / "private_authority/component_bindings_v1.json").write_text(json.dumps(bindings))

        runtime_outputs = {"factor_panel": {}, "opening_clocks": {}}
        driver_outputs = {}
        for year in years:
            for family, stem in (("factor_panel", "factor_panel"), ("opening_clocks", "opening_clocks")):
                data = f"trading_day,value\n{year}-01-02,{year}\n".encode()
                path = f"data/runtime_text_2015_2025/{stem}_{year}.csv"
                target = external / path
                target.write_bytes(data)
                runtime_outputs[family][str(year)] = {"path": path, "bytes": len(data), "sha256": sha256(data)}
            data = f"trading_day,value\n{year}-01-02,{year}\n".encode()
            path = f"data/driver_runtime_text_2015_2020/driver_external_{year}.csv"
            target = external / path
            target.write_bytes(data)
            driver_outputs[str(year)] = {"path": path, "bytes": len(data), "sha256": sha256(data)}

        runtime = {
            "schema_id": "overnight_runtime_text_carrier@1.0",
            "instrument": "000852.SH",
            "published_year_window": [2015, 2020],
            "withheld_years": withheld,
            "years": years,
            "production_authority": False,
            "transform": {
                "scientific_change": False, "forward_fill": False, "backward_fill": False,
                "resampling": False, "feature_engineering": False, "nearest_clock_match": False,
            },
            "factor_panel_columns": ["trading_day", "gap", "rvol20", "us_nasdaq", "us_vix_chg"],
            "clocks": ["09:35", "09:50", "10:05", "10:35"],
            "outputs": runtime_outputs,
        }
        driver = {
            "schema_id": "overnight_driver_runtime_text_2015_2020@1.0",
            "instrument": "000852.SH",
            "published_window": "2015-01-05..2020-12-31",
            "withheld_years": withheld,
            "blackbox_opened": False,
            "production_authority": False,
            "transform": {"scientific_change": False, "feature_selection_from_outcomes": False, "2021_2025_row_level_text_generated": False},
            "columns": ["trading_day", "a50_channel_return", "hkma_usdcny_closure_return"],
            "outputs": driver_outputs,
        }
        (external / "data/runtime_text_2015_2025/manifest.json").write_text(json.dumps(runtime))
        (external / "data/driver_runtime_text_2015_2020/manifest.json").write_text(json.dumps(driver))
        return inputs

    def test_synthetic_materialization_and_validator(self):
        runner = load_module("carrier_runner", EXECUTOR / "overnight_carrier_materialization.py")
        validator = load_module("carrier_validator", EXECUTOR / "verify_overnight_carrier_materialization.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inputs = self.build_fixture(root)
            out = root / "out"
            receipt = runner.materialize(inputs, out)
            self.assertEqual(receipt["materialized_file_count"], 18)
            self.assertTrue(receipt["all_required_families_present"])
            self.assertFalse(receipt["blackbox_window_opened"])
            self.assertFalse(receipt["outcome_analysis_executed"])
            self.assertFalse(receipt["training_executed"])
            self.assertEqual(validator.validate(inputs, out)["status"], "passed")

    def test_rejects_any_2021_2025_csv(self):
        runner = load_module("carrier_runner_leak", EXECUTOR / "overnight_carrier_materialization.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inputs = self.build_fixture(root)
            leak = inputs / "external/data/runtime_text_2015_2025/factor_panel_2021.csv"
            leak.write_text("forbidden\n")
            with self.assertRaises(ValueError):
                runner.materialize(inputs, root / "out")

    def test_profile_and_public_stage_are_immutable_and_credential_separated(self):
        profile = json.loads((EXECUTOR / "overnight_carrier_materialization_profile.json").read_text())
        source = json.loads((EXECUTOR / "overnight_carrier_source_manifest.json").read_text())
        self.assertEqual(profile["profile_name"], "overnight-carrier-materialization-v1")
        self.assertEqual(profile["transport_profile"], "handoff-verify-v1")
        self.assertEqual(profile["private_ref"], source["private_authority"]["private_ref"])
        self.assertEqual(source["external_ref"], "9905c2f8942ad0a2faf106d42c1b62fd6127e646")
        self.assertEqual(source["withheld_years"], [2021, 2022, 2023, 2024, 2025])
        stage = (EXECUTOR / "overnight_carrier_stage_public.py").read_text()
        self.assertIn("private_token_must_not_reach_public_stage", stage)
        self.assertIn("raw.githubusercontent.com", stage)
        self.assertNotIn("csi1000-timing-strategy-private", stage)

    def test_broker_must_reuse_reviewed_transport_without_external_network(self):
        text = (EXECUTOR / "overnight_carrier_materialization_broker.py").read_text()
        self.assertIn("overnight-carrier-materialization-v1", text)
        self.assertIn("handoff-verify-v1", text)
        self.assertIn("legacy_prepare_inputs", text)
        self.assertIn("install_overlay", text)
        self.assertNotIn("raw.githubusercontent.com", text)
        self.assertNotIn("urllib.request", text)

    def test_standard_workflow_and_controller_route_only_reviewed_profile(self):
        workflow = WORKFLOW.read_text()
        controller = CONTROLLER.read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("\n  push:", workflow)
        self.assertIn("overnight-carrier-materialization-v1", workflow)
        self.assertIn("Stage fixed public Overnight carriers without private credentials", workflow)
        for phase in ("prepare", "compute", "cleanup", "publish"):
            self.assertIn(f"overnight_carrier_materialization_broker.py {phase}", workflow)
        self.assertIn("controller: overnight-carrier-materialization-v1", controller)
        self.assertIn("inputs[profile]=$profile", controller)

    def test_protocol_keeps_research_boundary_closed(self):
        text = PROTOCOL.read_text()
        self.assertIn("non-outcome-bearing", text)
        self.assertIn("historical carrier source only", text)
        self.assertIn("2021-2025", text)
        self.assertIn("new non-rescue Overnight identity", text)
        self.assertIn("production_authority=false", text)


if __name__ == "__main__":
    unittest.main()
