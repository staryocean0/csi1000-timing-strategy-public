from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "executor"))

import two_wave_t0_causal_c1_compression_interaction_v1 as m


class Issue615InteractionTests(unittest.TestCase):
    def test_frozen_band_groups(self):
        self.assertEqual([m._risk_group(x) for x in range(1, 6)],
                         ["LOW", "LOW", "MID", "HIGH", "HIGH"])

    def test_authoritative_507_identifiers_are_frozen(self):
        self.assertEqual(
            m.AUTHORITATIVE_RISK_MODULE_SHA256,
            "7c386d7ce6b5b41a8df297aecf74488d806dcb20c09c852aab566f424602478c",
        )
        self.assertEqual(
            m.AUTHORITATIVE_SCORED_LEDGER_SHA256,
            "6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33",
        )

    def _support_table(self, n=60, blocks=20):
        return {
            "grid": {
                rel: {
                    group: {"n": n, "blocks": blocks}
                    for group in ("LOW", "HIGH")
                }
                for rel in ("ALIGNED", "OPPOSED")
            }
        }

    def test_support_gate_uses_preregistered_minima(self):
        meta = {"causal_c1_coverage": 0.99}
        support = m.support_gate(meta, self._support_table())
        self.assertTrue(support["passed"])

        low_n = self._support_table()
        low_n["grid"]["ALIGNED"]["LOW"]["n"] = 49
        self.assertFalse(m.support_gate(meta, low_n)["passed"])

        low_blocks = self._support_table()
        low_blocks["grid"]["OPPOSED"]["HIGH"]["blocks"] = 14
        self.assertFalse(m.support_gate(meta, low_blocks)["passed"])

        self.assertFalse(
            m.support_gate({"causal_c1_coverage": 0.949}, self._support_table())["passed"]
        )

    def test_adjudication_requires_all_five_frozen_gates(self):
        support = {"passed": True}
        point = {
            "delta_aligned_HIGH_minus_LOW": -10.0,
            "delta_opposed_HIGH_minus_LOW": 5.0,
            "DID_opposed_minus_aligned": 15.0,
        }
        yearly = {
            "2018": {"delta_aligned": -1.0, "delta_opposed": 1.0},
            "2019": {"delta_aligned": -1.0, "delta_opposed": 1.0},
            "2020": {"delta_aligned": 1.0, "delta_opposed": -1.0},
        }
        boot = {
            "delta_aligned": {"ci95": [-20.0, -1.0]},
            "delta_opposed": {"ci95": [1.0, 20.0]},
            "did": {"ci95": [1.0, 30.0]},
        }
        result = m.adjudicate(support, point, yearly, boot)
        self.assertEqual(
            result["verdict"],
            "T0_CAUSAL_C1_COMPRESSION_INTERACTION_SUPPORTED",
        )

        boot["did"]["ci95"] = [-1.0, 30.0]
        result = m.adjudicate(support, point, yearly, boot)
        self.assertEqual(
            result["verdict"],
            "T0_CAUSAL_C1_COMPRESSION_INTERACTION_NOT_SUPPORTED",
        )

    def test_insufficient_support_is_not_relabelled_negative(self):
        result = m.adjudicate(
            {"passed": False},
            {},
            {
                "2018": {"delta_aligned": -1.0, "delta_opposed": 1.0},
                "2019": {"delta_aligned": -1.0, "delta_opposed": 1.0},
            },
            {
                "delta_aligned": {"ci95": [-2.0, -1.0]},
                "delta_opposed": {"ci95": [1.0, 2.0]},
                "did": {"ci95": [1.0, 3.0]},
            },
        )
        self.assertEqual(
            result["verdict"],
            "T0_CAUSAL_C1_COMPRESSION_INTERACTION_INSUFFICIENT_SUPPORT",
        )


if __name__ == "__main__":
    unittest.main()
