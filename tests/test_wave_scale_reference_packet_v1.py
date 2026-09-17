import json,math,sys,unittest
from datetime import date,timedelta
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
import wave_scale_reference_packet_v1 as p
import wave_scale_reference_packet_verifier_v1 as v
import wave_scale_reference_sampling_v1 as s
import wave_segmentation_carrier_qualification_v1 as q

TZ='Asia/Shanghai'


def candidate_days():
    out=[]
    for year in range(2015,2021):
        for quarter in range(1,5):
            month=1+(quarter-1)*3
            d=date(year,month,1);limit=60 if (year,quarter)==(2015,1) else 10;rows=[]
            while len(rows)<limit:
                if d.weekday()<5:rows.append(d.isoformat())
                d+=timedelta(days=1)
            out.extend(rows)
    return out


def stamp(day,minute):
    return pd.Timestamp(f'{day} {minute//60:02d}:{minute%60:02d}',tz=TZ).tz_convert('UTC')


def price_at(day_index,minute):
    k=day_index*226+(minute-574 if minute<=686 else 113+minute-784)
    return 100.0+2.0*math.sin(k/35.0)+0.0005*k


def direct_frames():
    days=candidate_days();one_rows=[];five={i:[] for i in range(5)}
    for di,day in enumerate(days):
        common=list(range(574,687))+list(range(784,897))
        for minute in common:
            close=price_at(di,minute)
            one_rows.append({'audit_day':day,'audit_minute':minute,'audit_utc':stamp(day,minute),
                             'close':close,'causal_flat_fill':False,'high_frequency_analysis_eligible':True})
        for offset in range(5):
            clocks=[m for m in q.expected_minutes(f'5m_offset_{offset}.parquet')
                    if 574<=m<=686 or 784<=m<=896]
            for minute in clocks:
                close=price_at(di,minute)
                five[offset].append({'audit_day':day,'audit_minute':minute,'audit_utc':stamp(day,minute),
                                     'low':close*.999,'close':close,'high':close*1.001})
    frames={'1m_official.parquet':pd.DataFrame(one_rows)}
    frames.update({f'5m_offset_{i}.parquet':pd.DataFrame(rows) for i,rows in five.items()})
    return days,frames


class ReferencePacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.days,cls.frames=direct_frames();cls.common=set(cls.days)
        cls.sequence=p._common_sequence(cls.frames['1m_official.parquet'],cls.common)
        cls.rows=s.select_primary_days(cls.days)
        with patch.object(p,'qualify_frames',return_value=(cls.frames,cls.common,{})):
            cls.files=p.build_packet(cls.frames,{})

    def test_primary_sample_and_file_counts(self):
        self.assertEqual(len(self.rows),192);self.assertEqual(len(self.files),580)
        panels=[name for name in self.files if name.startswith('panels/')]
        self.assertEqual(len(panels),576)
        self.assertEqual(sum(name.endswith('_A150.svg') for name in panels),192)
        self.assertEqual(sum(name.endswith('_A300.svg') for name in panels),192)
        self.assertEqual(sum(name.endswith('_B300.svg') for name in panels),192)

    def test_blind_inventory_has_no_calendar_identity(self):
        blind=self.files['blind_inventory.json'].decode()
        self.assertNotRegex(blind,r'20\d{2}-\d{2}-\d{2}')
        for token in ('diagnostic','score','pnl','outcome','r1','r2','r3'):
            self.assertNotIn(token,blind.lower())

    def test_summary_has_no_labels_scores_or_authority(self):
        summary=json.loads(self.files['packet_summary.json'])
        self.assertFalse(summary['candidate_outputs_in_packet'])
        self.assertFalse(summary['diagnostic_scores_in_packet'])
        self.assertFalse(summary['primary_reference_labels_frozen'])
        self.assertIsNone(summary['numeric_state_thresholds'])
        self.assertFalse(summary['R4_selected']);self.assertFalse(summary['router_pnl'])
        self.assertFalse(summary['production_authority'])

    def test_full_inventory_is_private_mapping_surface(self):
        full=json.loads(self.files['full_inventory.json'])
        self.assertEqual(len(full),192)
        self.assertEqual(set(full[0]),{'day','quarter','slot','anchor','panel_id'})
        self.assertRegex(full[0]['day'],r'^20\d{2}-\d{2}-\d{2}$')
        self.assertEqual({r['panel_id'] for r in full},{r['panel_id'] for r in self.rows})

    def test_selected_contexts_are_causal_and_flat_fill_free(self):
        for row in self.rows[:12]:
            c=p._context(self.sequence,p._anchor_index(self.sequence,row['day'],row['anchor']),300)
            self.assertEqual(c['relative_minute'].iloc[0],-299);self.assertEqual(c['relative_minute'].iloc[-1],0)
            self.assertFalse(bool(c['causal_flat_fill'].any()))

    def test_flat_fill_in_selected_context_fails_closed(self):
        row=self.rows[0];idx=p._anchor_index(self.sequence,row['day'],row['anchor'])
        bad=self.sequence.copy();bad.loc[idx-20,'causal_flat_fill']=True
        with self.assertRaises(ValueError):p._context(bad,idx,300)

    def test_producer_and_independent_phase_payload_agree(self):
        row=self.rows[8];idx=p._anchor_index(self.sequence,row['day'],row['anchor'])
        context=p._context(self.sequence,idx,300)
        self.assertEqual(p._phase_payload(self.frames,context),v.phase_payload(self.frames,context))

    def test_phase_views_use_only_bars_fully_inside_trailing_context(self):
        row=self.rows[9];idx=p._anchor_index(self.sequence,row['day'],row['anchor'])
        context=p._context(self.sequence,idx,300);actual=p._phase_payload(self.frames,context)
        relative={stamp:int(rel) for stamp,rel in zip(context['audit_utc'],context['relative_minute'])}
        allowed={(str(day),int(minute)) for day,minute in zip(context['audit_day'],context['audit_minute'])}
        for offset in range(5):
            frame=self.frames[f'5m_offset_{offset}.parquet'];part=frame.loc[frame['audit_utc'].isin(relative)]
            expected=[]
            for _,bar in part.iterrows():
                members=q.bucket_members(offset,int(bar['audit_minute']));day=str(bar['audit_day'])
                if members is not None and all((day,int(minute)) in allowed for minute in members):
                    expected.append(relative[bar['audit_utc']])
            self.assertEqual([x[0] for x in actual[f'offset{offset}']],expected)

    def test_panel_manifest_matches_panel_bytes(self):
        manifest=json.loads(self.files['panel_manifest.json'])
        self.assertEqual(len(manifest),576)
        for name in list(sorted(manifest))[:10]:
            raw=self.files[name]
            self.assertEqual(manifest[name]['bytes'],len(raw))
            self.assertEqual(manifest[name]['sha256'],__import__('hashlib').sha256(raw).hexdigest())

    def test_result_manifest_seals_all_580_members(self):
        m=json.loads(p.result_manifest(self.files))
        self.assertEqual(len(m['files']),580)
        self.assertFalse(m['market_labels_frozen']);self.assertFalse(m['diagnostic_scores_measured'])
        self.assertFalse(m['production_authority'])

    def test_verifier_is_independent_from_producer_and_renderer(self):
        text=(ROOT/'executor/wave_scale_reference_packet_verifier_v1.py').read_text()
        self.assertNotIn('wave_scale_reference_packet_v1',text)
        self.assertNotIn('wave_scale_reference_packet_entry_v1',text)
        self.assertNotIn('wave_scale_reference_visuals_v1',text)
        self.assertNotIn('wave_scale_dominance_diagnostics',text)

    def test_producer_has_no_detector_or_dominance_import(self):
        text=(ROOT/'executor/wave_scale_reference_packet_v1.py').read_text()
        self.assertNotIn('wave_recognizer_r',text)
        self.assertNotIn('wave_scale_dominance_diagnostics',text)
        self.assertNotIn('outcome_',text.lower())

    def test_entry_is_no_argument_fixed_path(self):
        text=(ROOT/'executor/wave_scale_reference_packet_entry_v1.py').read_text()
        self.assertIn("INPUTS=Path('/work/inputs')",text)
        self.assertIn("OUT=Path('/results/study')",text)
        self.assertNotIn('argparse',text);self.assertNotIn('sys.argv',text)
        self.assertNotIn('urllib',text);self.assertNotIn('requests',text)

    def test_packet_protocol_pins_reference_without_thresholds(self):
        protocol=json.loads((ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_PACKET_PROTOCOL_20260917.json').read_text())
        self.assertEqual(protocol['profile'],'two-wave-scale-reference-blind-packet-v1')
        self.assertEqual(set(protocol['files']),set(p.FILES))
        self.assertEqual(protocol['reference_contract']['primary_panels'],192)
        self.assertFalse(protocol['reference_contract']['future_suffix_generated'])
        self.assertIsNone(protocol['numeric_state_thresholds'])
        self.assertFalse(protocol['primary_labels_frozen']);self.assertFalse(protocol['production_authority'])

if __name__=='__main__':unittest.main()
