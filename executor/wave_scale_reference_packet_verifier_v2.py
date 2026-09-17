"""Independent verifier for #363 amended real blind reference packet v2.

Does not import packet producer, entry, renderer, or dominance diagnostics.
"""
from __future__ import annotations
import hashlib,json,math,re
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
import wave_segmentation_carrier_verifier_v1 as cv
import wave_scale_reference_verifier_v2 as rv

INPUTS=Path('/work/inputs')
RESULTS=Path('/results/study')
PROTOCOL=Path('/work/scale_reference_packet/protocol.json')
FILES=('1m_official.parquet',*(f'5m_offset_{i}.parquet' for i in range(5)))
COMMON_WINDOWS=((574,686),(784,896))
ANCHOR_MINUTES={'11:00':660,'14:30':870}
PANEL_NAME_RE=re.compile(r'^panels/([0-9a-f]{20})_(A150|A300|B300)\.svg$')


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def load_json(path,max_bytes=8*1024*1024):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>max_bytes:raise ValueError('json_file')
    return json.loads(path.read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))


def read_protocol():
    p=load_json(PROTOCOL)
    if p.get('schema_id')!='csi1000.scale_reference_packet_protocol@2.0':
        raise ValueError('protocol')
    if p.get('profile')!='two-wave-scale-reference-blind-packet-v2':
        raise ValueError('profile')
    if set(p.get('files',{}))!=set(FILES):
        raise ValueError('file_set')
    ref=p['reference_contract']
    if ref['primary_panels']!=192 or ref['contexts_trading_minutes']!=[150,300]:
        raise ValueError('reference_contract')
    if ref['future_suffix_generated'] is not False:
        raise ValueError('future_scope')
    if p['numeric_state_thresholds'] is not None:
        raise ValueError('threshold_selected')
    if p['primary_labels_frozen'] is not False:
        raise ValueError('labels_already_frozen')
    return p


def read_frames(protocol):
    if INPUTS.is_symlink() or not INPUTS.is_dir():
        raise ValueError('input_root')
    if {p.name for p in INPUTS.iterdir()}!=set(FILES):
        raise ValueError('input_set')
    frames={}
    for name in FILES:
        frame=cv.read_frame(INPUTS/name,name,protocol['files'][name])
        frame['audit_utc']=pd.to_datetime(frame['timestamp'],utc=True)
        frames[name]=frame
    return frames


def common_days(frames):
    common=set.intersection(*(cv.full_days(frames[name],name) for name in FILES))
    one=frames['1m_official.parquet']
    eligible={day for day,part in one.groupby('audit_day')
              if day not in cv.EXCLUDED and bool(part['high_frequency_analysis_eligible'].all())}
    common &= eligible
    if len(common)!=1458:
        raise ValueError('common_day_count')
    return common


def common_sequence(one,common):
    minute=one['audit_minute']
    mask=one['audit_day'].isin(common)&(((minute>=574)&(minute<=686))|((minute>=784)&(minute<=896)))
    part=one.loc[mask].copy().sort_values('timestamp').reset_index(drop=True)
    if len(part)!=1458*226:
        raise ValueError('common_minute_count')
    part['audit_utc']=pd.to_datetime(part['timestamp'],utc=True)
    if part['audit_utc'].duplicated().any():
        raise ValueError('common_time_duplicate')
    return part


def anchor_context(sequence,row,length):
    minute=ANCHOR_MINUTES[row['anchor']]
    hits=sequence.index[(sequence['audit_day']==row['day'])&(sequence['audit_minute']==minute)].tolist()
    if len(hits)!=1:
        raise ValueError('anchor_support')
    if hits[0]-length+1<0:
        raise ValueError('context_support')
    part=sequence.iloc[hits[0]-length+1:hits[0]+1].copy()
    if len(part)!=length or bool(part['causal_flat_fill'].any()):
        raise ValueError('context_support')
    if not bool(part['high_frequency_analysis_eligible'].all()):
        raise ValueError('context_eligibility')
    part['relative_minute']=np.arange(-(length-1),1,dtype=int)
    return part


def phase_support_inside_context(context300):
    allowed={(str(day),int(minute)) for day,minute in zip(context300['audit_day'],context300['audit_minute'])}
    days=sorted({day for day,_ in allowed})
    for offset in range(5):
        minutes,_=cv.expected(f"5m_offset_{offset}.parquet")
        count=0
        for day in days:
            for close in minutes:
                if (day,int(close)) not in allowed:
                    continue
                members=cv.members(offset,int(close))
                if members is not None and all((day,int(minute)) in allowed for minute in members):
                    count+=1
        if count<2:
            return False
    return True


