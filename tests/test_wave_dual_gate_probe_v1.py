"""Synthetic unit tests only. No market data, no empirical acceptance."""
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "executor"))
from wave_dual_gate_probe_v1 import (
    CompletedWave, binary_losses, completed_shape, future_parent_turn,
    graphical_components, nested_probabilities, paired_block_interval,
    period_bucket, purged_training, trend_shadow_trades,
)


def node(t, known, price, root="r"):
    return dict(occurrence_bar=t, known_from_bar=known, price=price, root_id=root)


def pivot(t, known, kind, root="r"):
    return dict(occurrence_bar=t, known_from_bar=known, kind=kind, root_id=root)


class ShapeTests(unittest.TestCase):
    def setUp(self):
        self.close = [100, 103, 107, 110, 109, 108, 107, 105, 104, 105, 106]
        self.wave = CompletedWave(0, 3, 8, 10)

    def test_not_available_on_terminal_low(self):
        with self.assertRaises(ValueError):
            completed_shape(self.close, self.wave, 8)

    def test_consumer_is_after_confirmation(self):
        f = completed_shape(self.close, self.wave, 10)
        self.assertEqual(f["earliest_consumer_bar"], 11)
        self.assertEqual(f["confirmation_delay"], 2)

    def test_scale_invariance(self):
        a = completed_shape(self.close, self.wave, 10)
        b = completed_shape(np.array(self.close) * 9, self.wave, 10)
        for k in ("g", "peak_phase", "front_push", "back_push", "efficiency"):
            self.assertAlmostEqual(a[k], b[k])

    def test_future_suffix_is_not_read(self):
        a = completed_shape(self.close, self.wave, 10)
        b = completed_shape(self.close + [float("nan"), -1], self.wave, 10)
        self.assertEqual(a, b)

    def test_zero_height_rejected(self):
        with self.assertRaises(ValueError):
            completed_shape([100] * 11, self.wave, 10)

    def test_invalid_wave_clock(self):
        with self.assertRaises(ValueError):
            CompletedWave(0, 4, 8, 7)
        with self.assertRaises(ValueError):
            CompletedWave(False, 4, 8, 10)


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.close = np.exp(np.linspace(4.6, 4.7, 13) + np.sin(np.arange(13)) * 0.01)
        self.layers = [[node(0, 2, 100), node(4, 6, 102), node(8, 10, 104)],
                       [node(0, 3, 100), node(8, 11, 103)]]

    def test_reconstruction_and_no_fake_spectral_claim(self):
        out = graphical_components(self.close, self.layers, 12, "r")
        self.assertLess(out["reconstruction_error"], 1e-12)
        self.assertFalse(out["orthogonal_energy_claimed"])
        self.assertAlmostEqual(sum(out["geometric_variance_normalized_scores"]), 1)

    def test_no_right_edge_extrapolation(self):
        out = graphical_components(self.close, self.layers, 12, "r")
        self.assertEqual(out["support_end"], 8)
        self.assertEqual(out["right_edge_age_bars"], 4)

    def test_future_nodes_are_ignored(self):
        out = graphical_components(self.close, self.layers, 12, "r")
        future = [x + [node(15, 20, 1, "future-root")] for x in self.layers]
        self.assertEqual(out, graphical_components(list(self.close) + [-1], future, 12, "r"))

    def test_unknown_coarse_graph_stays_unknown(self):
        out = graphical_components(self.close, self.layers, 9, "r")
        self.assertEqual(out["status"], "INSUFFICIENT_GRAPH")

    def test_mixed_root_rejected(self):
        with self.assertRaises(ValueError):
            graphical_components(self.close, [[node(0, 1, 100), node(8, 9, 110, "other")]], 12, "r")

    def test_clock_rejected(self):
        with self.assertRaises(ValueError):
            graphical_components(self.close, [[node(8, 3, 100)]], 12, "r")

    def test_period_bucket_boundaries(self):
        self.assertEqual(period_bucket(None, 20), "UNRESOLVED")
        self.assertEqual(period_bucket(40, 20), "2T_TO_3T")
        self.assertEqual(period_bucket(60, 20), "2T_TO_3T")
        self.assertEqual(period_bucket(61, 20), "ABOVE_3T_BELOW_6T")
        self.assertEqual(period_bucket(120, 20), "AT_LEAST_6T")


