"""Supplemental independent scoring and calendar accounting for the frozen pilot.
Only synthetic CI or the approved isolated runner calls this module.
"""
from collections import Counter
import math
import numpy as np


def economics(rows, opens, day_index, T):
    """Allocate every settled-trade open-to-open increment and cost once.
    Inference uses 20-session blocks and length-2 circular moving blocks.
    An unclosed terminal trade is not fabricated; its censor remains upstream.
    """
    if not rows:
        return dict(blocks=0, interval=None, baseline_net_bps=0., filtered_net_bps=0., actual_filtered_two_sided_fast_loss_rate=None)
    first=min(int(day_index[r['entry_bar']])//20 for r in rows)
    last=max(int(day_index[r['exit_bar']])//20 for r in rows)
    values=np.zeros((last-first+1,2)); selected=[]
    for r in rows:
        entry,exit_=r['entry_bar'],r['exit_bar']
        if not 0 <= entry < exit_ < len(opens): raise ValueError('invalid fills')
        col=int(bool(r['selected']))
        for t in range(entry,exit_):
            inc=r['side']*math.log(opens[t+1]/opens[t])*10000
            block=int(day_index[t+1])//20-first
            values[block,0]+=inc
            if col: values[block,1]+=inc
        for t in (entry,exit_):
            block=int(day_index[t])//20-first
            values[block,0]-=2.
            if col: values[block,1]-=2.
        if col:selected.append(r)
    expected=sum(r['net_bps'] for r in rows)
    expected_selected=sum(r['net_bps'] for r in selected)
    if not math.isclose(values[:,0].sum(),expected,abs_tol=1e-7) or not math.isclose(values[:,1].sum(),expected_selected,abs_tol=1e-7):
        raise ValueError('calendar attribution does not conserve settled net returns')
    pairs=[bool(a['gross_log_return']<0 and b['gross_log_return']<0 and a['duration']<=T and b['duration']<=T and a['side']!=b['side']) for a,b in zip(selected,selected[1:])]
    ci=None
    if len(values)>=30:
        rng=np.random.default_rng(20260916);n=len(values)
        starts=rng.integers(0,n,(2000,(n+1)//2))
        indices=np.stack((starts,(starts+1)%n),axis=2).reshape(2000,-1)[:,:n]
        ci=np.quantile((values[:,1]-values[:,0])[indices].mean(axis=1),[.0125,.9875]).tolist()
    return dict(blocks=len(values),interval=ci,estimand='filtered_minus_baseline_net_bps_per_20_session_block',
        bootstrap='circular_moving_blocks_length_2',baseline_net_bps=float(values[:,0].sum()),filtered_net_bps=float(values[:,1].sum()),
        calendar_blocks=[dict(block=i+first,baseline=float(v[0]),filtered=float(v[1])) for i,v in enumerate(values)],
        actual_filtered_two_sided_fast_loss_rate=float(np.mean(pairs)) if pairs else None,
        actual_filtered_adjacent_pairs=len(pairs),cross_block_trades_preserved=True)


def verify_probabilities(events,oof):
    """Independent table rebuilding: do not call producer bin/probability/loss APIs."""
    settled=[r for r in events if r['status']=='SETTLED']; checked=0
    for year in (2018,2019,2020):
        tests=[r for r in settled if r['year']==year]
        predictions=[r for r in oof if r['year']==year]
        if not tests:
            if predictions:raise ValueError('unexpected predictions')
            continue
        start=min(r['fold_start'] for r in tests);groups={r['parent_id'] for r in tests}
        training=[r for r in settled if r['year']<year and r['mature_bar']<start and r['parent_id'] not in groups]
        if not training:
            if predictions:raise ValueError('untrained prediction')
            continue
        if [r['wave_id'] for r in predictions]!=[r['wave_id'] for r in tests]:raise ValueError('prediction population mismatch')
        fields=('parent_age','parent_strength','relative_amplitude')
        cuts={k:np.quantile([r[k] for r in training if math.isfinite(r[k])],[1/3,2/3]).tolist() for k in fields}
        def key(r):
            bins=tuple(sum(r[k]>=cut for cut in cuts[k]) for k in fields)
            k0=(r['direction'],bins[0],bins[1]);k1=k0+(r['nine'],bins[2])
            return (k0,k1,k1+(r['shape'],))
        counts=[Counter() for _ in range(3)];positives=[Counter() for _ in range(3)]
        for r in training:
            for i,k in enumerate(key(r)):counts[i][k]+=1;positives[i][k]+=r['target']
        prior=(sum(r['target'] for r in training)+1)/(len(training)+2)
        for r in predictions:
            probability=prior
            for i,k in enumerate(key(r)):
                probability=(positives[i][k]+20*probability)/(counts[i][k]+20)
                if not math.isclose(probability,r['p'+str(i)],rel_tol=0,abs_tol=1e-12):raise ValueError('independent table probability mismatch')
            checked+=1
    return checked


def verify_trade_sequence(bars,ledgers,T):
    """Independent exact entry/exit and filtering-time checks, including errors."""
    c=bars.close.to_numpy(float);o=bars.open.to_numpy(float);side=0;signals=[]
    for t in range(T,len(c)-1):
        new=1 if c[t]>max(c[t-T:t]) else -1 if c[t]<min(c[t-T:t]) else side
        if new!=side:signals.append((t,new));side=new
    count=0
    for name in ('trades','sensitivity_trades'):
        rows=ledgers[name]
        if len(rows)!=max(0,len(signals)-1):raise ValueError('trade count mismatch')
        for i,r in enumerate(rows):
            t,s=signals[i];ex=signals[i+1][0]+1;en=t+1
            if (r['signal_bar'],r['side'],r['entry_bar'],r['exit_bar'],r['duration'])!=(t,s,en,ex,ex-en):raise ValueError('independent exit clock mismatch')
            gross=s*math.log(o[ex]/o[en])
            if r['fast_loss']!=(ex-en<=T and gross<0):raise ValueError('fast-loss drift')
            bg=r['background']
            if bg.get('support_end',t)>t:raise ValueError('future background')
            if not math.isclose(r['net_bps'],gross*10000-4,abs_tol=1e-8):raise ValueError('net proxy drift')
            count+=1
    return count
