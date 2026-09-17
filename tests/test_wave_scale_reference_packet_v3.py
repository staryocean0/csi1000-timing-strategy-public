import sys,unittest
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"executor"))
import wave_scale_reference_packet_v2 as producer
import wave_scale_reference_packet_verifier_v3 as verifier


def seq(rows=420,day="2020-01-02",anchor="11:00"):
    minute=660 if anchor=="11:00" else 870
    df=pd.DataFrame({
        "audit_day":[day]*rows,
        "audit_minute":[600]*rows,
        "audit_utc":pd.date_range("2020-01-02",periods=rows,freq="min",tz="UTC"),
        "close":100+np.arange(rows)*.001,
        "causal_flat_fill":[False]*rows,
        "high_frequency_analysis_eligible":[True]*rows})
    df.loc[rows-1,"audit_minute"]=minute
    return df


class V3ReasonTaxonomyTests(unittest.TestCase):
    def test_flat_fill_is_not_collapsed_to_support(self):
        x=seq();x.loc[len(x)-20,"causal_flat_fill"]=True
        with self.assertRaisesRegex(ValueError,"^context_causal_flat_fill$"):
            verifier.anchor_context(x,{"day":"2020-01-02","anchor":"11:00"},300)

    def test_hfa_ineligible_has_exact_reason(self):
        x=seq();x.loc[len(x)-30,"high_frequency_analysis_eligible"]=False
        with self.assertRaisesRegex(ValueError,"^context_ineligible$"):
            verifier.anchor_context(x,{"day":"2020-01-02","anchor":"11:00"},300)

    def test_short_history_and_missing_anchor_are_distinct(self):
        x=seq(200)
        with self.assertRaisesRegex(ValueError,"^context_support$"):
            verifier.anchor_context(x,{"day":"2020-01-02","anchor":"11:00"},300)
        y=seq();y.loc[len(y)-1,"audit_minute"]=601
        with self.assertRaisesRegex(ValueError,"^anchor_support$"):
            verifier.anchor_context(y,{"day":"2020-01-02","anchor":"11:00"},300)

    def test_phase_support_is_a_separate_predicate(self):
        x=seq().iloc[-300:].copy();x["relative_minute"]=np.arange(-299,1)
        self.assertFalse(verifier.phase_support_inside_context(x))

    def test_producer_and_v3_verifier_flat_fill_reason_match(self):
        x=seq();x.loc[len(x)-10,"causal_flat_fill"]=True
        for fn,row in ((producer._context,None),(verifier.anchor_context,{"day":"2020-01-02","anchor":"11:00"})):
            with self.assertRaisesRegex(ValueError,"^context_causal_flat_fill$"):
                if row is None: fn(x,len(x)-1,300)
                else: fn(x,row,300)

    def test_v2_scientific_sources_are_not_modified(self):
        expected={
          "wave_scale_reference_packet_v2.py":"90b226723098188185725576e4caffa37993d2d4",
          "wave_scale_reference_sampling_v2.py":"7cc243a1cee058b15d96db82a123e466de63571b",
          "wave_scale_reference_visuals_v1.py":"d6ce92747bf2701b32c473af9361b46db4effb02",
          "wave_scale_reference_verifier_v2.py":"1394ab08c1a3e49ad8930189765f59969b414b7a"}
        import hashlib
        for name,want in expected.items():
            raw=(ROOT/"executor"/name).read_bytes();got=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
            self.assertEqual(got,want,name)

if __name__=="__main__":unittest.main()