def anchor_context_eligible_days(sequence,common):
    eligible=set();reasons=Counter()
    for day in sorted(common):
        row={'day':day,'anchor':rv._anchor(day)}
        try:
            c300=anchor_context(sequence,row,300)
        except ValueError as error:
            reason=str(error)
            if reason not in {'anchor_support','context_support','context_eligibility'}:
                raise
            reasons[reason]+=1
            continue
        if not phase_support_inside_context(c300):
            reasons['phase_support']+=1
            continue
        eligible.add(day)
    return eligible,dict(sorted(reasons.items()))


def normalized_close(part):
    y=np.log(part['close'].to_numpy(float));span=float(y.max()-y.min())
    if span<=np.finfo(float).eps:return np.zeros(len(y))
    return (y-float(y.min()))/span


def expected_shape_points(values):
    rows=np.asarray(values,float)
    out=[]
    for i,value in enumerate(rows):
        x=28.0+904.0*i/(len(rows)-1)
        y=28.0+244.0*(1.0-float(value))
        out.append(f'{x:.3f},{y:.3f}')
    return ' '.join(out)


def extract_polylines(svg):
    return re.findall(r'<polyline points="([^"]+)"',svg)


def verify_shape_file(path,panel,part):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>1024*1024:
        raise ValueError('shape_file')
    svg=path.read_text()
    rv.verify_svg(svg,panel,'shape')
    lines=extract_polylines(svg)
    if lines!=[expected_shape_points(normalized_close(part))]:
        raise ValueError('shape_geometry')


def phase_payload(frames,context300):
    relative={stamp:int(rel) for stamp,rel in zip(context300['audit_utc'],context300['relative_minute'])}
    allowed={(str(day),int(minute)) for day,minute in zip(context300['audit_day'],context300['audit_minute'])}
    chosen={};pool=[]
    for offset in range(5):
        frame=frames[f'5m_offset_{offset}.parquet']
        part=frame.loc[frame['audit_utc'].isin(relative)]
        rows=[]
        for _,row in part.iterrows():
            members=cv.members(offset,int(row['audit_minute']))
            day=str(row['audit_day'])
            if members is None or any((day,int(minute)) not in allowed for minute in members):
                continue
            values=(float(row['low']),float(row['close']),float(row['high']))
            if not values[0]<=values[1]<=values[2]:raise ValueError('phase_ohlc')
            rows.append((relative[row['audit_utc']],*values));pool.extend(values)
        if len(rows)<2:raise ValueError('phase_support')
        chosen[f'offset{offset}']=rows
    y=np.log(np.asarray(pool,float));lo=float(y.min());span=float(y.max()-y.min())
    def norm(x):return 0.5 if span<=np.finfo(float).eps else float((math.log(float(x))-lo)/span)
    return {key:[(rel,norm(low),norm(close),norm(high)) for rel,low,close,high in rows]
            for key,rows in chosen.items()}


def phase_xy(minute,value,top):
    x=70.0+850.0*(minute+299)/299.0
    y=top+68.0*(1.0-value)
    return x,y


def expected_phase_geometry(phases):
    polylines=[];lines=[]
    for index in range(5):
        rows=sorted(phases[f'offset{index}'])
        top=34+index*100;points=[]
        for minute,low,close,high in rows:
            x,yc=phase_xy(minute,close,top)
            _,yl=phase_xy(minute,low,top);_,yh=phase_xy(minute,high,top)
            points.append(f'{x:.3f},{yc:.3f}');lines.append((x,yh,x,yl))
        polylines.append(' '.join(points));lines.append((70.0,top+68.0,920.0,top+68.0))
    return polylines,lines


def extracted_lines(svg):
    rows=re.findall(r'<line x1="([0-9.]+)" y1="([0-9.]+)" x2="([0-9.]+)" y2="([0-9.]+)"',svg)
    return [tuple(float(v) for v in row) for row in rows]


