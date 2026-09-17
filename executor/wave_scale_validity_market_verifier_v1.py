"""Independent verifier for issue #376 validity diagnostics.

Does not import the validity producer or wave_scale_validity_diagnostics_v1.
"""
from __future__ import annotations
from collections import Counter
import hashlib,json,math
from pathlib import Path
import numpy as np
import pandas as pd
import wave_segmentation_carrier_verifier_v1 as cv
import wave_scale_reference_verifier_v2 as rv

INPUTS=Path('/work/inputs');RESULTS=Path('/results/study');PROTOCOL=Path('/work/scale_validity_measurement/protocol.json')
FILES=('1m_official.parquet',*(f'5m_offset_{i}.parquet' for i in range(5)))
EXPECTED_BLIND_SHA='5ab33685531475b3ad6cf4f69590c0af0925836679043d24ce2a44127ab7d4d1'
EPS=1e-14;PERSISTENCE=10;LOC_TOL=5

def sha(path):
    with path.open('rb') as s:return hashlib.file_digest(s,'sha256').hexdigest()
def load_json(path,max_bytes=32*1024*1024):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>max_bytes:raise ValueError('json_file')
    return json.loads(path.read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
def protocol():
    p=load_json(PROTOCOL)
    if p.get('schema_id')!='csi1000.scale_validity_market_protocol@1.0' or p.get('profile')!='two-wave-scale-validity-diagnostic-measurement-v1':raise ValueError('protocol')
    if set(p.get('files',{}))!=set(FILES) or p.get('reference_labels_visible_to_compute') is not False or p.get('threshold_selection_in_run') is not False:raise ValueError('scope')
    return p
def frames(p):
    out={}
    for n in FILES:
        f=cv.read_frame(INPUTS/n,n,p['files'][n]);f['audit_utc']=pd.to_datetime(f['timestamp'],utc=True);out[n]=f
    return out
def common_days(fs):
    c=set.intersection(*(cv.full_days(fs[n],n) for n in FILES));one=fs['1m_official.parquet']
    c&={d for d,g in one.groupby('audit_day') if d not in cv.EXCLUDED and bool(g['high_frequency_analysis_eligible'].all())}
    if len(c)!=1458:raise ValueError('common_days')
    return c
def sequence(one,common):
    m=one['audit_minute'];x=one.loc[one['audit_day'].isin(common)&(((m>=574)&(m<=686))|((m>=784)&(m<=896)))].copy().sort_values('timestamp').reset_index(drop=True)
    if len(x)!=1458*226:raise ValueError('common_sequence')
    x['audit_utc']=pd.to_datetime(x['timestamp'],utc=True);return x
def context(seq,row):
    minute={'11:00':660,'14:30':870}[row['anchor']];hits=seq.index[(seq['audit_day']==row['day'])&(seq['audit_minute']==minute)].tolist()
    if len(hits)!=1 or hits[0]<299:raise ValueError('context_support')
    x=seq.iloc[hits[0]-299:hits[0]+1].copy()
    if bool(x['causal_flat_fill'].any()):raise ValueError('context_causal_flat_fill')
    if not bool(x['high_frequency_analysis_eligible'].all()):raise ValueError('context_ineligible')
    x['relative_minute']=np.arange(-299,1,dtype=int);return x
def anchor_eligible(seq,common):
    ok=set();reasons=Counter()
    for day in sorted(common):
        row={'day':day,'anchor':rv._anchor(day)}
        try:x=context(seq,row)
        except ValueError as e:reasons[str(e)]+=1;continue
        allowed={(str(d),int(m)) for d,m in zip(x['audit_day'],x['audit_minute'])};days=sorted({d for d,_ in allowed});good=True
        for off in range(5):
            mins,_=cv.expected(f'5m_offset_{off}.parquet');count=0
            for d in days:
                for close in mins:
                    if (d,int(close)) not in allowed:continue
                    mem=cv.members(off,int(close))
                    if mem is not None and all((d,int(v)) in allowed for v in mem):count+=1
            if count<2:good=False;break
        if good:ok.add(day)
        else:reasons['phase_support']+=1
    if len(ok)!=1414 or dict(sorted(reasons.items()))!={'context_causal_flat_fill':43,'context_support':1}:raise ValueError('eligibility_identity')
    return ok
def phase_rows(fs,x):
    rel={t:int(r) for t,r in zip(x['audit_utc'],x['relative_minute'])}
    allowed={(str(d),int(m)) for d,m in zip(x['audit_day'],x['audit_minute'])};out={}
    for off in range(5):
        rows=[]
        frame=fs[f'5m_offset_{off}.parquet']
        for _,r in frame.loc[frame['audit_utc'].isin(rel)].iterrows():
            mem=cv.members(off,int(r['audit_minute']));d=str(r['audit_day'])
            if mem is None or any((d,int(v)) not in allowed for v in mem):continue
            values=(float(r['low']),float(r['close']),float(r['high']))
            if not all(math.isfinite(v) and v>0 for v in values) or not values[0]<=values[1]<=values[2]:raise ValueError('phase_price')
            rows.append((rel[r['audit_utc']],*values))
        rows=sorted(rows)
        if len(rows)<6 or len({r[0] for r in rows})!=len(rows):raise ValueError('phase_support')
        out[f'offset{off}']=rows
    return out

def one_minute(prices,rel):
    y=np.log(np.asarray(prices,float));r=np.asarray(rel,int);d=np.diff(y);a=np.abs(d);idx=int(np.argmax(a))+1
    jump=float(a[idx-1]);tv=float(a.sum());rng=float(y.max()-y.min());sign=0.0 if jump<=EPS else float(np.sign(d[idx-1]));support=min(PERSISTENCE,len(y)-idx);p=None
    if jump>EPS and support>=3:
        pre=float(y[idx-1]);p=float(np.median((y[idx:idx+support]-pre)*sign/jump))
    return {'close_jump_concentration':None if tv<=EPS else jump/tv,'close_range_concentration':None if rng<=EPS else jump/rng,
            'largest_close_jump_log':jump,'largest_close_jump_relative_minute':int(r[idx]),'jump_persistence_ratio':p,
            'jump_post_support':int(support),'log_range':rng,'total_variation':tv,'near_constant':bool(rng<=1e-10)}

def phase_measure(rows):
    arr=np.asarray(rows,float);rel=arr[:,0].astype(int);low=arr[:,1];closep=arr[:,2];high=arr[:,3]
    y=np.log(closep);d=np.abs(np.diff(y));idx=int(np.argmax(d))+1;lo=np.log(low);hi=np.log(high);rng=float(hi.max()-lo.min());w=[]
    for i in range(1,len(y)):
        upper=max(0.0,float(hi[i]-max(y[i-1],y[i])));lower=max(0.0,float(min(y[i-1],y[i])-lo[i]));w.append(max(upper,lower))
    wick=float(max(w)) if w else 0.0
    return {'largest_phase_close_jump_log':float(d[idx-1]),'largest_phase_close_jump_relative_minute':int(rel[idx]),
            'wick_only_concentration':None if rng<=EPS else wick/rng,'largest_wick_excess_log':wick,'phase_ohlc_log_range':rng}

def q(values):
    x=np.asarray([v for v in values if v is not None],float)
    if not len(x):return None
    return {'min':float(x.min()),'q25':float(np.quantile(x,.25)),'median':float(np.median(x)),'q75':float(np.quantile(x,.75)),'max':float(x.max())}

def panel(pid,x,rows):
    one=one_minute(x['close'].to_numpy(float),x['relative_minute'].to_numpy(int));ps={k:phase_measure(v) for k,v in rows.items()}
    loc=[p['largest_phase_close_jump_relative_minute'] for p in ps.values()];counts=[sum(abs(v-c)<=LOC_TOL for v in loc) for c in loc];one_loc=one['largest_close_jump_relative_minute']
    return {'panel_id':pid,'validity':{'schema_id':'csi1000.scale_validity_evidence@1.0','one_minute':one,'phases':ps,
      'phase_stability':{'largest_jump_relative_minute_range':int(max(loc)-min(loc)),'largest_jump_location_agreement_within_5m':int(max(counts)),
      'largest_jump_distance_to_1m':q([abs(v-one_loc) for v in loc]),'wick_only_concentration':q([p['wick_only_concentration'] for p in ps.values()])},
      'validity_state':'UNASSIGNED_THRESHOLD_FREE','threshold_selected':False}}

def close(a,b,path='root'):
    if isinstance(a,dict):
        if set(a)!=set(b):raise ValueError('dict_keys:'+path)
        for k in a:close(a[k],b[k],path+'.'+k)
    elif isinstance(a,list):
        if len(a)!=len(b):raise ValueError('list_len:'+path)
        for i,(x,y) in enumerate(zip(a,b)):close(x,y,f'{path}[{i}]')
    elif isinstance(a,(int,str,bool)) or a is None:
        if a!=b:raise ValueError('value:'+path)
    elif not math.isclose(float(a),float(b),rel_tol=2e-10,abs_tol=2e-10):raise ValueError('float:'+path)

def main():
    p=protocol();fs=frames(p);c=common_days(fs);seq=sequence(fs['1m_official.parquet'],c);eligible=anchor_eligible(seq,c);full=rv.derive(sorted(eligible));blind=rv.expected_blind(full)
    blind_raw=(json.dumps(blind,sort_keys=True,separators=(',',':'))+'\n').encode()
    if hashlib.sha256(blind_raw).hexdigest()!=EXPECTED_BLIND_SHA:raise ValueError('blind_hash')
    path=RESULTS/'validity_diagnostics.jsonl';lines=path.read_text().splitlines()
    if len(lines)!=192:raise ValueError('diagnostic_rows')
    got=[json.loads(v,parse_constant=lambda z:(_ for _ in ()).throw(ValueError(z))) for v in lines];order=[v['panel_id'] for v in blind]
    if [v['panel_id'] for v in got]!=order:raise ValueError('diagnostic_order')
    by={r['panel_id']:r for r in full}
    for g in got:
        row=by[g['panel_id']];x=context(seq,row);expected=panel(row['panel_id'],x,phase_rows(fs,x));close(g,expected)
    summary=load_json(RESULTS/'validity_summary.json');raw=path.read_bytes()
    if summary.get('validity_diagnostics_sha256')!=hashlib.sha256(raw).hexdigest() or summary.get('panels')!=192 or summary.get('reference_labels_joined') is not False or summary.get('numeric_validity_thresholds') is not None or summary.get('validity_state_assigned') is not False:raise ValueError('summary')
    manifest=load_json(RESULTS/'manifest.json')
    if manifest.get('reference_labels_visible_to_compute') is not False or manifest.get('threshold_selected') is not False:raise ValueError('manifest_scope')
    for n,m in manifest['files'].items():
        rp=RESULTS/n
        if m!={'bytes':rp.stat().st_size,'sha256':sha(rp)}:raise ValueError('manifest_identity')
    print(json.dumps({'status':'passed','panels_verified':192,'validity_diagnostics_sha256':summary['validity_diagnostics_sha256'],'reference_labels_joined':False,'threshold_selected':False,'production_authority':False},sort_keys=True,separators=(',',':')))
if __name__=='__main__':main()
