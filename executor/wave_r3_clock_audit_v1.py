"""Bounded in-memory diagnostics only. No market loading, CLI or file output.

Inputs must be inventories from the frozen R3 study. A separate reviewed
entry and verifier are required before any real-carrier execution.
"""
from collections import Counter
import hashlib
import numpy as np
from wave_recognizer_r1_v1 import _coverage, _runs, _episodes
from wave_recognizer_r3_v1_visuals import plan, _r2_floor_cases
from wave_multiscale_dual_gates_v2 import amp
from wave_r3_clock_probe_v1 import action, reset_bar_predicates

MAX_ROWS=70114


def dist(values):
    a=np.asarray(list(values),float)
    if not len(a): return dict(n=0,minimum=None,q25=None,median=None,q75=None,p90=None,maximum=None)
    return dict(n=len(a),minimum=float(a.min()),q25=float(np.quantile(a,.25)),
        median=float(np.median(a)),q75=float(np.quantile(a,.75)),p90=float(np.quantile(a,.9)),maximum=float(a.max()))


def token(text): return hashlib.sha256(text.encode()).hexdigest()[:16]


def latency_rows(candidate):
    events={(m['epoch'],m['candidate_occurrence_bar'],m['maturity_bar']):m for m in candidate['maturities']}
    if len(events)!=len(candidate['maturities']): raise ValueError('duplicate maturity key')
    result=[]
    for w in candidate['waves']:
        m=events[(w['epoch'],w['end_bar'],w['known_from_bar'])]
        delay=w['known_from_bar']-w['end_bar']
        gap=m['counter_occurrence_bar']-w['end_bar']
        survival=m['maturity_bar']-m['counter_occurrence_bar']
        if delay!=gap+survival or gap<4 or survival<4: raise ValueError('final-low latency identity failed')
        result.append(dict(wave_id=w['wave_id'],epoch=w['epoch'],final_low_occurrence=w['end_bar'],
            counter_occurrence=m['counter_occurrence_bar'],known_from_bar=w['known_from_bar'],
            occurrence_separation=gap,counter_survival=survival,confirmation_delay=delay))
    return result


def reset_summary(row,rows,closes):
    t,pre=row['bar_index'],row['pre']
    anchor=max(v for v in (pre['candidate'],pre['last_pivot']) if v is not None)
    segment=[r for r in rows[max(0,anchor):t] if r['pre']['epoch']==pre['epoch']]
    counts=Counter(action(r) for r in segment)
    ages=[r['bar_index']-r['pre']['pending_counter'] for r in segment if r['pre']['pending_counter'] is not None]
    boundary_restarts=sum(action(r)=='COUNTER_SUPERSEDE' and r['pre']['pending_counter'] is not None
        and r['bar_index']-r['pre']['pending_counter']>=4 for r in segment)
    return dict(reset_bar_predicates=reset_bar_predicates(row,closes),
        processed_action_counts=dict(sorted(counts.items())),pending_counter_prebar_age=dist(ages),
        counter_updates=sum(counts[k] for k in ('COUNTER_CREATE','COUNTER_SUPERSEDE')),
        maturity_boundary_supersessions=boundary_restarts,
        processed_subscale_rejections=counts['SUBSCALE_REJECT_REARM'],
        processed_mature_acceptances=counts['ACCEPT_MATURE_COUNTER'],
        chain_length_before_reset=pre['chain_n'],candidate_mode_before_reset=pre['mode'])


def control_summaries(bars,candidate,r1,r2,base,rows):
    panels=plan(bars,candidate,base,r2)
    cutoffs={p['wave_id']:p['cutoff'] for p in panels if p['kind']=='R2_MIN_LEG_LEG_CONTROL'}
    references={w['wave_id']:w for w in r2['waves']}
    answer=[]
    for item in _r2_floor_cases(r2):
        w=references[item['wave_id']];cutoff=cutoffs[item['wave_id']];containing=[]
        for v in candidate['waves']:
            if v['known_from_bar']>cutoff: continue
            for direction,s,e in [('UP',v['start_bar'],v['high_bar']),('DOWN',v['high_bar'],v['end_bar'])]:
                if s<=w['start_bar'] and e>=w['end_bar']:
                    containing.append(dict(direction=direction,leg_bars=e-s,
                        R1_complete_waves_inside=sum(z['start_bar']>=s and z['end_bar']<=e
                            and z['known_from_bar']<=cutoff for z in r1['waves'])))
        roles=[]
        for kind,i in [('low',w['start_bar']),('high',w['high_bar']),('low',w['end_bar'])]:
            view=rows[i:cutoff+1]
            exits=Counter(action(r) for r in view if r['pre']['pending_counter']==i
                and r['post']['pending_counter']!=i)
            roles.append(dict(kind=kind,
                confirmed_by_R3_asof_cutoff=any(p['kind']==kind and p['occurrence_bar']==i
                    and p['confirmation_bar']<=cutoff and not p['left_censored'] for p in candidate['pivots']),
                seen_as_R3_candidate=any(x['post']['candidate']==i for x in view),
                seen_as_R3_pending_counter=any(x['post']['pending_counter']==i for x in view),
                pending_exit_actions=dict(sorted(exits.items()))))
        answer.append(dict(case_id=item['id'],up_leg_bars=w['high_bar']-w['start_bar'],
            down_leg_bars=w['end_bar']-w['high_bar'],full_R2_wave_inside_one_R3_leg=bool(containing),
            containing_R3_legs=containing,R2_pivot_roles_under_R3=roles,
            interpretation='INTER_DETECTOR_DISAGREEMENT_NOT_AUTOMATIC_MISSED_WAVE'))
    return answer


