"""R2 eligible-counter-shadow recognizer and aggregate readiness diagnostics.

Detector-quality research only. R2 keeps frozen R1 progress-aware reset and
changes one state semantic: an ineligible early opposite extreme may not block
later opposite evidence whose own occurrence is >= MIN_LEG bars from the live
candidate. No C2/C3 state, returns, PnL, routing, 1m or production authority.
"""
from __future__ import annotations
from collections import Counter
import hashlib, math
import numpy as np
from two_wave_v0800_scale_map import TemporalMaturityAEngine, MIN_LEG, MAX_UNFINISHED_LEG
from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_multiscale_dual_gates_v2 import amp
from wave_recognizer_r1_v1 import (
    candidate_inventory as r1_inventory,
    _coverage, _runs, _quartile, _summary, _raw_range, _episodes,
    _metrics, _old_blind_recovery,
)


class EligibleCounterShadowEngine(TemporalMaturityAEngine):
    """Frozen R1 reset clock + scale-eligible opposite counter.

    `counter` remains the legacy raw most-extreme opposite observation for
    diagnostics only. `eligible_counter` is independently updated only by
    opposite bars whose own occurrence is at least MIN_LEG after candidate.
    Confirmed pivot occurrence spacing therefore remains >= MIN_LEG.
    """
    def __init__(self, bars):
        super().__init__(bars)
        self.eligible_counter = None

    def reset(self, i: int) -> None:
        super().reset(i)
        self.eligible_counter = None

    def run(self):
        for i in range(len(self.bars)):
            if self.boot_low is None:
                self.boot_low=self.point(i,'low');self.boot_high=self.point(i,'high');continue
            progress=self.last_pivot_bar
            if self.candidate is not None:
                progress=self.candidate[0] if progress is None else max(progress,self.candidate[0])
            if progress is not None and i-progress>MAX_UNFINISHED_LEG:
                self.reset(i);continue
            if self.mode is None:
                self.bootstrap(i);self.eligible_counter=None;continue
            close=float(self.bars.iloc[i].close);candidate_close=self.candidate[1]
            improvement=self.mode*(close-candidate_close)
            if improvement>0:
                self.candidate=self.point(i,'high' if self.mode>0 else 'low')
                self.counter=None;self.eligible_counter=None;continue
            if improvement<0:
                kind='low' if self.mode>0 else 'high'
                if self.counter is None or self.mode*(close-self.counter[1])<0:
                    self.counter=self.point(i,kind)
                if i-self.candidate[0]>=MIN_LEG:
                    if self.eligible_counter is None or self.mode*(close-self.eligible_counter[1])<0:
                        self.eligible_counter=self.point(i,kind)
            if self.eligible_counter is not None:
                old=self.candidate;new=self.eligible_counter
                # Construction guarantees occurrence-time scale semantics.
                if new[0]-old[0] < MIN_LEG:
                    raise AssertionError('eligible counter violates MIN_LEG')
                self.confirm(old,i);self.mode*=-1;self.candidate=new
                self.counter=None;self.eligible_counter=None
        return self.waves,self.pivots,self.resets


def _wave_dict(rec):
    w=rec.wave
    a,h,b=map(math.log,(w.start_low,w.high,w.end_low));duration=w.end_bar-w.start_bar
    phase=(w.high_bar-w.start_bar)/duration
    height=h-(a+phase*(b-a))
    return dict(wave_id=w.wave_id,epoch=rec.epoch,start_bar=w.start_bar,high_bar=w.high_bar,end_bar=w.end_bar,
                start_low=w.start_low,high=w.high,end_low=w.end_low,confirmation_bar=w.confirmation_bar,
                known_from_bar=w.confirmation_bar,duration=duration,height_log=height,
                confirmation_delay=w.confirmation_bar-w.end_bar)


def candidate_inventory(bars):
    engine=EligibleCounterShadowEngine(bars);records,pivots,resets=engine.run()
    return dict(waves=[_wave_dict(r) for r in records],pivots=pivots,resets=resets)


def _reference_recovery(reference_cov,cand_cov):
    episodes=_runs(~reference_cov);nonedge=[(s,e) for s,e in episodes if s>0 and e<len(reference_cov)-1]
    bars=sum(e-s+1 for s,e in nonedge);recovered=sum(int(cand_cov[s:e+1].sum()) for s,e in nonedge)
    full=sum(bool(cand_cov[s:e+1].all()) for s,e in nonedge)
    return dict(nonedge_episodes=len(nonedge),nonedge_bars=bars,recovered_bars=recovered,
                recovered_bar_fraction=recovered/bars if bars else None,fully_recovered_episodes=full)


