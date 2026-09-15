import math
import unittest

from executor.two_wave_v0800_semantics import (
    AWave,
    CANDIDATE_RHOS,
    LEGACY_RHO_CONTROL,
    channel_geometry,
    classify_pair,
    internal_wave_descriptor,
    scale_band,
    select_backward_predecessor,
    shared_anchor_strict,
)


class TwoWaveV0800SemanticsTest(unittest.TestCase):
    def wave(self, start, high, end, low0, peak, low1, confirm=None, wave_id=""):
        return AWave(
            start_bar=start,
            high_bar=high,
            end_bar=end,
            start_low=low0,
            high=peak,
            end_low=low1,
            confirmation_bar=end + 2 if confirm is None else confirm,
            wave_id=wave_id,
        )

    def test_frozen_scale_bands(self):
        expected = {
            5: [(4, 6), (4, 6), (4, 7), (4, 7)],
            10: [(8, 12), (8, 13), (8, 14), (7, 15)],
            20: [(16, 25), (15, 26), (15, 28), (14, 30)],
        }
        for n, bands in expected.items():
            self.assertEqual([scale_band(n, rho) for rho in CANDIDATE_RHOS], bands)
        self.assertEqual(LEGACY_RHO_CONTROL, 2.0)
        self.assertNotIn(LEGACY_RHO_CONTROL, CANDIDATE_RHOS)

    def test_top_channel_is_parallel_translation(self):
        wave = self.wave(0, 4, 10, 100.0, 112.0, 103.0)
        geom = channel_geometry(wave)
        self.assertGreater(geom.channel_height_log, 0.0)
        self.assertAlmostEqual(geom.top_start - geom.bottom_start, geom.channel_height_log)
        self.assertAlmostEqual(geom.top_high - geom.bottom_high, geom.channel_height_log)
        self.assertAlmostEqual(geom.top_end - geom.bottom_end, geom.channel_height_log)

    def test_nonpositive_channel_fails_closed(self):
        wave = self.wave(0, 5, 10, 100.0, 99.0, 100.0)
        with self.assertRaises(ValueError):
            channel_geometry(wave)

    def test_backward_predecessor_skips_only_out_of_scale_objects(self):
        old_same = self.wave(0, 5, 10, 100.0, 110.0, 102.0, wave_id="old")
        micro = self.wave(22, 23, 25, 101.0, 103.0, 102.0, wave_id="micro")
        near_same = self.wave(15, 20, 27, 101.0, 111.0, 103.0, wave_id="near")
        current = self.wave(30, 35, 40, 103.0, 113.0, 105.0, confirm=43, wave_id="current")
        picked = select_backward_predecessor(current, [old_same, micro, near_same], rho=1.5)
        self.assertIs(picked, near_same)

    def test_backward_predecessor_never_uses_future_confirmed_wave(self):
        past = self.wave(10, 15, 20, 100.0, 110.0, 102.0, confirm=22, wave_id="past")
        future_known = self.wave(20, 25, 30, 102.0, 112.0, 104.0, confirm=99, wave_id="future")
        current = self.wave(30, 35, 40, 104.0, 114.0, 106.0, confirm=43, wave_id="current")
        picked = select_backward_predecessor(current, [past, future_known], rho=1.5)
        self.assertIs(picked, past)

    def test_shared_anchor_is_reported_separately(self):
        previous = self.wave(0, 5, 10, 100.0, 110.0, 102.0)
        current = self.wave(10, 15, 20, 102.0, 112.0, 104.0)
        gapped = self.wave(12, 17, 22, 102.0, 112.0, 104.0)
        self.assertTrue(shared_anchor_strict(previous, current))
        self.assertFalse(shared_anchor_strict(previous, gapped))

    def test_one_wave_descriptor_is_not_market_state(self):
        wave = self.wave(0, 5, 10, 100.0, 110.0, 102.0)
        self.assertIn(internal_wave_descriptor(wave, 0.1), {"UP", "DOWN", "RANGE"})
        self.assertEqual(classify_pair(None, wave, rho=1.5, tau=0.1, kappa=1.5), "Uncertain")

    def test_two_same_scale_up_waves_can_form_uptrend(self):
        previous = self.wave(0, 5, 10, 100.0, 110.0, 102.0)
        current = self.wave(10, 15, 20, 102.0, 112.0, 104.0)
        self.assertEqual(
            classify_pair(previous, current, rho=1.25, tau=0.1, kappa=1.5),
            "UpTrend",
        )

    def test_scale_mismatch_cannot_form_state(self):
        previous = self.wave(0, 2, 4, 100.0, 110.0, 102.0)
        current = self.wave(10, 15, 20, 102.0, 112.0, 104.0)
        self.assertEqual(
            classify_pair(previous, current, rho=1.5, tau=0.1, kappa=1.5),
            "NotSameScale",
        )

    def test_opposite_directions_are_uncertain(self):
        previous = self.wave(0, 5, 10, 100.0, 110.0, 102.0)
        current = self.wave(10, 15, 20, 102.0, 111.0, 100.0)
        self.assertEqual(
            classify_pair(previous, current, rho=1.25, tau=0.1, kappa=2.0),
            "Uncertain",
        )


if __name__ == "__main__":
    unittest.main()