def summarize(bars,parent,candidate,base,r1,r2,rows):
    n=len(bars)
    if not 0<n<=MAX_ROWS or len(rows)!=n: raise ValueError('bounded complete trace required')
    if [r['bar_index'] for r in rows]!=list(range(n)): raise ValueError('trace ordering')
    closes=bars.close.to_numpy(float)
    cover={k:_coverage(v['waves'],n) for k,v in [('original',base),('R1',r1),('R2',r2),('R3',candidate)]}
    reference=np.array([amp(w) for w in base['waves']])
    nonedge=[r for r in _episodes(bars,cover['R3'],reference) if not r['edge']]
    resets={r['bar_index']:r for r in candidate['resets']};cases=[]
    for ep in nonedge:
        s,e=ep['start'],ep['end'];targets=[t for t in resets if s<=t<=e]
        phase=None
        if targets:
            first=min(targets)
            phase=dict(before_first_reset_bars=first-s,reset_bars=len(targets),
                       after_first_reset_nonreset_bars=e-first+1-len(targets))
        cases.append(dict(case_id=token(f"{s}:{e}:{ep['amplitude_quartile']}"),bars=e-s+1,
            amplitude_quartile=ep['amplitude_quartile'],reset_count=len(targets),gap_phase_accounting=phase,
            originally_covered_bars=int(cover['original'][s:e+1].sum()),R1_covered_bars=int(cover['R1'][s:e+1].sum()),
            post_reset_actions=dict(sorted(Counter(action(rows[t]) for t in range(min(targets)+1,e+1)).items())) if targets else {},
            reset_evidence=[reset_summary(rows[t],rows,closes) for t in targets]))
    old=[(s,e) for s,e in _runs(~cover['R1']) if s>0 and e<n-1]
    new_r1=cover['original'] & ~cover['R1']
    old_cases=[dict(case_id=token(f'{s}:{e}'),bars=e-s+1,R3_recovered_bars=int(cover['R3'][s:e+1].sum()),
        prior_R1_new_bar_subset=int(new_r1[s:e+1].sum()),
        subset_recovered_bars=int((new_r1[s:e+1]&cover['R3'][s:e+1]).sum())) for s,e in old]
    lr=latency_rows(candidate)
    joint=Counter((r['occurrence_separation'],r['counter_survival'],r['confirmation_delay']) for r in lr)
    t0=parent['T0_bars'];q1=parent['baseline_reference']['amplitude_quartiles'][0];short={}
    for name,inv in [('original',base),('R1',r1),('R2',r2),('R3',candidate)]:
        low=[amp(w)<=q1 for w in inv['waves']];small=[w['duration']<=t0 for w in inv['waves']]
        total=len(low);count=sum(a and b for a,b in zip(low,small))
        short[name]=dict(waves=total,low_amplitude_count=sum(low),short_count=sum(small),joint_count=count,
                        joint_share=count/total if total else None)
    labels=Counter(reset_bar_predicates(rows[t],closes)['classification'] for t in resets)
    return dict(schema_id='csi1000.r3_clock_evidence_audit@1.0',research_issue=345,status='FROZEN_R3_EVIDENCE_ONLY',
        parent_run='35174316105-1',bars=n,data_role='PREVIOUSLY_CONSUMED_DEVELOPMENT_NOT_FRESH_OOS',
        frozen_R3_identity=dict(waves=len(candidate['waves']),pivots=len(candidate['pivots']),resets=len(candidate['resets']),
            rejections=len(candidate['rejections']),maturities=len(candidate['maturities'])),
        residual_cases=cases,reset_classification_counts=dict(sorted(labels.items())),
        classification_scope='OBSERVED_CLOCK_PREDICATES_NOT_COUNTERFACTUAL_REPAIR',
        R1_recovery=dict(cases=old_cases,episodes=len(old),bars=sum(e-s+1 for s,e in old),
            exact_92_subset_bars=int(new_r1.sum()),exact_92_subset_recovered=int((new_r1&cover['R3']).sum()),
            newly_blind_vs_R1_bars=int((cover['R1']&~cover['R3']).sum())),
        final_low_latency=dict(waves_accounted=len(lr),pointwise_identity_violations=0,
            occurrence_separation=dist(r['occurrence_separation'] for r in lr),
            counter_survival=dist(r['counter_survival'] for r in lr),confirmation_delay=dist(r['confirmation_delay'] for r in lr),
            joint_frequency=[dict(occurrence_separation=g,counter_survival=s,confirmation_delay=d,count=c)
                for (g,s,d),c in sorted(joint.items())]),
        joint_short_low_amplitude=dict(definition='DURATION_LE_T0_AND_AMPLITUDE_LE_ORIGINAL_Q1',
            T0_bars=t0,original_amplitude_Q1=q1,diagnostic_only=True,counts=short),
        R2_floor_controls=control_summaries(bars,candidate,r1,r2,base,rows),
        longest_R3_wave_bars=max((w['duration'] for w in candidate['waves']),default=0),
        causality_verification_pending=True,visual_manual_acceptance=False,R3_readiness_passed=False,
        R4_selected=False,one_minute_admitted=False,outcomes_used=False,new_training=False,
        authority=dict(signal=False,detector_repair=False,router=False,trade=False,production=False))
