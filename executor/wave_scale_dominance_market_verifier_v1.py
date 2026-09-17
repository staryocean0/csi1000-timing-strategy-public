"""Independent verifier for issue #372 market diagnostics.

Does not import the market measurement producer or wave_scale_dominance_diagnostics_v1.
"""
from __future__ import annotations
from collections import Counter
import hashlib,json,math
from pathlib import Path
import numpy as np
import pandas as pd
import wave_segmentation_carrier_verifier_v1 as cv
import wave_scale_reference_verifier_v2 as rv

INPUTS=Path('/work/inputs');RESULTS=Path('/results/study');PROTOCOL=Path('/work/scale_dominance_measurement/protocol.json')
FILES=('1m_official.parquet',*(f'5m_offset_{i}.parquet' for i in range(5)))
EXPECTED_BLIND_SHA='5ab33685531475b3ad6cf4f69590c0af0925836679043d24ce2a44127ab7d4d1'
MIN_SIDE=3;EPS=1e-14;VAR_FLOOR=1e-24

def sha(path):
    with path.open('rb') as s:return hashlib.file_digest(s,'sha256').hexdigest()
def load_json(path,max_bytes=32*1024*1024):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>max_bytes:raise ValueError('json_file')
    return json.loads(path.read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
def protocol():
    p=load_json(PROTOCOL)
    if p.get('schema_id')!='csi1000.scale_dominance_market_protocol@1.0' or p.get('profile')!='two-wave-scale-dominance-diagnostic-measurement-v1':raise ValueError('protocol')
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
    rel={t:int(r) for t,r in zip(x['audit_utc'],x['relative_minute'])};allowed={(str(d),int(m)) for d,m in zip(x['audit_day'],x['audit_minute'])};out={}
    for off in range(5):
        rows=[]
        for _,r in fs[f'5m_offset_{off}.parquet'].loc[fs[f'5m_offset_{off}.parquet']['audit_utc'].isin(rel)].iterrows():
            mem=cv.members(off,int(r['audit_minute']));d=str(r['audit_day'])
            if mem is None or any((d,int(v)) not in allowed for v in mem):continue
            rows.append((rel[r['audit_utc']],float(r['close'])))
        rows=sorted(rows)
        if len(rows)<6:raise ValueError('phase_support')
        out[f'offset{off}']=rows
    return out

def fit(y,X):
    b,_,rank,_=np.linalg.lstsq(X,y,rcond=None);res=y-X@b;sse=float(res@res);sst=float(((y-y.mean())@(y-y.mean())));n,k=X.shape
    r2=None if sst<=EPS else float(1-sse/sst);bic=float(n*math.log(max(sse/n,VAR_FLOOR))+k*math.log(n))
    return b,res,sse,r2,bic,int(rank)
def lag1(r):
    if len(r)<3:return None
    a,b=r[:-1],r[1:]
    if float(np.std(a))<=EPS or float(np.std(b))<=EPS:return 0.0
    return float(np.corrcoef(a,b)[0,1])
def outlier(r):
    c=float(np.median(r));mad=float(np.median(np.abs(r-c)));peak=float(np.max(np.abs(r-c)))
    if mad<=EPS:
        return (None,False) if peak<=EPS else (None,True)
    v=float(peak/(1.4826*mad))
    return (v,False) if math.isfinite(v) else (None,True)
def measure(rows):
    rel=[r[0] for r in rows];y=np.log(np.asarray([r[1] for r in rows],float));n=len(y);t=np.linspace(-1,1,n)
    level=fit(y,np.ones((n,1)));trend=fit(y,np.column_stack([np.ones(n),t]));bg=min([('LEVEL',level,1),('ONE_LEG_TREND',trend,2)],key=lambda z:(z[1][4],z[2],z[0]))
    eligible=list(range(2,n-2));pen=2*math.log(len(eligible));cand=[]
    for turn in eligible:
        knot=t[turn];X=np.column_stack([np.ones(n),t,np.maximum(t-knot,0.0)]);f=fit(y,X);pre=float(f[0][1]);post=float(f[0][1]+f[0][2]);shape='PEAK' if pre>0 and post<0 else ('TROUGH' if pre<0 and post>0 else 'NO_REVERSAL')
        cand.append((f[4]+pen,f[4],turn,f,shape))
    cand.sort(key=lambda z:(z[0],z[1],z[2]));a,b=cand[0],cand[1];f=a[3];turn=a[2]
    rng=float(y.max()-y.min());tv=float(np.abs(np.diff(y)).sum());sser=None if bg[1][2]<=EPS else float(f[2]/bg[1][2]);rmse=math.sqrt(f[2]/n)
    outlier_value,outlier_nonfinite=outlier(f[1])
    return {'bars':n,'relative_start_minute':rel[0],'relative_end_minute':rel[-1],'eligible_knots':len(eligible),'search_penalty':pen,
      'background_selected':bg[0],'background_bic':bg[1][4],'background_sse':bg[1][2],'background_r2':bg[1][3],
      'best_turn_index':turn,'best_turn_relative_minute':rel[turn],'left_bars':turn+1,'right_bars':n-turn,'left_fraction':(turn+1)/n,'right_fraction':(n-turn)/n,
      'shape':a[4],'raw_piecewise_bic':f[4],'search_adjusted_bic':a[0],'delta_search_adjusted_bic_vs_background':a[0]-bg[1][4],
      'second_best_search_adjusted_bic':b[0],'best_second_adjusted_bic_gap':b[0]-a[0],
      'fractional_sse_improvement':None if sser is None else 1-sser,'delta_r2_vs_background':None if f[3] is None or bg[1][3] is None else f[3]-bg[1][3],
      'normalized_rmse_to_log_range':None if rng<=EPS else rmse/rng,'residual_lag1':lag1(f[1]),'robust_outlier_score':outlier_value,
      'robust_outlier_score_nonfinite':outlier_nonfinite,'near_constant':rng<=1e-10,'log_range':rng,'total_variation':tv,'tortuosity':None if rng<=EPS else tv/rng}
def q(values):
    x=np.asarray(values,float);return {'min':float(x.min()),'q25':float(np.quantile(x,.25)),'median':float(np.median(x)),'q75':float(np.quantile(x,.75)),'max':float(x.max())}
def panel(pid,rows):
    ps={k:measure(v) for k,v in rows.items()};turns=[p['best_turn_relative_minute'] for p in ps.values()];sh=Counter(p['shape'] for p in ps.values())
    def qs(k):return q([p[k] for p in ps.values() if p[k] is not None])
    return {'panel_id':pid,'phase_count':5,'phases':ps,'phase_stability':{'turn_relative_minute':q(turns),'turn_relative_minute_range':int(max(turns)-min(turns)),'shape_counts':dict(sorted(sh.items())),'shape_agreement_max':max(sh.values()),'bars':qs('bars'),'delta_search_adjusted_bic_vs_background':qs('delta_search_adjusted_bic_vs_background'),'fractional_sse_improvement':qs('fractional_sse_improvement'),'normalized_rmse_to_log_range':qs('normalized_rmse_to_log_range'),'residual_lag1':qs('residual_lag1'),'robust_outlier_score':qs('robust_outlier_score'),'tortuosity':qs('tortuosity')},'dominance_state':'UNASSIGNED_THRESHOLD_FREE','threshold_selected':False}
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
    lines=(RESULTS/'diagnostics.jsonl').read_text().splitlines()
    if len(lines)!=192:raise ValueError('diagnostic_rows')
    got=[json.loads(x,parse_constant=lambda z:(_ for _ in ()).throw(ValueError(z))) for x in lines];order=[x['panel_id'] for x in blind]
    if [x['panel_id'] for x in got]!=order:raise ValueError('diagnostic_order')
    by={r['panel_id']:r for r in full}
    for g in got:
        row=by[g['panel_id']];x=context(seq,row);expected=panel(row['panel_id'],phase_rows(fs,x));close(g,expected)
    summary=load_json(RESULTS/'diagnostic_summary.json');raw=(RESULTS/'diagnostics.jsonl').read_bytes()
    if summary.get('diagnostics_sha256')!=hashlib.sha256(raw).hexdigest() or summary.get('panels')!=192 or summary.get('reference_labels_joined') is not False or summary.get('numeric_state_thresholds') is not None:raise ValueError('summary')
    manifest=load_json(RESULTS/'manifest.json')
    if manifest.get('reference_labels_joined') is not False or manifest.get('threshold_selected') is not False:raise ValueError('manifest_scope')
    for n,m in manifest['files'].items():
        path=RESULTS/n
        if m!={'bytes':path.stat().st_size,'sha256':sha(path)}:raise ValueError('manifest_identity')
    print(json.dumps({'status':'passed','panels_verified':192,'phase_rows_verified':960,'diagnostics_sha256':summary['diagnostics_sha256'],'reference_labels_joined':False,'threshold_selected':False,'production_authority':False},sort_keys=True,separators=(',',':')))
if __name__=='__main__':main()
