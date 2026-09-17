"""R3 mature-counter-rearm recognizer and frozen-readiness diagnostics.

Detector-quality research only. R3 preserves frozen R1 progress-aware reset,
MIN_LEG=4 and MAX_UNFINISHED_LEG=48. It separates two causal clocks:
(1) pivot occurrence separation and (2) survival/maturity of the opposite
extremum. No amplitude/volatility threshold, returns, PnL, 1m or authority.
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
    _coverage, _runs, _episodes, _metrics, _old_blind_recovery,
)
from wave_recognizer_r2_v1 import (
    candidate_inventory as r2_inventory,
    _wave_dict, _reference_recovery, _pivot_gap_audit,
)


class MatureCounterRearmEngine(TemporalMaturityAEngine):
    """R1 reset clock + counter-extremum survival + subscale rejection.

    A newly observed/more-extreme opposite close becomes `counter_candidate`.
    It cannot confirm on that bar. It must survive MIN_LEG subsequent bars
    without being superseded. On maturity, its occurrence must also be at least
    MIN_LEG from the live pivot candidate. A mature but too-close counter is
    rejected from the pivot chain and the search rearms on the next bar.
    """
    def __init__(self, bars):
        super().__init__(bars)
        self.counter_candidate = None
        self.rejections = []
        self.maturities = []

    def reset(self, i: int) -> None:
        super().reset(i)
        self.counter_candidate = None

    def run(self):
        for i in range(len(self.bars)):
            if self.boot_low is None:
                self.boot_low = self.point(i, 'low')
                self.boot_high = self.point(i, 'high')
                continue

            # Frozen R1 progress-aware stale clock.
            progress = self.last_pivot_bar
            if self.candidate is not None:
                progress = self.candidate[0] if progress is None else max(progress, self.candidate[0])
            if progress is not None and i - progress > MAX_UNFINISHED_LEG:
                self.reset(i)
                continue

            if self.mode is None:
                self.bootstrap(i)
                self.counter_candidate = None
                continue

            close = float(self.bars.iloc[i].close)
            candidate_close = self.candidate[1]
            improvement = self.mode * (close - candidate_close)

            if improvement > 0:
                self.candidate = self.point(i, 'high' if self.mode > 0 else 'low')
                self.counter = None
                self.counter_candidate = None
                continue

            updated_counter = False
            if improvement < 0:
                kind = 'low' if self.mode > 0 else 'high'
                # Retain legacy raw counter only as a diagnostic state.
                if self.counter is None or self.mode * (close - self.counter[1]) < 0:
                    self.counter = self.point(i, kind)
                if self.counter_candidate is None or self.mode * (close - self.counter_candidate[1]) < 0:
                    self.counter_candidate = self.point(i, kind)
                    updated_counter = True

            # Frozen processing order: a counter created/superseded on this bar
            # restarts its survival clock and cannot mature on the same bar.
            if updated_counter:
                continue

            if self.counter_candidate is not None and i - self.counter_candidate[0] >= MIN_LEG:
                new = self.counter_candidate
                occurrence_gap = new[0] - self.candidate[0]
                event = dict(
                    epoch=self.epoch,
                    candidate_occurrence_bar=self.candidate[0],
                    counter_occurrence_bar=new[0],
                    maturity_bar=i,
                    survival_bars=i-new[0],
                    occurrence_gap=occurrence_gap,
                    counter_kind=new[2],
                )
                if occurrence_gap >= MIN_LEG:
                    old = self.candidate
                    self.maturities.append(dict(event, status='ACCEPTED_MATURE_COUNTER'))
                    self.confirm(old, i)
                    self.mode *= -1
                    self.candidate = new
                    self.counter = None
                    self.counter_candidate = None
                else:
                    self.rejections.append(dict(event, status='SUBSCALE_REJECTED'))
                    # Fresh search begins on the NEXT bar; no retrospective replay.
                    self.counter = None
                    self.counter_candidate = None
        return self.waves, self.pivots, self.resets, self.rejections, self.maturities


def candidate_inventory(bars):
    engine = MatureCounterRearmEngine(bars)
    records, pivots, resets, rejections, maturities = engine.run()
    return dict(
        waves=[_wave_dict(r) for r in records],
        pivots=pivots,
        resets=resets,
        rejections=rejections,
        maturities=maturities,
    )


def _dist(values):
    a=np.asarray(list(values),float)
    if not len(a):return dict(n=0,minimum=None,q25=None,median=None,q75=None,p90=None,maximum=None)
    return dict(n=int(len(a)),minimum=float(a.min()),q25=float(np.quantile(a,.25)),median=float(np.quantile(a,.5)),q75=float(np.quantile(a,.75)),p90=float(np.quantile(a,.9)),maximum=float(a.max()))


def analyze(bars):
    base=base_inventory(bars);r1=r1_inventory(bars);r2=r2_inventory(bars);cand=candidate_inventory(bars);n=len(bars)
    base_cov=_coverage(base['waves'],n);r1_cov=_coverage(r1['waves'],n);r2_cov=_coverage(r2['waves'],n);cand_cov=_coverage(cand['waves'],n)
    ref=np.asarray([amp(w) for w in base['waves']],float);q1=float(np.quantile(ref,.25))
    initial=[w['duration'] for w in base['waves'] if int(bars.timestamp.iloc[w['known_from_bar']].year)<=2017]
    if not initial:raise ValueError('no frozen initial-period reference')
    T0=max(2,int(math.ceil(np.median(initial))))
    eps=_episodes(bars,cand_cov,ref);nonedge=[r for r in eps if not r['edge']]
    blind_bars=sum(r['bars'] for r in nonedge);substantial=[r for r in nonedge if r['amplitude_quartile'] in ('Q3','Q4')]
    substantial_bars=sum(r['bars'] for r in substantial);q1n=sum(r['amplitude_quartile']=='Q1' for r in nonedge)
    bm=_metrics(base['waves'],bars,q1);rm=_metrics(r1['waves'],bars,q1);r2m=_metrics(r2['waves'],bars,q1);cm=_metrics(cand['waves'],bars,q1)
    anti=dict(
        wave_count_ratio=cm['count']/bm['count'],
        median_duration_ratio=cm['duration']['median']/bm['duration']['median'],
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
    rejects=cand['rejections'];mature=cand['maturities']
    return dict(
        schema_id='csi1000.recognizer_r3_mature_counter_rearm@1.0',
        status='AGGREGATE_CANDIDATE_NOT_PRODUCTION',T0_bars=T0,
        counts=dict(bars=n,baseline_waves=len(base['waves']),r1_waves=len(r1['waves']),r2_waves=len(r2['waves']),candidate_waves=len(cand['waves']),
                    baseline_resets=len(base['resets']),r1_resets=len(r1['resets']),r2_resets=len(r2['resets']),candidate_resets=len(cand['resets']),
                    nonedge_blind_episodes=len(nonedge),nonedge_blind_bars=blind_bars,substantial_blind_episodes=len(substantial),substantial_blind_bars=substantial_bars,
                    newly_blind_vs_R1_bars=int(newly_blind.sum()),newly_blind_vs_R1_segments=len(new_blind_runs),
                    subscale_rejections=len(rejects),accepted_mature_counters=len(mature)),
        blind_fraction_nonedge=blind_bars/n,
        residual_amplitude_counts=dict(sorted(Counter(r['amplitude_quartile'] for r in nonedge).items())),
        longest_substantial_blind_bars=max([r['bars'] for r in substantial],default=0),
        base_blind_recovery=_old_blind_recovery(base_cov,cand_cov),
        r1_blind_recovery=_reference_recovery(r1_cov,cand_cov),
        r2_blind_recovery=_reference_recovery(r2_cov,cand_cov),
        baseline_metrics=bm,r1_metrics=rm,r2_metrics=r2m,candidate_metrics=cm,
        anti_oversegmentation=anti,pivot_gap_audit=_pivot_gap_audit(cand['pivots']),readiness_gates=gates,
        numeric_gate_pass=all(v for k,v in gates.items() if k not in ('causality','geometry_evidence')),
        subscale_rejection_diagnostics=dict(
            occurrence_gap=_dist(r['occurrence_gap'] for r in rejects),
            survival_bars=_dist(r['survival_bars'] for r in rejects)),
        accepted_counter_diagnostics=dict(
            occurrence_gap=_dist(r['occurrence_gap'] for r in mature),
            survival_bars=_dist(r['survival_bars'] for r in mature)),
        r2_failure_reference=dict(
            formal_public_run_id='35163544010-1',
            formal_decision='REJECT_R2_FOR_5M_READINESS',
            frozen_wave_count_ratio=1.7359168997203356,
            frozen_median_duration_ratio=.6666666666666666,
            frozen_low_amplitude_share_change=.10479079879748449),
        residual_substantial_example_ids=ids,
        baseline_reference=dict(T0_basis='2015_2017_completed_base_median_ceil',amplitude_quartiles=np.quantile(ref,[.25,.5,.75]).tolist()),
        edge_censoring=dict(episodes=sum(r['edge'] for r in eps),bars=sum(r['bars'] for r in eps if r['edge']),all_blind_fraction=float((~cand_cov).mean())),
        residual_nonedge_episodes=[dict(id=hashlib.sha256(f"{r['start']}:{r['end']}:{r['amplitude_quartile']}".encode()).hexdigest()[:16],bars=r['bars'],amplitude_quartile=r['amplitude_quartile'],raw_log_range=r['raw_log_range'],reason='RESET_BREAK' if any(r['start']<=x['bar_index']<=r['end'] for x in cand['resets']) else 'UNFINISHED_OR_CROSS_RESET_CHAIN') for r in nonedge],
        per_year=[dict(year=int(y),bars=int((bars.timestamp.dt.year==y).sum()),baseline_blind_bars=int(((bars.timestamp.dt.year.to_numpy()==y)&~base_cov).sum()),r1_blind_bars=int(((bars.timestamp.dt.year.to_numpy()==y)&~r1_cov).sum()),r2_blind_bars=int(((bars.timestamp.dt.year.to_numpy()==y)&~r2_cov).sum()),candidate_blind_bars=int(((bars.timestamp.dt.year.to_numpy()==y)&~cand_cov).sum())) for y in sorted(set(bars.timestamp.dt.year))],
        one_minute_admitted=False,outcomes_used=False,new_training=False,
        authority=dict(signal=False,detector_repair=False,router=False,trade=False,production=False)),cand,base,r1,r2