def verify_phase_file(path,panel,phases):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>2*1024*1024:
        raise ValueError('phase_file')
    svg=path.read_text();rv.verify_svg(svg,panel,'phase')
    expected_poly,expected_lines=expected_phase_geometry(phases)
    if extract_polylines(svg)!=expected_poly:
        raise ValueError('phase_close_geometry')
    actual_lines=extracted_lines(svg)
    if len(actual_lines)!=len(expected_lines):
        raise ValueError('phase_line_count')
    for actual,expected in zip(actual_lines,expected_lines):
        if any(abs(a-e)>0.0011 for a,e in zip(actual,expected)):
            raise ValueError('phase_wick_geometry')


def verify_file_manifest(manifest):
    if manifest.get('schema_id')!='csi1000.scale_reference_packet_manifest@2.0':
        raise ValueError('manifest_schema')
    if manifest.get('market_labels_frozen') is not False or manifest.get('diagnostic_scores_measured') is not False:
        raise ValueError('manifest_scope')
    actual={str(path.relative_to(RESULTS)) for path in RESULTS.rglob('*') if path.is_file() and path.name!='manifest.json'}
    expected=set(manifest.get('files',{}))
    if actual!=expected:
        raise ValueError('result_file_set')
    for name,meta in manifest['files'].items():
        path=RESULTS/name
        if path.is_symlink() or not path.is_file():raise ValueError('result_file_type')
        if meta!={'bytes':path.stat().st_size,'sha256':sha(path)}:raise ValueError('result_file_identity')
    return actual


def verify_summary(summary,anchor_eligible,eligibility_exclusions):
    expected={'common_complete_eligible_days':1458,'anchor_context_eligible_days':len(anchor_eligible),
              'anchor_context_exclusions':eligibility_exclusions,'primary_panels':192,'panel_files':576,
              'contexts_trading_minutes':[150,300],'candidate_outputs_in_packet':False,
              'diagnostic_scores_in_packet':False,'numeric_amplitude_visible_pass_A':False,
              'outcomes_used':False,'primary_reference_labels_frozen':False,
              'numeric_state_thresholds':None,'R4_selected':False,
              'one_minute_strategy_admitted':False,'router_pnl':False,'production_authority':False}
    for key,value in expected.items():
        if summary.get(key)!=value:raise ValueError('summary:'+key)
    if summary.get('schema_id')!='csi1000.scale_reference_blind_packet@2.0':raise ValueError('summary_schema')


def verify_all_panels(frames,sequence,full):
    checked=0
    for row in full:
        panel=row['panel_id']
        c150=anchor_context(sequence,row,150);c300=anchor_context(sequence,row,300)
        verify_shape_file(RESULTS/f'panels/{panel}_A150.svg',panel,c150)
        verify_shape_file(RESULTS/f'panels/{panel}_A300.svg',panel,c300)
        phases=phase_payload(frames,c300)
        verify_phase_file(RESULTS/f'panels/{panel}_B300.svg',panel,phases)
        checked+=1
    if checked!=192:raise ValueError('panel_verify_count')
    return checked


def main():
    protocol=read_protocol();frames=read_frames(protocol);common=common_days(frames)
    sequence=common_sequence(frames['1m_official.parquet'],common)
    anchor_eligible,eligibility_exclusions=anchor_context_eligible_days(sequence,common)
    expected_full=rv.derive(sorted(anchor_eligible));expected_blind=rv.expected_blind(expected_full)
    full=load_json(RESULTS/'full_inventory.json');blind=load_json(RESULTS/'blind_inventory.json')
    if full!=expected_full:raise ValueError('full_inventory')
    if blind!=expected_blind:raise ValueError('blind_inventory')
    rv.verify_inventories(sorted(anchor_eligible),full,blind)
    manifest=load_json(RESULTS/'manifest.json');actual=verify_file_manifest(manifest)
    summary=load_json(RESULTS/'packet_summary.json');verify_summary(summary,anchor_eligible,eligibility_exclusions)
    panel_manifest=load_json(RESULTS/'panel_manifest.json')
    expected_panel_meta={name:meta for name,meta in manifest['files'].items() if PANEL_NAME_RE.fullmatch(name)}
    if panel_manifest!=expected_panel_meta or len(panel_manifest)!=576:
        raise ValueError('panel_manifest')
    if len(actual)!=580:
        raise ValueError('result_member_count')
    checked=verify_all_panels(frames,sequence,full)
    result={'status':'passed','panels_verified':checked,'panel_files_verified':576,
            'primary_labels_frozen':False,'diagnostic_scores_measured':False,
            'new_training':False,'production_authority':False}
    print(json.dumps(result,sort_keys=True,separators=(',',':')))


if __name__=='__main__':main()
