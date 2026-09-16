"""Self-contained R1 verifier: separate array replay, masks, gates and OHLC evidence.
Full report replay is labelled reproducibility; separate replay below does not
call the candidate engine. No private transport or market downloads here.
"""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
import xml.etree.ElementTree as ET
from wave_recognizer_r1_v1 import analyze,ProgressAwareAEngine
from wave_recognizer_r1_v1_entry import clean,load_market


def independent_pivots(bars):
    prices=bars.close.to_numpy(float); low=high=None; candidate=counter=last=None; mode=0;epoch=0;out=[];resets=[]
    for t,p in enumerate(prices):
        if low is None:low=high=t;continue
        anchor=max(x for x in (last,candidate) if x is not None) if last is not None or candidate is not None else None
        if anchor is not None and t-anchor>48:
            resets.append((t,epoch,last));epoch+=1;mode=0;last=candidate=counter=None;low=high=t;continue
        seed=False;kind=None;index=None
        if mode==0:
            low=t if p<prices[low] else low;high=t if p>prices[high] else high
            if high-low>=4:index=low;kind='low';mode=1;candidate=high;seed=True
            elif low-high>=4:index=high;kind='high';mode=-1;candidate=low;seed=True
        else:
            improvement=mode*(p-prices[candidate])
            if improvement>0:candidate=t;counter=None;continue
            if improvement<0 and (counter is None or mode*(p-prices[counter])<0):counter=t
            if counter is not None and counter-candidate>=4:
                index=candidate;kind='high' if mode==1 else 'low';mode=-mode;candidate=counter;counter=None
        if index is not None:out.append((kind,index,t,epoch,seed));last=index
    return out,resets


def wave_key(record):
    w=record.wave
    return (record.epoch,w.start_bar,w.high_bar,w.end_bar,w.confirmation_bar,w.start_low,w.high,w.end_low)


def independent_waves(bars,pivots):
    chain=[];epoch=None;result=[]
    for kind,i,t,e,seed in pivots:
        if epoch!=e:chain=[];epoch=e
        if seed:continue
        chain.append((kind,i))
        if len(chain)>=3 and [x[0] for x in chain[-3:]]==['low','high','low']:
            a,h,b=[x[1] for x in chain[-3:]]
            result.append((e,a,h,b,t,float(bars.low.iloc[a]),float(bars.high.iloc[h]),float(bars.low.iloc[b])))
    return result


def checked_replays(bars):
    from two_wave_v0800_scale_map import TemporalMaturityAEngine
    full,piv,reset=ProgressAwareAEngine(bars).run();expected,ex_reset=independent_pivots(bars)
    observed=[(p['kind'],p['occurrence_bar'],p['confirmation_bar'],p['epoch'],p['left_censored']) for p in piv]
    if expected!=observed:raise ValueError('independent candidate pivot mismatch')
    if ex_reset!=[(r['bar_index'],r['epoch'],r['previous_pivot_bar']) for r in reset]:raise ValueError('independent candidate reset mismatch')
    if [wave_key(r) for r in full]!=independent_waves(bars,expected):raise ValueError('independent candidate OHLC wave mismatch')
    from wave_dual_gate_hierarchy_v1 import base_inventory
    base=base_inventory(bars);old,old_p,old_r=TemporalMaturityAEngine(bars).run()
    old_keys=[(w['epoch'],w['start_bar'],w['high_bar'],w['end_bar'],w['known_from_bar'],w['start_low'],w['high'],w['end_low']) for w in base['waves']]
    if [wave_key(r) for r in old]!=old_keys:raise ValueError('frozen base wave mismatch')
    if [(r['bar_index'],r['epoch']) for r in old_r]!=[(r['known_from_bar'],r['epoch']) for r in base['resets']]:raise ValueError('frozen base reset mismatch')
    cuts=sorted(set(int(v) for v in np.linspace(0,len(bars)-1,min(8,len(bars)))))
    count=0
    for t in cuts:
        records,pp,rr=ProgressAwareAEngine(bars.iloc[:t+1].copy()).run()
        if [wave_key(r) for r in records]!=[wave_key(r) for r in full if r.wave.confirmation_bar<=t]:raise ValueError('future suffix changes candidate waves')
        if pp!=[p for p in piv if p['confirmation_bar']<=t] or rr!=[r for r in reset if r['bar_index']<=t]:raise ValueError('future suffix changes event ledger')
        count+=len(records)
    return dict(candidate_waves=len(full),candidate_pivots=len(piv),candidate_resets=len(reset),baseline_waves=len(old),prefix_cutoffs=cuts,confirmed_wave_comparisons=count),full,old


