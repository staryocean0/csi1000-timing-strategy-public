"""R1 progress-aware reset recognizer and aggregate readiness diagnostics.

Development detector-quality study only. No returns, PnL, routing, signals or
production authority. R1 changes one clock only: an unfinished leg is stale
48 bars after its latest candidate extreme, not 48 bars after the last pivot.
"""
from __future__ import annotations
from collections import Counter
import hashlib, math
import numpy as np
from two_wave_v0800_scale_map import TemporalMaturityAEngine, MIN_LEG, MAX_UNFINISHED_LEG
from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_multiscale_dual_gates_v2 import amp

class ProgressAwareAEngine(TemporalMaturityAEngine):
    def run(self):
        for i in range(len(self.bars)):
            if self.boot_low is None:
                self.boot_low=self.point(i,'low'); self.boot_high=self.point(i,'high'); continue
            progress=self.last_pivot_bar
            if self.candidate is not None:
                progress=self.candidate[0] if progress is None else max(progress,self.candidate[0])
            if progress is not None and i-progress>MAX_UNFINISHED_LEG:
                self.reset(i); continue
            if self.mode is None:
                self.bootstrap(i); continue
            close=float(self.bars.iloc[i].close); candidate_close=self.candidate[1]
            if self.mode*(close-candidate_close)>0:
                self.candidate=self.point(i,'high' if self.mode>0 else 'low'); self.counter=None; continue
            if self.mode*(close-candidate_close)<0:
                kind='low' if self.mode>0 else 'high'
                if self.counter is None or self.mode*(close-self.counter[1])<0:
                    self.counter=self.point(i,kind)
            if self.counter is not None and self.counter[0]-self.candidate[0]>=MIN_LEG:
                old=self.candidate; new=self.counter; self.confirm(old,i); self.mode*=-1; self.candidate=new; self.counter=None
        return self.waves,self.pivots,self.resets

def _wave_dict(rec):
    w=rec.wave
    a,h,b=map(math.log,(w.start_low,w.high,w.end_low)); duration=w.end_bar-w.start_bar
    phase=(w.high_bar-w.start_bar)/duration
    height=h-(a+phase*(b-a))
    return dict(wave_id=w.wave_id,epoch=rec.epoch,start_bar=w.start_bar,high_bar=w.high_bar,end_bar=w.end_bar,
                start_low=w.start_low,high=w.high,end_low=w.end_low,confirmation_bar=w.confirmation_bar,
                known_from_bar=w.confirmation_bar,duration=duration,height_log=height,
                confirmation_delay=w.confirmation_bar-w.end_bar)

def candidate_inventory(bars):
    engine=ProgressAwareAEngine(bars); records,pivots,resets=engine.run()
    return dict(waves=[_wave_dict(r) for r in records],pivots=pivots,resets=resets)

def _coverage(waves,n):
    out=np.zeros(n,dtype=bool)
    for w in waves: out[w['start_bar']:w['end_bar']+1]=True
    return out

def _runs(mask):
    out=[]; start=None
    for i,v in enumerate(mask):
        if v and start is None:start=i
        if start is not None and (not v or i==len(mask)-1):
            e=i if v and i==len(mask)-1 else i-1;out.append((start,e));start=None
    return out

def _quartile(v,ref):
    q=np.quantile(ref,[.25,.5,.75])
    return 'Q1' if v<=q[0] else 'Q2' if v<=q[1] else 'Q3' if v<=q[2] else 'Q4'
def _summary(values):
    x=np.asarray(values,float)
    if not len(x):return {'n':0,'q25':None,'median':None,'q75':None,'p90':None}
    q=np.quantile(x,[.25,.5,.75,.9]);return {'n':len(x),'q25':float(q[0]),'median':float(q[1]),'q75':float(q[2]),'p90':float(q[3])}
def _raw_range(bars,s,e):
    return float(math.log(float(bars.high.iloc[s:e+1].max())/float(bars.low.iloc[s:e+1].min())))
def _episodes(bars,covered,ref):
    rows=[]
    for s,e in _runs(~covered):
        q=_quartile(_raw_range(bars,s,e),ref)
        rows.append(dict(start=s,end=e,bars=e-s+1,edge=s==0 or e==len(bars)-1,amplitude_quartile=q,
                         raw_log_range=_raw_range(bars,s,e)))
    return rows

def _metrics(waves,bars,baseline_q1):
    amplitudes=[];dur=[];delay=[];heights=[]; years=Counter()
    for w in waves:
        amplitudes.append(amp(w));heights.append(w['height_log']);dur.append(w['duration']);delay.append(w.get('confirmation_delay',w['known_from_bar']-w['end_bar']))
        years[str(int(bars.timestamp.iloc[w['known_from_bar']].year))]+=1
    return dict(count=len(waves),waves_per_year=dict(sorted(years.items())),duration=_summary(dur),amplitude=_summary(amplitudes),
                channel_height=_summary(heights),confirmation_delay=_summary(delay),low_amplitude_share=float(np.mean(np.asarray(amplitudes)<=baseline_q1)) if amplitudes else None)
def _old_blind_recovery(base_cov,cand_cov):
    episodes=_runs(~base_cov);nonedge=[(s,e) for s,e in episodes if s>0 and e<len(base_cov)-1]
    bars=sum(e-s+1 for s,e in nonedge); recovered=sum(int(cand_cov[s:e+1].sum()) for s,e in nonedge)
    full=sum(bool(cand_cov[s:e+1].all()) for s,e in nonedge)
    return dict(nonedge_episodes=len(nonedge),nonedge_bars=bars,recovered_bars=recovered,
                recovered_bar_fraction=recovered/bars if bars else None,fully_recovered_episodes=full)
