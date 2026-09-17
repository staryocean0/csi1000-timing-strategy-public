"""Build #363 amended blind reference packets v2 from already-qualified carriers.

No detector, dominance score, outcome, threshold selection, or trading logic.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

from wave_segmentation_carrier_qualification_v1 import (
    FILES, EXCLUDED, PRICE, canonicalize, complete_days, bucket_members, expected_minutes,
)
from wave_scale_reference_sampling_v2 import (
    select_primary_days, blinded_inventory, normalize_log_shape, anchor_clock,
)
from wave_scale_reference_visuals_v1 import render_shape_svg, render_phase_svg

COMMON_WINDOWS=((574,686),(784,896))
ANCHOR_MINUTES={"11:00":660,"14:30":870}
CONTEXTS=(150,300)


def _common_minute_mask(frame:pd.DataFrame)->pd.Series:
    minute=frame['audit_minute']
    return (((minute>=COMMON_WINDOWS[0][0])&(minute<=COMMON_WINDOWS[0][1])) |
            ((minute>=COMMON_WINDOWS[1][0])&(minute<=COMMON_WINDOWS[1][1])))


def qualify_frames(raw_frames:dict[str,pd.DataFrame],declared_rows:dict[str,int]):
    frames={}
    metrics={}
    for name in FILES:
        frame,metric=canonicalize(raw_frames[name],name,declared_rows[name])
        if metric['errors']:
            raise ValueError('carrier_schema_or_clock:'+name)
        frames[name]=frame;metrics[name]=metric
    common=set.intersection(*(complete_days(frames[name],name) for name in FILES))
    one=frames['1m_official.parquet']
    eligible={day for day,part in one.groupby('audit_day')
              if day not in EXCLUDED and bool(part['high_frequency_analysis_eligible'].all())}
    common &= eligible
    if len(common)!=1458:
        raise ValueError('qualified_common_day_count')
    return frames,common,metrics


def _common_sequence(one:pd.DataFrame,common:set[str])->pd.DataFrame:
    part=one.loc[one['audit_day'].isin(common)&_common_minute_mask(one)].copy()
    part=part.sort_values('audit_utc').reset_index(drop=True)
    if len(part)!=len(common)*226:
        raise ValueError('common_minute_count')
    if part['audit_utc'].duplicated().any():
        raise ValueError('common_time_duplicate')
    return part


def _anchor_index(sequence:pd.DataFrame,day:str,anchor:str)->int:
    minute=ANCHOR_MINUTES.get(anchor)
    if minute is None:
        raise ValueError('anchor_clock')
    hits=sequence.index[(sequence['audit_day']==day)&(sequence['audit_minute']==minute)].tolist()
    if len(hits)!=1:
        raise ValueError('anchor_support')
    return int(hits[0])


def _context(sequence:pd.DataFrame,index:int,length:int)->pd.DataFrame:
    if length not in CONTEXTS or index-length+1<0:
        raise ValueError('context_support')
    part=sequence.iloc[index-length+1:index+1].copy()
    if len(part)!=length:
        raise ValueError('context_length')
    if bool(part['causal_flat_fill'].any()):
        raise ValueError('context_causal_flat_fill')
    if not bool(part['high_frequency_analysis_eligible'].all()):
        raise ValueError('context_ineligible')
    part['relative_minute']=np.arange(-(length-1),1,dtype=int)
    return part


def _phase_support_inside_context(context300:pd.DataFrame)->bool:
    allowed={(str(day),int(minute)) for day,minute in zip(context300['audit_day'],context300['audit_minute'])}
    days=sorted({day for day,_ in allowed})
    for offset in range(5):
        count=0
        for day in days:
            for close in expected_minutes(f"5m_offset_{offset}.parquet"):
                if (day,int(close)) not in allowed:
                    continue
                members=bucket_members(offset,int(close))
                if members is not None and all((day,int(minute)) in allowed for minute in members):
                    count+=1
        if count<2:
            return False
    return True


def anchor_context_eligible_days(frames,sequence,common):
    eligible=set();reasons=Counter()
    for day in sorted(common):
        anchor=anchor_clock(day)
        try:
            idx=_anchor_index(sequence,day,anchor)
            c300=_context(sequence,idx,300)
        except ValueError as error:
            reason=str(error)
            if reason not in {'anchor_support','context_support','context_length','context_causal_flat_fill','context_ineligible'}:
                raise
            reasons[reason]+=1
            continue
        if not _phase_support_inside_context(c300):
            reasons['phase_support']+=1
            continue
        eligible.add(day)
    return eligible,dict(sorted(reasons.items()))


def _normalize_pool(values:np.ndarray):
    arr=np.asarray(values,float)
    if arr.ndim!=1 or not len(arr) or not np.isfinite(arr).all() or np.any(arr<=0):
        raise ValueError('phase_price_pool')
    y=np.log(arr);lo=float(y.min());hi=float(y.max());span=hi-lo
    if span<=np.finfo(float).eps:
        return lo,hi,None
    return lo,hi,span


def _norm(value:float,lo:float,span:float|None)->float:
    return 0.5 if span is None else float((np.log(float(value))-lo)/span)


def _phase_payload(frames:dict[str,pd.DataFrame],context300:pd.DataFrame)->dict:
    relative={stamp:int(rel) for stamp,rel in zip(context300['audit_utc'],context300['relative_minute'])}
    allowed={(str(day),int(minute)) for day,minute in zip(context300['audit_day'],context300['audit_minute'])}
    selected={}
    pooled=[]
    for offset in range(5):
        name=f'5m_offset_{offset}.parquet';frame=frames[name]
        part=frame.loc[frame['audit_utc'].isin(relative)].copy()
        rows=[]
        for _,row in part.iterrows():
            members=bucket_members(offset,int(row['audit_minute']))
            day=str(row['audit_day'])
            if members is None or any((day,int(minute)) not in allowed for minute in members):
                continue
            rel=relative[row['audit_utc']]
            values=(float(row['low']),float(row['close']),float(row['high']))
            if not values[0]<=values[1]<=values[2]:
                raise ValueError('phase_ohlc_order')
            pooled.extend(values);rows.append((rel,*values))
        if len(rows)<2:
            raise ValueError('phase_support:'+name)
        selected[f'offset{offset}']=rows
    lo,_,span=_normalize_pool(np.asarray(pooled,float))
    out={}
    for key,rows in selected.items():
        out[key]=[(rel,_norm(low,lo,span),_norm(close,lo,span),_norm(high,lo,span))
                  for rel,low,close,high in rows]
    return out


def _panel_files(frames,sequence,row):
    idx=_anchor_index(sequence,row['day'],row['anchor'])
    c150=_context(sequence,idx,150);c300=_context(sequence,idx,300)
    s150=normalize_log_shape(c150['close'].to_numpy(float))['shape']
    s300=normalize_log_shape(c300['close'].to_numpy(float))['shape']
    phases=_phase_payload(frames,c300)
    panel=row['panel_id']
    return {
        f'panels/{panel}_A150.svg':render_shape_svg(panel,s150).encode(),
        f'panels/{panel}_A300.svg':render_shape_svg(panel,s300).encode(),
        f'panels/{panel}_B300.svg':render_phase_svg(panel,phases).encode(),
    }


def _encode(value)->bytes:
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def build_packet(raw_frames:dict[str,pd.DataFrame],declared_rows:dict[str,int])->dict[str,bytes]:
    frames,common,_=qualify_frames(raw_frames,declared_rows)
    sequence=_common_sequence(frames['1m_official.parquet'],common)
    anchor_eligible,eligibility_exclusions=anchor_context_eligible_days(frames,sequence,common)
    full=select_primary_days(sorted(anchor_eligible))
    if len(full)!=192 or len({row['panel_id'] for row in full})!=192:
        raise ValueError('primary_sample_cardinality')
    blind=blinded_inventory(full)
    files={}
    for row in full:
        panel_files=_panel_files(frames,sequence,row)
        overlap=set(files).intersection(panel_files)
        if overlap:
            raise ValueError('duplicate_panel_file')
        files.update(panel_files)
    if len(files)!=576:
        raise ValueError('panel_file_count')
    panel_manifest={name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
                    for name,raw in sorted(files.items())}
    full_raw=_encode(full);blind_raw=_encode(blind);panels_raw=_encode(panel_manifest)
    anchors=Counter(row['anchor'] for row in full)
    summary={
        'schema_id':'csi1000.scale_reference_blind_packet@2.0',
        'research_issue':359,'parent_issue':353,
        'status':'BLIND_PACKET_GENERATED_REFERENCE_LABELS_NOT_FROZEN',
        'population_role':'PREVIOUSLY_CONSUMED_DEVELOPMENT_REFERENCE_ONLY',
        'common_complete_eligible_days':len(common),'anchor_context_eligible_days':len(anchor_eligible),
        'anchor_context_exclusions':eligibility_exclusions,'primary_panels':192,
        'panel_files':576,'contexts_trading_minutes':[150,300],
        'anchor_counts':dict(sorted(anchors.items())),
        'candidate_outputs_in_packet':False,'diagnostic_scores_in_packet':False,
        'numeric_amplitude_visible_pass_A':False,'outcomes_used':False,
        'primary_reference_labels_frozen':False,'numeric_state_thresholds':None,
        'R4_selected':False,'one_minute_strategy_admitted':False,
        'router_pnl':False,'production_authority':False,
    }
    summary_raw=_encode(summary)
    files['full_inventory.json']=full_raw
    files['blind_inventory.json']=blind_raw
    files['panel_manifest.json']=panels_raw
    files['packet_summary.json']=summary_raw
    return files


def result_manifest(files:dict[str,bytes])->bytes:
    meta={name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
          for name,raw in sorted(files.items())}
    return _encode({'schema_id':'csi1000.scale_reference_packet_manifest@2.0',
                    'files':meta,'market_labels_frozen':False,
                    'diagnostic_scores_measured':False,'new_training':False,
                    'production_authority':False})
