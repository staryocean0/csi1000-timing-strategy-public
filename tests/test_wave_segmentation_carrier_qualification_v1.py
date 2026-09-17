import copy
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))
import wave_segmentation_carrier_qualification_v1 as q

DAY = "2020-01-02"
TZ = "Asia/Shanghai"


def local_timestamp(day, minute):
    value = pd.Timestamp(f"{day} {minute // 60:02d}:{minute % 60:02d}", tz=TZ)
    return value, value.tz_convert("UTC")


def one_minute(day=DAY):
    rows = []
    for index, minute in enumerate(q.expected_minutes("1m_official.parquet")):
        local, utc = local_timestamp(day, minute)
        close = 100.0 + index * 0.01
        rows.append(dict(symbol=q.SYMBOL, timestamp=utc, bar_end_shanghai=local,
            trading_day=day, open=close, high=close + 0.002, low=close - 0.003, close=close,
            causal_flat_fill=False, high_frequency_analysis_eligible=True))
    return pd.DataFrame(rows)


def five_minute(one, offset, day=DAY):
    records = []
    minute_map = {int(row.audit_minute): idx for idx, row in one.assign(
        audit_minute=pd.to_datetime(one["timestamp"], utc=True).dt.tz_convert(TZ).dt.hour * 60 +
                     pd.to_datetime(one["timestamp"], utc=True).dt.tz_convert(TZ).dt.minute).iterrows()}
    for close_minute in q.expected_minutes(f"5m_offset_{offset}.parquet"):
        local, utc = local_timestamp(day, close_minute)
        members = q.bucket_members(offset, close_minute)
        if offset == 0 and members[0] in (570, 780):
            available = [m for m in members if m in minute_map]
            part = one.iloc[[minute_map[m] for m in available]]
        else:
            part = one.iloc[[minute_map[m] for m in members]]
        agg = q.aggregate_ohlc(part)
        records.append(dict(symbol=q.SYMBOL, timestamp=utc, bar_end_shanghai=local,
            trading_day=day, open=agg[0], high=agg[1], low=agg[2], close=agg[3]))
    return pd.DataFrame(records)


def synthetic_frames():
    one = one_minute()
    return {"1m_official.parquet": one,
            **{f"5m_offset_{i}.parquet": five_minute(one, i) for i in range(5)}}


