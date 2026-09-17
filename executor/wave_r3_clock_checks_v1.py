"""Pure independent trace checks; no market loader, output adapter or dispatch."""
import numpy as np
from wave_r3_clock_probe_v1 import replay, pivot_key
from wave_recognizer_r3_v1_verifier import independent_waves


def check_trace(bars,observed,rows):
    if not 0<len(bars)<=70114 or len(rows)!=len(bars): raise ValueError('trace row bound')
    records,pivots,resets,rejects,mature=observed
    expected=replay(bars.close.to_numpy(float))
    for name,value in [('rows',rows),('pivots',pivots),('resets',resets),
                       ('rejections',rejects),('maturities',mature)]:
        if value!=expected[name]: raise ValueError('independent trace mismatch: '+name)
    emitted=[(r.epoch,r.wave.start_bar,r.wave.high_bar,r.wave.end_bar,r.wave.confirmation_bar,
              r.wave.start_low,r.wave.high,r.wave.end_low) for r in records]
    keys=[tuple(pivot_key(p)) for p in expected['pivots']]
    if emitted!=independent_waves(bars,keys): raise ValueError('independent wave geometry mismatch')
    return dict(trace_rows=len(rows),pivots=len(pivots),waves=len(records),resets=len(resets),
                rejections=len(rejects),maturities=len(mature))


def independent_coverage(waves,n):
    delta=np.zeros(n+1,dtype=np.int64)
    for w in waves:
        a,b=w['start_bar'],w['end_bar']
        if not 0<=a<=b<n: raise ValueError('wave outside carrier')
        delta[a]+=1;delta[b+1]-=1
    return np.cumsum(delta[:-1])>0


def check_subset_counts(summary,base,r1,r3,n):
    bc=independent_coverage(base['waves'],n);a=independent_coverage(r1['waves'],n)
    c=independent_coverage(r3['waves'],n);subset=bc & ~a
    expected=dict(exact_92_subset_bars=int(subset.sum()),
        exact_92_subset_recovered=int((subset&c).sum()),newly_blind_vs_R1_bars=int((a&~c).sum()))
    for k,v in expected.items():
        if summary['R1_recovery'][k]!=v: raise ValueError('independent subset mismatch: '+k)
    # Closed-interval gap partitions must not count the reset twice.
    for case in summary['residual_cases']:
        phase=case['gap_phase_accounting']
        if phase is not None and sum(phase.values())!=case['bars']:
            raise ValueError('gap partition mismatch')
    return expected