def analyze(bars):
    base=base_inventory(bars); cand=candidate_inventory(bars); n=len(bars)
    base_cov=_coverage(base['waves'],n); cand_cov=_coverage(cand['waves'],n)
    ref=np.asarray([amp(w) for w in base['waves']],float); q1=float(np.quantile(ref,.25)); initial=[w['duration'] for w in base['waves'] if int(bars.timestamp.iloc[w['known_from_bar']].year)<=2017]
    if not initial: raise ValueError('no frozen initial-period reference')
    T0=max(2,int(math.ceil(np.median(initial))))
    eps=_episodes(bars,cand_cov,ref); nonedge=[r for r in eps if not r['edge']]
    blind_bars=sum(r['bars'] for r in nonedge); substantial=[r for r in nonedge if r['amplitude_quartile'] in ('Q3','Q4')]
    substantial_bars=sum(r['bars'] for r in substantial); q1n=sum(r['amplitude_quartile']=='Q1' for r in nonedge)
    bm=_metrics(base['waves'],bars,q1);cm=_metrics(cand['waves'],bars,q1)
    anti=dict(wave_count_ratio=cm['count']/bm['count'],median_duration_ratio=cm['duration']['median']/bm['duration']['median'],
              median_amplitude_ratio=cm['amplitude']['median']/bm['amplitude']['median'],
              median_channel_height_ratio=cm['channel_height']['median']/bm['channel_height']['median'],
              low_amplitude_share_change=cm['low_amplitude_share']-bm['low_amplitude_share'],
              confirmation_delay_median_change=cm['confirmation_delay']['median']-bm['confirmation_delay']['median'],
              confirmation_delay_p90_change=cm['confirmation_delay']['p90']-bm['confirmation_delay']['p90'])
    anti_pass=(anti['wave_count_ratio']<=1.25 and anti['median_duration_ratio']>=.75 and anti['median_amplitude_ratio']>=.75 and anti['median_channel_height_ratio']>=.75 and
               anti['low_amplitude_share_change']<=.05 and anti['confirmation_delay_median_change']<=4 and anti['confirmation_delay_p90_change']<=8)
    gates=dict(coverage=blind_bars/n<=.02,substantial_misses=len(substantial)<=5 and substantial_bars/n<=.0025,
               residual_character=(q1n/len(nonedge)>=.90 if nonedge else True),
               no_long_substantial=all(r['bars']<=1.5*T0 for r in substantial),no_oversegmentation=anti_pass,
               causality=False,geometry_evidence=False,no_outcome_tuning=True)
    ids=[hashlib.sha256(f"{r['start']}:{r['end']}:{r['amplitude_quartile']}".encode()).hexdigest()[:16] for r in substantial]
    return dict(schema_id='csi1000.recognizer_r1_progress_reset@1.0',status='AGGREGATE_CANDIDATE_NOT_PRODUCTION',T0_bars=T0,
        counts=dict(bars=n,baseline_waves=len(base['waves']),candidate_waves=len(cand['waves']),baseline_resets=len(base['resets']),candidate_resets=len(cand['resets']),
                    nonedge_blind_episodes=len(nonedge),nonedge_blind_bars=blind_bars,substantial_blind_episodes=len(substantial),substantial_blind_bars=substantial_bars),
        blind_fraction_nonedge=blind_bars/n,residual_amplitude_counts=dict(sorted(Counter(r['amplitude_quartile'] for r in nonedge).items())),
        longest_substantial_blind_bars=max([r['bars'] for r in substantial],default=0),old_blind_recovery=_old_blind_recovery(base_cov,cand_cov),
        baseline_metrics=bm,candidate_metrics=cm,anti_oversegmentation=anti,readiness_gates=gates,
        numeric_gate_pass=all(v for k,v in gates.items() if k not in ('causality','geometry_evidence')),
        residual_substantial_example_ids=ids,
        baseline_reference=dict(T0_basis='2015_2017_completed_base_median_ceil',amplitude_quartiles=np.quantile(ref,[.25,.5,.75]).tolist()),
        edge_censoring=dict(episodes=sum(r['edge'] for r in eps),bars=sum(r['bars'] for r in eps if r['edge']),all_blind_fraction=float((~cand_cov).mean())),
        residual_nonedge_episodes=[dict(id=hashlib.sha256(f"{r['start']}:{r['end']}:{r['amplitude_quartile']}".encode()).hexdigest()[:16],bars=r['bars'],amplitude_quartile=r['amplitude_quartile'],raw_log_range=r['raw_log_range'],reason='RESET_BREAK' if any(r['start']<=x['bar_index']<=r['end'] for x in cand['resets']) else 'UNFINISHED_OR_CROSS_RESET_CHAIN') for r in nonedge],
        per_year=[dict(year=int(y),bars=int((bars.timestamp.dt.year==y).sum()),baseline_blind_bars=int(((bars.timestamp.dt.year.to_numpy()==y)&~base_cov).sum()),candidate_blind_bars=int(((bars.timestamp.dt.year.to_numpy()==y)&~cand_cov).sum())) for y in sorted(set(bars.timestamp.dt.year))],
        one_minute_admitted=False,outcomes_used=False,new_training=False,
        authority=dict(signal=False,detector_repair=False,router=False,trade=False,production=False)),cand,base
