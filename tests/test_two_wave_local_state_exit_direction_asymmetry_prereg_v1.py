from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "docs/research/TWO_WAVE_LOCAL_STATE_EXIT_DIRECTION_ASYMMETRY_MECHANISM_PREREG_20260920.json"

class DirectionAsymmetryPreregTests(unittest.TestCase):
    def test_frozen_identity_and_scope(self):
        d=json.loads(P.read_text(encoding="utf-8"))
        self.assertEqual(d["schema_id"], "csi1000.two_wave_local_state_exit_direction_asymmetry_prereg@1.0")
        self.assertEqual(d["issue"], 647)
        self.assertEqual(d["study_class"], "mechanism_audit_only")
        self.assertFalse(d["fresh_oos"])
        self.assertFalse(d["scientific_authority_from_this_study"])
        src=d["source_evidence"]
        self.assertEqual(src["canonical_run_identity"], "35488698309-1")
        self.assertEqual(src["scored_ledger_sha256"], "c1ef13cfc3b2bc5669955ff62a5200b6c56c6868b459421d7e621e5ed189f46f")
        self.assertEqual(src["rows"], 29713)
        self.assertEqual(src["years"], [2018,2019,2020])
        self.assertEqual(d["frozen_target"], "structural_exit_next8")
        self.assertEqual(d["states"], ["CURRENT_UP","CURRENT_DOWN"])
        self.assertEqual([x["raw"] for x in d["components"]], ["abs_ret_8","range_8","rv_8","efficiency_8"])
        self.assertEqual([x["risk"] for x in d["components"]], ["risk_abs_ret_8","risk_range_8","risk_rv_8","risk_efficiency_8"])
        self.assertIn("Do not add new features", d["stop_rule"])
        self.assertTrue(all(v is False for v in d["authority"].values()))

    def test_no_cross_frequency_or_trading_inputs(self):
        d=json.loads(P.read_text(encoding="utf-8"))
        allowed=" ".join(d["allowed_columns"])
        for token in ["P128","P256","C1","C2","C3","pnl","return_bp","route"]:
            self.assertNotIn(token, allowed)
        self.assertEqual(d["analysis"]["uncertainty"], "20-trading-day block bootstrap, 5000 repetitions, seed 20260920")
        self.assertEqual(set(d["mechanism_labels"]), {
            "COMPONENT_COHERENT_DIRECTION_ASYMMETRY",
            "AGE_COMPOSITION_DOMINANT",
            "MIXED_OR_INCONCLUSIVE",
        })

if __name__ == "__main__":
    unittest.main()