class OutcomeTests(unittest.TestCase):
    def test_late_old_high_not_a_predicted_turn(self):
        out = future_parent_turn([pivot(8, 12, "high"), pivot(21, 25, "low")], 10, 10, "UP", "r")
        self.assertEqual(out["target"], 0)
        self.assertEqual(out["late_confirmations_of_old_turns"], 1)

    def test_future_new_high_is_turn(self):
        out = future_parent_turn([pivot(14, 18, "high"), pivot(22, 28, "low")], 10, 10, "UP", "r")
        self.assertEqual(out["target"], 1)
        self.assertEqual(out["lead_bars"], 4)
        self.assertEqual(out["mature_bar"], 28)

    def test_absence_not_zero_before_settlement(self):
        out = future_parent_turn([pivot(14, 18, "high")], 10, 10, "UP", "r")
        self.assertEqual(out["status"], "RIGHT_CENSORED")
        self.assertIsNone(out["target"])

    def test_reset_not_a_negative_label(self):
        out = future_parent_turn([pivot(14, 18, "high"), pivot(22, 28, "low")], 10, 10, "UP", "r", [19])
        self.assertEqual(out["status"], "RESET_CENSORED")

    def test_range_not_forced_into_up_or_down(self):
        with self.assertRaises(ValueError):
            future_parent_turn([], 10, 10, "RANGE", "r")


class EvaluationTests(unittest.TestCase):
    def test_purge_uses_maturity_and_parent_groups(self):
        rows = [dict(decision_bar=1, mature_bar=8, parent_id="a", target=1),
                dict(decision_bar=2, mature_bar=12, parent_id="b", target=0),
                dict(decision_bar=3, mature_bar=9, parent_id="test", target=1)]
        self.assertEqual(purged_training(rows, 10, {"test"}), rows[:1])

    def test_unseen_shape_falls_back_to_baseline(self):
        train = [dict(target=i % 2, context="up", shape="known") for i in range(40)]
        p = nested_probabilities(train, [dict(context="up", shape="unseen")], [("context",), ("context", "shape")])
        self.assertEqual(p[0], p[1])

    def test_non_nested_keys_rejected(self):
        with self.assertRaises(ValueError):
            nested_probabilities([dict(target=1)], [], [("context",), ("shape",)])

    def test_proper_losses(self):
        loss = binary_losses([0, 1], [0.2, 0.8])
        np.testing.assert_allclose(loss["brier"], [0.04, 0.04])
        np.testing.assert_allclose(loss["logloss"], [-math.log(0.8)] * 2)

    def test_insufficient_blocks_not_significant(self):
        out = paired_block_interval([1] * 20, [str(i) for i in range(20)])
        self.assertEqual(out["status"], "INSUFFICIENT_BLOCKS")

    def test_equal_block_weight_not_event_weight(self):
        values = [1.0] * 100 + [0.0] * 29
        blocks = ["big"] * 100 + [str(i) for i in range(29)]
        out = paired_block_interval(values, blocks, repetitions=100)
        self.assertAlmostEqual(out["mean"], 1 / 30)


class ShadowTests(unittest.TestCase):
    def test_next_open_not_confirmation_close_fill(self):
        close = [100, 101, 103, 99, 98, 104, 105]
        open_ = [100, 100, 101, 102, 97, 100, 106]
        out = trend_shadow_trades(close, open_, 2)
        first = out["trades"][0]
        self.assertEqual(first["signal_bar"], 2)
        self.assertEqual(first["entry_bar"], 3)
        self.assertEqual(first["exit_bar"], 4)
        self.assertAlmostEqual(first["gross_log_return"], math.log(97 / 102))

    def test_cost_charged_both_sides(self):
        out = trend_shadow_trades([100, 101, 103, 99, 98, 104, 105], [100] * 7, 2, cost_bps_per_side=5)
        for row in out["trades"]:
            self.assertAlmostEqual(row["net_log_return_proxy"], -0.001)

    def test_unclosed_trade_censored(self):
        out = trend_shadow_trades(list(range(100, 120)), list(range(100, 120)), 3)
        self.assertEqual(out["trades"], [])
        self.assertEqual(out["right_censored_open_trade"], 1)

    def test_completed_trades_invariant_to_future_suffix(self):
        close = [100, 101, 103, 99, 98, 104, 105]
        a = trend_shadow_trades(close, close, 2)["trades"]
        b = trend_shadow_trades(close + [90, 80, 120], close + [91, 82, 115], 2)["trades"]
        for original, extended in zip(a, b):
            for key in original:
                if key != "two_sided_fast_loss":
                    self.assertEqual(original[key], extended[key])

    def test_invalid_price_fail_closed(self):
        with self.assertRaises(ValueError):
            trend_shadow_trades([100, 101, 0], [100] * 3, 2)


if __name__ == "__main__":
    unittest.main()
