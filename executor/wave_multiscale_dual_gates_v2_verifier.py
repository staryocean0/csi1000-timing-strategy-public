"""Read-only verifier for multiscale dual gates v2.
Report replay is reproducibility; base-kernel and causal-prefix checks are independent.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
from wave_multiscale_dual_gates_v2 import analyze,base_inventory,hierarchy,states_at
from wave_multiscale_dual_gates_v2_entry import FILES,load_market,encode,clean

def verify_base_kernel(bars,base):
    from two_wave_v0800_scale_map import TemporalMaturityAEngine
    engine=TemporalMaturityAEngine(bars);waves,pivots,resets=engine.run()
    exp=[(p['kind'],p['occurrence_bar'],p['confirmation_bar'],p['epoch'],p['left_censored']) for p in pivots]
    got=[(p['kind'],p['occurrence_bar'],p['known_from_bar'],p['epoch'],p['left_censored']) for p in base['pivots']]
    if exp!=got:raise ValueError('base pivot drift')
    if len(waves)!=len(base['waves']):raise ValueError('base wave count drift')
    for rec,w in zip(waves,base['waves']):
        q=rec.wave
        for k in ('start_bar','high_bar','end_bar','start_low','high','end_low'):
            if getattr(q,k)!=w[k]:raise ValueError('base anchor drift')
        if q.confirmation_bar!=w['known_from_bar']:raise ValueError('base confirmation drift')
    return {'pivots':len(pivots),'waves':len(waves),'resets':len(resets)}

def verify_prefixes(bars,ledgers,samples=24):
    candidates=ledgers['A_events']+ledgers['B_events']
    if not candidates:return 0
    picks=np.unique(np.linspace(0,len(candidates)-1,min(samples,len(candidates)),dtype=int));checked=0
    for i in picks:
        r=candidates[int(i)];t=r['decision_bar'];prefix=bars.iloc[:t+1].copy();b=base_inventory(prefix);h=hierarchy(b,1)
        full=states_at(ledgers['base'],ledgers['hierarchy'],t)
        part=states_at(b,h,t)
        def norm(s):
            if isinstance(s,dict):return {k:norm(v) for k,v in s.items() if k not in ('state_id','root_id','base_root_id')}
            return s
        if encode(norm(full))!=encode(norm(part)):raise ValueError('future suffix changes multiscale state')
        checked+=1
    return checked

def verify_scores(report,ledgers):
    for gate,key in (('A','A_oof'),('B','B_oof')):
        rows=ledgers[key];pooled=report[gate]['pooled']
        if pooled is None:
            if rows:raise ValueError('missing score summary')
            continue
        y=np.asarray([r['target'] for r in rows],float)
        for j in range(3):
            p=np.asarray([r[f'p{j}'] for r in rows],float)
            b=float(np.mean((p-y)**2));pp=np.clip(p,1e-12,1-1e-12);l=float(np.mean(-(y*np.log(pp)+(1-y)*np.log1p(-pp))))
            if not math.isclose(b,pooled['brier'][j],abs_tol=1e-12) or not math.isclose(l,pooled['logloss'][j],abs_tol=1e-12):raise ValueError('score arithmetic drift')
    return {'A':len(ledgers['A_oof']),'B':len(ledgers['B_oof'])}

def verify_results(bars,out):
    out=Path(out);expected=set(FILES)|{'manifest.json'}
    if out.is_symlink() or not out.is_dir() or {p.name for p in out.iterdir()}!=expected:raise ValueError('output set drift')
    manifest=json.loads((out/'manifest.json').read_text());values={}
    if manifest.get('new_training') is not True or manifest.get('production_authority') is not False:raise ValueError('authority drift')
    for name in FILES:
        raw=(out/name).read_bytes();meta={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        if manifest['files'][name]!=meta:raise ValueError('output hash drift')
        values[name[:-5]]=json.loads(raw)
    report=values.pop('report');rebuilt,ledgers=analyze(bars)
    for k,v in rebuilt.items():
        if clean(v)!=report[k]:raise ValueError('report reproduction drift '+k)
    for k,v in ledgers.items():
        if encode(v)!=encode(values[k]):raise ValueError('ledger reproduction drift '+k)
    independent={'base_kernel':verify_base_kernel(bars,ledgers['base']),'prefixes':verify_prefixes(bars,ledgers),'scores':verify_scores(report,ledgers)}
    for gate in ('A','B'):
        if report[gate]['verdict'].startswith('RETAIN') and not report[gate]['support_passed']:raise ValueError('unsupported retention')
    return {'status':'passed','scope':'replay_plus_independent_base_prefix_score_arithmetic','independent':independent,'new_training':True,'production_authority':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--results',required=True);a=p.parse_args()
    if a.inputs!='/work/inputs' or a.results!='/results/study':raise ValueError('fixed paths only')
    print(json.dumps(verify_results(load_market(a.inputs),a.results),sort_keys=True))
if __name__=='__main__':main()
