import unittest

import pandas as pd

from executor.two_wave_v0800_scale_map import TemporalMaturityAEngine


class TwoWaveV0800ScaleMapTest(unittest.TestCase):
    def frame(self, closes):
        rows = []
        for i, close in enumerate(closes):
            rows.append(
                {
                    "timestamp": pd.Timestamp("2020-01-02 09:35") + pd.Timedelta(minutes=5 * i),
                    "open": close,
                    "high": close + 0.5,
                    "low": close - 0.5,
                    "close": close,
                    "bar_index": i,
                }
            )
        return pd.DataFrame(rows)

    def test_v043_maturity_does_not_confirm_terminal_low_at_occurrence(self):
        # Low at 8 becomes confirmed only after four later bars establish an
        # opposite running high; publication therefore occurs after occurrence.
        closes = [100, 99, 98, 97, 96, 98, 100, 102, 104, 102, 100, 98, 96, 98, 100, 102, 104]
        waves, pivots, _ = TemporalMaturityAEngine(self.frame(closes)).run()
        for pivot in pivots:
            if not pivot["left_censored"]:
                self.assertGreaterEqual(pivot["confirmation_delay_bars"], 4)
        for rec in waves:
            self.assertGreaterEqual(rec.wave.confirmation_bar - rec.wave.end_bar, 4)

    def test_emitted_a_wave_is_low_high_low_and_whole_cycle_duration(self):
        closes = [100, 99, 98, 97, 96, 98, 100, 102, 104, 102, 100, 98, 96, 98, 100, 102, 104, 102, 100, 98, 96, 98, 100, 102, 104]
        waves, _, _ = TemporalMaturityAEngine(self.frame(closes)).run()
        self.assertGreaterEqual(len(waves), 1)
        wave = waves[0].wave
        self.assertLess(wave.start_bar, wave.high_bar)
        self.assertLess(wave.high_bar, wave.end_bar)
        self.assertEqual(wave.duration, wave.end_bar - wave.start_bar)
        self.assertGreaterEqual(wave.duration, 8)


if __name__ == "__main__":
    unittest.main()