def _pivot_gap_audit(pivots):
    by_epoch={}
    gaps=[]
    for p in pivots:
        if p.get('left_censored'):continue
        e=p['epoch'];prev=by_epoch.get(e)
        if prev is not None:gaps.append(p['occurrence_bar']-prev)
        by_epoch[e]=p['occurrence_bar']
    return dict(n=len(gaps),minimum=min(gaps) if gaps else None,
                below_MIN_LEG=sum(g<MIN_LEG for g in gaps),all_ge_MIN_LEG=all(g>=MIN_LEG for g in gaps))


def analyze(bars):
    base=base_inventory(bars);r1=r1_inventory(bars);cand=candidate_inventory(bars);n=len(bars)
    base_cov=_coverage(base['waves'],n);r1_cov=_coverage(r1['waves'],n);cand_cov=_coverage(cand['waves'],n)
    ref=np.asarray([amp(w) for w in base['waves']],float);q1=float(np.quantile(ref,.25))
    initial=[w['duration'] for w in base['waves'] if int(bars.timestamp.iloc[w['known_from_bar']].year)<=2017]
    if not initial:raise ValueError('no frozen initial-period reference')
    T0=max(2,int(math.ceil(np.median(initial))))
    eps=_episodes(bars,cand_cov,ref);nonedge=[r for r in eps if not r['edge']]
    blind_bars=sum(r['bars'] for r in nonedge);substantial=[r for r in nonedge if r['amplitude_quartile'] in ('Q3','Q4')]
    substantial_bars=sum(r['bars'] for r in substantial);q1n=sum(r['amplitude_quartile']=='Q1' for r in nonedge)
    bm=_metrics(base['waves'],bars,q1);rm=_metrics(r1['waves'],bars,q1);cm=_metrics(cand['waves'],bars,q1)
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
    newly_blind=(r1_cov & ~cand_cov);new_blind_runs=_runs(newly_blind)
    ids=[hashlib.sha256(f"{r['start']}:{r['end']}:{r['amplitude_quartile']}".encode()).hexdigest()[:16] for r in substantial]
    return dict(schema_id='csi1000.recognizer_r2_eligible_counter_shadow@1.0',status='AGGREGATE_CANDIDATE_NOT_PRODUCTION',T0_bars=T0,
        counts=dict(bars=n,baseline_waves=len(base['waves']),r1_waves=len(r1['waves']),candidate_waves=len(cand['waves']),baseline_resets=len(base['resets']),r1_resets=len(r1['resets']),candidate_resets=len(cand['resets']),
                    nonedge_blind_episodes=len(nonedge),nonedge_blind_bars=blind_bars,substantial_blind_episodes=len(substantial),substantial_blind_bars=substantial_bars,
                    newly_blind_vs_R1_bars=int(newly_blind.sum()),newly_blind_vs_R1_segments=len(new_blind_runs)),
        blind_fraction_nonedge=blind_bars/n,residual_amplitude_counts=dict(sorted(Counter(r['amplitude_quartile'] for r in nonedge).items())),
        longest_substantial_blind_bars=max([r['bars'] for r in substantial],default=0),
        base_blind_recovery=_old_blind_recovery(base_cov,cand_cov),r1_blind_recovery=_reference_recovery(r1_cov,cand_cov),
        baseline_metrics=bm,r1_metrics=rm,candidate_metrics=cm,anti_oversegmentation=anti,pivot_gap_audit=_pivot_gap_audit(cand['pivots']),readiness_gates=gates,
        numeric_gate_pass=all(v for k,v in gates.items() if k not in ('causality','geometry_evidence')),
        residual_substantial_example_ids=ids,
        baseline_reference=dict(T0_basis='2015_2017_completed_base_median_ceil',amplitude_quartiles=np.quantile(ref,[.25,.5,.75]).tolist()),
        edge_censoring=dict(episodes=sum(r['edge'] for r in eps),bars=sum(r['bars'] for r in eps if r['edge']),all_blind_fraction=float((~cand_cov).mean())),
        residual_nonedge_episodes=[dict(id=hashlib.sha256(f"{r['start']}:{r['end']}:{r['amplitude_quartile']}".encode()).hexdigest()[:16],bars=r['bars'],amplitude_quartile=r['amplitude_quartile'],raw_log_range=r['raw_log_range'],reason='RESET_BREAK' if any(r['start']<=x['bar_index']<=r['end'] for x in cand['resets']) else 'UNFINISHED_OR_CROSS_RESET_CHAIN') for r in nonedge],
        per_year=[dict(year=int(y),bars=int((bars.timestamp.dt.year==y).sum()),baseline_blind_bars=int(((bars.timestamp.dt.year.to_numpy()==y)&~base_cov).sum()),r1_blind_bars=int(((bars.timestamp.dt.year.to_numpy()==y)&~r1_cov).sum()),candidate_blind_bars=int(((bars.timestamp.dt.year.to_numpy()==y)&~cand_cov).sum())) for y in sorted(set(bars.timestamp.dt.year))],
        one_minute_admitted=False,outcomes_used=False,new_training=False,
        authority=dict(signal=False,detector_repair=False,router=False,trade=False,production=False)),cand,base,r1
