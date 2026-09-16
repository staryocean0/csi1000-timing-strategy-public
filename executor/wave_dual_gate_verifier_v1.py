"""Read-only verification: original kernels, causal prefixes, ledger arithmetic.

Report reconstruction uses the producer's analysis module (reproducibility,
not an independent statistical implementation). Kernel/label/trade checks
below are separate; neither a zero exit code nor equality grants market merit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from wave_dual_gate_hierarchy_v1 import base_inventory,hierarchy,background
from wave_dual_gate_analysis_v1 import analyze
from wave_dual_gate_study_v1 import load_market,encode,clean,FILES


def verify_ledger_arithmetic(bars,ledgers,T):
    close=bars.close.to_numpy(float);op=bars.open.to_numpy(float)
    side=0;signals=[]
    for t in range(T,len(close)-1):
        desired=1 if all(close[t]>x for x in close[t-T:t]) else -1 if all(close[t]<x for x in close[t-T:t]) else side
        if desired!=side:signals.append((t,desired));side=desired
    for name in ('trades','sensitivity_trades'):
        rows=ledgers[name]
        if [(r['signal_bar'],r['side']) for r in rows]!=signals[:-1]:raise ValueError('entry decision ledger drift')
        for i,r in enumerate(rows):
            if r['entry_bar']!=r['signal_bar']+1 or r['exit_bar']<=r['entry_bar']:
                raise ValueError('next-open clock drift')
            gross=r['side']*math.log(op[r['exit_bar']]/op[r['entry_bar']])
            if not math.isclose(gross,r['gross_log_return'],abs_tol=1e-12):raise ValueError('fill arithmetic drift')
            if not math.isclose(gross-.0004,r['net_log_return_proxy'],abs_tol=1e-12):raise ValueError('cost arithmetic drift')
            if r['two_sided_fast_loss'] is not None:
                if i+1>=len(rows):raise ValueError('unsettled two-trade target')
                expected=r['fast_loss'] and rows[i+1]['fast_loss'] and r['side']!=rows[i+1]['side']
                if bool(r['two_sided_fast_loss'])!=expected:raise ValueError('whipsaw arithmetic drift')
    for r in ledgers['oof']:
        if r['mature_bar']<r['decision_bar'] or any(not 0<=r['p'+str(i)]<=1 for i in range(3)):
            raise ValueError('invalid scored event')
        ctx=ledgers['hierarchy_A']['graphs'][0][r['parent_id'].rsplit(':e',1)[0]]
        ps=[p for p in ctx['pivots'] if p['epoch']==r['epoch'] and not p['left_censored']]
        end=r['decision_bar']+r['horizon'];kind='high' if r['direction']=='UP' else 'low'
        target=int(any(r['decision_bar']<p['occurrence_bar']<=end and p['kind']==kind for p in ps))
        closing=next((p for p in ps if p['occurrence_bar']>end),None)
        if target!=r['target'] or closing is None or closing['known_from_bar']!=r['mature_bar']:
            raise ValueError('future-turn target drift')


def verify_original_kernels(bars,ledgers):
    from two_wave_v0800_scale_map import TemporalMaturityAEngine
    from wave_skeleton_context_v1 import NodeMaturityEngine,ContextConfig
    engine=TemporalMaturityAEngine(bars);waves,pivots,resets=engine.run();base=ledgers['base']
    expected=[(p['kind'],p['occurrence_bar'],p['confirmation_bar'],p['epoch'],p['left_censored']) for p in pivots]
    actual=[(p['kind'],p['occurrence_bar'],p['known_from_bar'],p['epoch'],p['left_censored']) for p in base['pivots']]
    if expected!=actual:raise ValueError('frozen base pivot mismatch')
    if [(r['bar_index'],r['epoch']) for r in resets]!=[(r['known_from_bar'],r['epoch']) for r in base['resets']]:raise ValueError('frozen resets mismatch')
    columns=('start_bar','high_bar','end_bar','start_low','high','end_low')
    if len(waves)!=len(base['waves']):raise ValueError('frozen wave count mismatch')
    for ref,w in zip(waves,base['waves']):
        if any(getattr(ref.wave,k)!=w[k] for k in columns) or ref.wave.confirmation_bar!=w['known_from_bar']:
            raise ValueError('frozen OHLC anchors mismatch')
    for name in ('hierarchy_A','hierarchy_B'):
        h=ledgers[name]
        for depth,roots in enumerate(h['layers'][:-1]):
            for root in roots:
                reference=NodeMaturityEngine(root['root_id'],ContextConfig(min_leg_nodes=h['minimum']))
                for node in root['nodes']:reference.append(node)
                computed=h['graphs'][depth][root['root_id']]
                a=[(p['kind'],p['occurrence_bar'],p['known_from_bar'],p['parent_epoch'],p['left_censored']) for p in reference.pivots]
                b=[(p['kind'],p['occurrence_bar'],p['known_from_bar'],p['epoch'],p['left_censored']) for p in computed['pivots']]
                if a!=b:raise ValueError('frozen node maturity mismatch')
    return dict(base_pivots_checked=len(pivots),base_waves_checked=len(waves),hierarchy_kernels_checked=True)


def verify_prefixes(bars,ledgers,T,samples=24):
    rows=ledgers['trades'];indices=np.unique(np.linspace(0,len(rows)-1,min(samples,len(rows)),dtype=int)) if rows else []
    for i in indices:
        row=rows[int(i)];t=row['decision_bar'];prefix=bars.iloc[:t+1].copy()
        b=base_inventory(prefix);h=hierarchy(b,1)
        expected=background(b,h,prefix.close.to_numpy(float),t,T)
        if encode(expected)!=encode(row['background']):raise ValueError('future suffix changes background')
    from wave_dual_gate_hierarchy_v1 import parent_context,shape
    event_candidates=ledgers['events']
    picks=np.unique(np.linspace(0,len(event_candidates)-1,min(samples,len(event_candidates)),dtype=int)) if event_candidates else []
    fullbase=ledgers['base'];fullhier=ledgers['hierarchy_A']
    for i in picks:
        row=event_candidates[int(i)];t=row['decision_bar'];prefix=bars.iloc[:t+1].copy()
        b=base_inventory(prefix);h=hierarchy(b,2);w=b['waves'][-1]
        expected=parent_context(b,h,w['skeleton_root'],t)
        observed=parent_context(fullbase,fullhier,w['skeleton_root'],t)
        strip=lambda ctx:None if ctx is None else {k:v for k,v in ctx.items() if k!='graph'}
        if encode(strip(expected))!=encode(strip(observed)):raise ValueError('future suffix changes A context')
        if row['formation_cutoff_bar']!=row['pair_start_bar']-1:raise ValueError('formation clock contaminated')
        if any(encode(shape(prefix,w)[k])!=encode(row[k]) for k in shape(prefix,w)):raise ValueError('future suffix changes shape')
    return len(indices)+len(picks)


def verify_results(bars,out,check_original=True):
    out=Path(out)
    if out.is_symlink() or not out.is_dir():raise ValueError('invalid result root')
    expected=set(FILES)|{'manifest.json'}
    if {p.name for p in out.iterdir()}!=expected:raise ValueError('output set drift')
    manifest=json.loads((out/'manifest.json').read_text());values={}
    if manifest.get('new_training') is not True or manifest.get('production_authority') is not False:raise ValueError('scope drift')
    for name in FILES:
        path=out/name
        if path.is_symlink() or path.stat().st_size>100_000_000:raise ValueError('unsafe result')
        raw=path.read_bytes()
        if manifest['files'][name]!=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()):raise ValueError('output hash drift')
        values[name[:-5]]=json.loads(raw)
    report=values.pop('report');rebuilt,ledgers=analyze(bars)
    for k,v in rebuilt.items():
        if clean(v)!=report[k]:raise ValueError('report reproduction mismatch: '+k)
    for k,v in ledgers.items():
        if encode(v)!=encode(values[k]):raise ValueError('ledger reproduction mismatch: '+k)
    verify_ledger_arithmetic(bars,ledgers,report['T'])
    independent=verify_original_kernels(bars,ledgers) if check_original else {'original_kernel_check':'NOT_RUN_SYNTHETIC_ONLY'}
    for j in range(3):
        rs=ledgers['oof']
        if not rs:continue
        brier=sum((r['p'+str(j)]-r['target'])**2 for r in rs)/len(rs)
        loss=-sum(r['target']*math.log(max(1e-12,r['p'+str(j)]))+(1-r['target'])*math.log(max(1e-12,1-r['p'+str(j)])) for r in rs)/len(rs)
        if not math.isclose(brier,report['A']['pooled']['brier'][j],abs_tol=1e-12) or not math.isclose(loss,report['A']['pooled']['logloss'][j],abs_tol=1e-12):raise ValueError('independent scoring arithmetic mismatch')
    from wave_dual_gate_audit_v1 import verify_probabilities,verify_trade_sequence
    independent['probabilities_checked']=verify_probabilities(ledgers['events'],ledgers['oof'])
    independent['exact_trade_sequences_checked']=verify_trade_sequence(bars,ledgers,report['T'])
    checked=verify_prefixes(bars,ledgers,report['T'])
    for key in ('A','B'):
        if report[key]['verdict'].startswith('RETAIN') and not report[key]['support_passed']:raise ValueError('unsupported acceptance')
    return dict(status='passed',verification_scope='reproduction_plus_independent_kernel_label_fill_checks',
        independent=independent,prefixes_checked=checked,new_training=True,production_authority=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--results',required=True);a=p.parse_args()
    if a.inputs!='/work/inputs' or a.results!='/results/study':raise ValueError('unapproved verification paths')
    result=verify_results(load_market(a.inputs),a.results);print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
