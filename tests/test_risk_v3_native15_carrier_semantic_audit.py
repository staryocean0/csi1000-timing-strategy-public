from __future__ import annotations
import importlib.util, json, tempfile, unittest
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

HERE=Path(__file__).resolve().parents[1]/"executor"
spec=importlib.util.spec_from_file_location("native15",HERE/"risk_v3_native15_carrier_semantic_audit.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class Native15AuditTests(unittest.TestCase):
    def test_prereg_hash_is_frozen(self):
        p=Path(__file__).resolve().parents[1]/"docs"/"research"/"RISK_TOOL_V3_NATIVE15_PHASE_A_PREREG_20260915.json"
        self.assertEqual(m.sha256_file(p),m.PREREG_SHA256)

    def test_controls_forbid_science(self):
        src=(HERE/"risk_v3_native15_carrier_semantic_audit.py").read_text()
        for token in ("RV_WINDOW","BG_WINDOW","SHOCK_SIGMA","HIGHVOL_RATIO","RECOVERY_NORMAL_RATIO"):
            self.assertNotIn(token,src)

    def test_synthetic_semantics_are_aggregate_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); inp=root/"inputs"; out=root/"out"; inp.mkdir()
            rows=[]
            for d in pd.bdate_range("2025-01-02",periods=10):
                clocks=["09:35","09:50","10:05","10:20","10:35","10:50","11:05","11:20",
                        "13:05","13:20","13:35","13:50","14:05","14:20","14:35","14:50"]
                for c in clocks:
                    rows.append((f"{d.date()} {c}:00","000852.SH",1.0))
            frame=pd.DataFrame(rows,columns=["timestamp","symbol","close"])
            pq.write_table(pa.Table.from_pandas(frame,preserve_index=False),inp/"15m_offset_5.parquet")
            carrier=inp/"15m_offset_5.parquet"
            prereg=Path(__file__).resolve().parents[1]/"docs"/"research"/"RISK_TOOL_V3_NATIVE15_PHASE_A_PREREG_20260915.json"
            (inp/"PREREG.json").write_bytes(prereg.read_bytes())
            (inp/"SOURCE_MANIFEST.json").write_text(json.dumps({"canonical_1m_parent_dataset_version":"test","artifacts":{"15m_offset_5.parquet":{"rows":len(frame)}}}))
            ident={"task_id":m.TASK_ID,"carrier":{"archive_path":"data/index/15m_offset_5.parquet","bytes":carrier.stat().st_size,"sha256":m.sha256_file(carrier)},"source_contract":{}}
            (inp/"DATA_IDENTITY.json").write_text(json.dumps(ident))
            r=m.run(inp,out)
            self.assertEqual(r["aggregate"]["mod15_residues"],[5])
            self.assertEqual(r["aggregate"]["duplicate_symbol_timestamp_rows"],0)
            self.assertEqual(r["aggregate"]["symbols"]["000852.SH"]["bars_per_day_mode"],16)
            self.assertFalse(r["controls"]["market_values_read"])
            self.assertNotIn("close",json.dumps(r).lower())

if __name__=="__main__": unittest.main()