class CarrierQualificationTests(unittest.TestCase):
    def test_clock_contract_counts(self):
        self.assertEqual(len(q.expected_minutes("1m_official.parquet")), 240)
        self.assertEqual(len(q.expected_minutes("5m_offset_0.parquet")), 48)
        for offset in range(1, 5):
            self.assertEqual(len(q.expected_minutes(f"5m_offset_{offset}.parquet")), 46)

    def test_bucket_members_preserve_two_sessions(self):
        self.assertEqual(q.bucket_members(0, 575), tuple(range(570, 576)))
        self.assertEqual(q.bucket_members(0, 580), tuple(range(576, 581)))
        self.assertEqual(q.bucket_members(1, 576), tuple(range(571, 577)))
        self.assertEqual(q.bucket_members(4, 789), tuple(range(784, 790)))
        self.assertIsNone(q.bucket_members(4, 700))

    def test_exact_synthetic_reconstruction(self):
        frames = synthetic_frames(); declared = {name: len(frame) for name, frame in frames.items()}
        with patch.object(q, "START_DAY", DAY), patch.object(q, "END_DAY", DAY), patch.object(q, "EXCLUDED", frozenset()):
            report = q.build_report(frames, declared)
        self.assertEqual(report["status"], "QUALIFIED_WITH_EXPECTED_UNSUPPORTED_BUCKETS")
        self.assertEqual(report["reconstruction"]["0"]["compared_bars"], 46)
        self.assertEqual(report["reconstruction"]["0"]["unsupported_or_other"]["SOURCE_MINUTE_NOT_EXPORTED"], 2)
        for offset in range(1, 5):
            self.assertEqual(report["reconstruction"][str(offset)]["compared_bars"], 46)
            self.assertEqual(report["reconstruction"][str(offset)]["mismatched_bars"], 0)
    def test_common_physical_support_is_not_bar_end_intersection(self):
        frames = synthetic_frames(); declared = {name: len(frame) for name, frame in frames.items()}
        with patch.object(q, "START_DAY", DAY), patch.object(q, "END_DAY", DAY), patch.object(q, "EXCLUDED", frozenset()):
            report = q.build_report(frames, declared)
        common = report["common_support"]
        self.assertEqual(common["common_complete_eligible_days"], 1)
        self.assertEqual(common["contract_common_minutes"], 226)
        self.assertEqual(common["exported_common_minute_rows"], 226)

    def test_flat_fill_is_unsupported_not_mismatch(self):
        frames = synthetic_frames(); frames["1m_official.parquet"].loc[40, "causal_flat_fill"] = True
        declared = {name: len(frame) for name, frame in frames.items()}
        with patch.object(q, "START_DAY", DAY), patch.object(q, "END_DAY", DAY), patch.object(q, "EXCLUDED", frozenset()):
            report = q.build_report(frames, declared)
        self.assertEqual(report["status"], "QUALIFIED_WITH_EXPECTED_UNSUPPORTED_BUCKETS")
        self.assertGreater(sum(v["unsupported_or_other"].get("CAUSAL_FLAT_FILL", 0) for v in report["reconstruction"].values()), 0)
        self.assertEqual(sum(v["mismatched_bars"] for v in report["reconstruction"].values()), 0)

    def test_price_tamper_is_construction_mismatch(self):
        frames = synthetic_frames(); frames["5m_offset_2.parquet"].loc[5, "open"] += 0.001
        declared = {name: len(frame) for name, frame in frames.items()}
        with patch.object(q, "START_DAY", DAY), patch.object(q, "END_DAY", DAY), patch.object(q, "EXCLUDED", frozenset()):
            report = q.build_report(frames, declared)
        self.assertEqual(report["status"], "CONSTRUCTION_MISMATCH")
        self.assertGreater(report["reconstruction"]["2"]["mismatched_bars"], 0)
    def test_declared_row_count_tamper_fails_schema(self):
        frames = synthetic_frames(); declared = {name: len(frame) for name, frame in frames.items()}
        declared["5m_offset_1.parquet"] += 1
        with patch.object(q, "START_DAY", DAY), patch.object(q, "END_DAY", DAY), patch.object(q, "EXCLUDED", frozenset()):
            report = q.build_report(frames, declared)
        self.assertEqual(report["status"], "SCHEMA_OR_CLOCK_FAILED")
        self.assertIn("DECLARED_ROW_COUNT", report["file_metrics"]["5m_offset_1.parquet"]["errors"])

    def test_unexpected_clock_fails_schema(self):
        frames = synthetic_frames(); local, utc = local_timestamp(DAY, 700)
        frames["5m_offset_3.parquet"].loc[0, "timestamp"] = utc
        frames["5m_offset_3.parquet"].loc[0, "bar_end_shanghai"] = local
        declared = {name: len(frame) for name, frame in frames.items()}
        with patch.object(q, "START_DAY", DAY), patch.object(q, "END_DAY", DAY), patch.object(q, "EXCLUDED", frozenset()):
            report = q.build_report(frames, declared)
        self.assertEqual(report["status"], "SCHEMA_OR_CLOCK_FAILED")

    def test_string_boolean_fields_are_parsed_explicitly(self):
        one = one_minute(); one["causal_flat_fill"] = "False"; one["high_frequency_analysis_eligible"] = "True"
        with patch.object(q, "START_DAY", DAY), patch.object(q, "END_DAY", DAY), patch.object(q, "EXCLUDED", frozenset()):
            _, metrics = q.canonicalize(one, "1m_official.parquet", len(one))
        self.assertEqual(metrics["errors"], [])

    def test_invalid_boolean_field_fails_closed(self):
        one = one_minute(); one["causal_flat_fill"] = one["causal_flat_fill"].astype(object); one.loc[0, "causal_flat_fill"] = "maybe"
        with patch.object(q, "START_DAY", DAY), patch.object(q, "END_DAY", DAY), patch.object(q, "EXCLUDED", frozenset()):
            _, metrics = q.canonicalize(one, "1m_official.parquet", len(one))
        self.assertIn("BOOLEAN_FIELD", metrics["errors"])
    def test_tolerance_is_fixed_and_small(self):
        a = np.asarray([100.0, 100.0, 100.0, 100.0])
        self.assertTrue(q.close_enough(a, a + 5e-11).all())
        self.assertFalse(q.close_enough(a, a + 1e-6).all())
        self.assertEqual(q.ABS_TOL, 1e-10); self.assertEqual(q.REL_TOL, 1e-12)

    def test_bad_ohlc_fails(self):
        one = one_minute(); one.loc[4, "high"] = one.loc[4, "low"] - 1
        with patch.object(q, "START_DAY", DAY), patch.object(q, "END_DAY", DAY), patch.object(q, "EXCLUDED", frozenset()):
            _, metrics = q.canonicalize(one, "1m_official.parquet", len(one))
        self.assertIn("OHLC_RANGE", metrics["errors"])

    def test_timestamp_shanghai_crosscheck_fails_closed(self):
        one = one_minute(); one.loc[0, "bar_end_shanghai"] = pd.Timestamp("2020-01-02 10:00", tz=TZ)
        with patch.object(q, "START_DAY", DAY), patch.object(q, "END_DAY", DAY), patch.object(q, "EXCLUDED", frozenset()):
            _, metrics = q.canonicalize(one, "1m_official.parquet", len(one))
        self.assertIn("SHANGHAI_TIMESTAMP_MISMATCH", metrics["errors"])

    def test_report_never_claims_aliasing_or_dominance(self):
        frames = synthetic_frames(); declared = {name: len(frame) for name, frame in frames.items()}
        with patch.object(q, "START_DAY", DAY), patch.object(q, "END_DAY", DAY), patch.object(q, "EXCLUDED", frozenset()):
            report = q.build_report(frames, declared)
        self.assertEqual(report["aliasing_conclusion"], "NOT_AUTHORIZED")
        self.assertEqual(report["scale_dominance_conclusion"], "NOT_AUTHORIZED")
        self.assertFalse(report["R4_selected"]); self.assertFalse(report["production_authority"])


if __name__ == "__main__":
    unittest.main()
