import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text_outputs_from_source():
    source = (ROOT / "executor/risk_success_mirror.py").read_text()
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "TEXT_OUTPUTS" for target in node.targets):
                return tuple(ast.literal_eval(node.value))
    raise AssertionError("TEXT_OUTPUTS not found")


class RiskSuccessMirrorTests(unittest.TestCase):
    def test_mirror_surface_is_fixed_text_only(self):
        outputs = text_outputs_from_source()
        self.assertEqual(
            set(outputs),
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
        self.assertFalse(any(name.endswith(".parquet") for name in outputs))

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
