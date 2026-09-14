import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RiskSuccessMirrorTests(unittest.TestCase):
    def test_mirror_surface_is_fixed_text_only(self):
        spec = importlib.util.spec_from_file_location(
            "risk_success_mirror", ROOT / "executor/risk_success_mirror.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(
            set(module.TEXT_OUTPUTS),
            {
                "SUMMARY.json",
                "SUPPORT_AUDIT.csv",
                "HORIZON_METRICS.csv",
                "SEVERITY_PERSISTENCE_SURFACE.csv",
                "T_TO_NORMAL_SUMMARY.csv",
                "MODEL_FREEZE.json",
                "INPUT_DATA_RECEIPT.json",
            },
        )
        self.assertFalse(any(name.endswith(".parquet") for name in module.TEXT_OUTPUTS))

    def test_workflow_mirrors_only_after_successful_risk_publish(self):
        text = (ROOT / ".github/workflows/public-compute.yml").read_text()
        needle = (
            "python3 executor/risk_research_broker.py publish risk-v2-severity-persistence-v1\n"
            "            python3 executor/risk_success_mirror.py"
        )
        self.assertIn(needle, text)
        self.assertEqual(text.count("python3 executor/risk_success_mirror.py"), 1)


if __name__ == "__main__":
    unittest.main()