def independent_numeric(bars,report,records,old):
    n=len(bars)
    def mask(rs):
        delta=np.zeros(n+1,dtype=int)
        for r in rs:delta[r.wave.start_bar]+=1;delta[r.wave.end_bar+1]-=1
        return np.cumsum(delta[:-1])>0
    def amplitude(r):
        w=r.wave;a,h,b=map(math.log,(w.start_low,w.high,w.end_low));height=h-(a+(w.high_bar-w.start_bar)/w.duration*(b-a));return max(height,h-min(a,b))
    covered=mask(records);base_mask=mask(old);ref=np.array([amplitude(r) for r in old]);qs=np.quantile(ref,[.25,.5,.75]);segments=[]
    changes=np.diff(np.concatenate(([False],~covered,[False])).astype(int));starts=np.where(changes==1)[0];ends=np.where(changes==-1)[0]-1
    for a,b in zip(starts,ends):
        if a==0 or b==n-1:continue
        value=math.log(float(bars.high.iloc[a:b+1].max())/float(bars.low.iloc[a:b+1].min()));q=1+int(np.searchsorted(qs,value,side='left'));segments.append((int(b-a+1),q))
    blind=sum(z for z,q in segments);large=[z for z,q in segments if q>=3];T=max(2,int(math.ceil(np.median([r.wave.duration for r in old if bars.timestamp.iloc[r.wave.confirmation_bar].year<=2017]))))
    expected=dict(nonedge_blind_episodes=len(segments),nonedge_blind_bars=blind,substantial_blind_episodes=len(large),substantial_blind_bars=sum(large))
    if any(report['counts'][k]!=v for k,v in expected.items()):raise ValueError('independent blind accounting mismatch')
    amps=np.array([amplitude(r) for r in records]);dur=np.array([r.wave.duration for r in records]);base_dur=np.array([r.wave.duration for r in old])
    height=lambda r:math.log(r.wave.high)-(math.log(r.wave.start_low)+(r.wave.high_bar-r.wave.start_bar)/r.wave.duration*math.log(r.wave.end_low/r.wave.start_low))
    delay=np.array([r.wave.confirmation_bar-r.wave.end_bar for r in records]);base_delay=np.array([r.wave.confirmation_bar-r.wave.end_bar for r in old])
    anti=(len(records)<=1.25*len(old) and np.median(dur)>=.75*np.median(base_dur) and np.median(amps)>=.75*np.median(ref) and np.median([height(r) for r in records])>=.75*np.median([height(r) for r in old]) and np.mean(amps<=qs[0])-np.mean(ref<=qs[0])<=.05 and np.median(delay)-np.median(base_delay)<=4 and np.quantile(delay,.9)-np.quantile(base_delay,.9)<=8)
    gates=dict(coverage=blind/n<=.02,substantial_misses=len(large)<=5 and sum(large)/n<=.0025,residual_character=not segments or sum(q==1 for z,q in segments)/len(segments)>=.90,no_long_substantial=all(z<=1.5*T for z in large),no_oversegmentation=bool(anti),no_outcome_tuning=True)
    if any(report['readiness_gates'][k]!=v for k,v in gates.items()) or report['numeric_gate_pass']!=all(gates.values()):raise ValueError('independent numeric verdict mismatch')
    if report['T0_bars']!=T:raise ValueError('baseline T0 drift')
    return dict(mask_accounting='passed',numeric_gates=gates)


def verify(bars,out):
    out=Path(out);expected={'report.json','manifest.json','visuals'}
    if out.is_symlink() or not out.is_dir() or {p.name for p in out.iterdir()}!=expected:raise ValueError('output set drift')
    m=json.loads((out/'manifest.json').read_text());raw=(out/'report.json').read_bytes()
    if (out/'report.json').is_symlink() or m['files']['report.json']!={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} or m.get('new_training') is not False or m.get('production_authority') is not False:raise ValueError('manifest drift')
    report=json.loads(raw);rebuilt,candidate,base=analyze(bars)
    for k,v in clean(rebuilt).items():
        if report.get(k)!=v:raise ValueError('report reproduction: '+k)
    if report.get('data_role')!='PREVIOUSLY_CONSUMED_DEVELOPMENT_NOT_FRESH_OOS' or report.get('source_data_sha256')!='bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48':raise ValueError('data identity drift')
    replay,records,old=checked_replays(bars);numeric=independent_numeric(bars,report,records,old)
    from wave_recognizer_r1_v1_visuals import plan,render
    index=json.loads((out/'visuals'/'index.json').read_text());planned=plan(bars,candidate,base);panels=index['panels']
    if len(planned)!=len(panels) or index['manual_acceptance'] is not False:raise ValueError('visual plan drift')
    for p,entry in zip(planned,panels):
        for k,v in p.items():
            if entry[k]!=v:raise ValueError('visual selection drift')
        name='case-'+p['id']+'.svg';file=out/'visuals'/name
        if file.is_symlink():raise ValueError('unsafe image path')
        data=file.read_bytes()
        if entry['file']!=name or hashlib.sha256(data).hexdigest()!=entry['sha256'] or len(data)!=entry['bytes'] or data!=render(bars,candidate,base,p).encode():raise ValueError('visual evidence drift')
        root=ET.fromstring(data);ns={'s':'http://www.w3.org/2000/svg'};candles=root.findall("s:g[@class='candle']",ns)
        if [int(c.attrib['data-bar-index']) for c in candles]!=list(range(p['first'],p['last']+1)):raise ValueError('missing original candles')
    if report['outcomes_used'] or report['one_minute_admitted'] or any(report['authority'].values()):raise ValueError('scope drift')
    return dict(status='passed',replay=replay,numeric=numeric,visual_pages=len(panels),visual_manual_acceptance=False,causality_passed=True,production_authority=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--results',required=True);a=p.parse_args()
    if a.inputs!='/work/inputs' or a.results!='/results/study':raise ValueError('fixed paths only')
    print(json.dumps(verify(load_market(a.inputs),a.results),sort_keys=True))
if __name__=='__main__':main()
