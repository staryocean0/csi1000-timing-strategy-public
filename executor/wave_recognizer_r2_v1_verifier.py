"""Independent R2 verifier: separate event replay, masks and OHLC evidence.

Full report reproduction is explicitly reproducibility; the event replay below
does not call EligibleCounterShadowEngine. No private transport or outcomes.
"""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
import xml.etree.ElementTree as ET
from wave_recognizer_r2_v1 import analyze
from wave_recognizer_r2_v1_entry import clean,load_market

MIN_LEG=4;MAX_AGE=48

def independent_pivots(bars):
 prices=bars.close.to_numpy(float);low=high=None;candidate=eligible=last=None;mode=0;epoch=0;out=[];resets=[]
 for t,p in enumerate(prices):
  if low is None:low=high=t;continue
  anchor=max(x for x in (last,candidate) if x is not None) if last is not None or candidate is not None else None
  if anchor is not None and t-anchor>MAX_AGE:
   resets.append((t,epoch,last));epoch+=1;mode=0;last=candidate=eligible=None;low=high=t;continue
  seed=False;kind=None;index=None
  if mode==0:
   low=t if p<prices[low] else low;high=t if p>prices[high] else high
   if high-low>=MIN_LEG:index=low;kind='low';mode=1;candidate=high;seed=True;eligible=None
   elif low-high>=MIN_LEG:index=high;kind='high';mode=-1;candidate=low;seed=True;eligible=None
  else:
   improvement=mode*(p-prices[candidate])
   if improvement>0:candidate=t;eligible=None;continue
   if improvement<0 and t-candidate>=MIN_LEG:
    if eligible is None or mode*(p-prices[eligible])<0:eligible=t
   if eligible is not None:
    index=candidate;kind='high' if mode==1 else 'low';mode=-mode;candidate=eligible;eligible=None
  if index is not None:out.append((kind,index,t,epoch,seed));last=index
 return out,resets

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

def _engine_wave_keys(candidate):
 return [(w['epoch'],w['start_bar'],w['high_bar'],w['end_bar'],w['known_from_bar'],w['start_low'],w['high'],w['end_low']) for w in candidate['waves']]

def verify_independent(bars,candidate,report):
 piv,resets=independent_pivots(bars);waves=independent_waves(bars,piv)
 observed=[(p['kind'],p['occurrence_bar'],p['confirmation_bar'],p['epoch'],p['left_censored']) for p in candidate['pivots']]
 if piv!=observed:raise ValueError('independent R2 pivot mismatch')
 if resets!=[(r['bar_index'],r['epoch'],r['previous_pivot_bar']) for r in candidate['resets']]:raise ValueError('independent R2 reset mismatch')
 if waves!=_engine_wave_keys(candidate):raise ValueError('independent R2 OHLC wave mismatch')
 # Every non-censored adjacent pivot in an epoch keeps the physical MIN_LEG scale.
 prev={};gaps=[]
 for kind,i,t,e,seed in piv:
  if seed:continue
  if e in prev:gaps.append(i-prev[e])
  prev[e]=i
 if any(g<MIN_LEG for g in gaps):raise ValueError('R2 pivot gap below MIN_LEG')
 if report['pivot_gap_audit']['below_MIN_LEG']!=0 or report['pivot_gap_audit']['all_ge_MIN_LEG'] is not True:raise ValueError('reported pivot gap audit drift')
 n=len(bars);delta=np.zeros(n+1,dtype=int)
 for e,a,h,b,t,lo,hi,endlo in waves:delta[a]+=1;delta[b+1]-=1
 covered=np.cumsum(delta[:-1])>0
 changes=np.diff(np.concatenate(([False],~covered,[False])).astype(int));starts=np.where(changes==1)[0];ends=np.where(changes==-1)[0]-1
 nonedge=[(int(a),int(b)) for a,b in zip(starts,ends) if a>0 and b<n-1]
 if sum(b-a+1 for a,b in nonedge)!=report['counts']['nonedge_blind_bars'] or len(nonedge)!=report['counts']['nonedge_blind_episodes']:raise ValueError('independent R2 blind mask mismatch')
 # Prefix replay: only already-confirmed waves/pivots/resets may exist.
 cuts=sorted(set(int(v) for v in np.linspace(0,n-1,min(8,n))));checked=0
 full_keys=waves
 for t in cuts:
  pp,rr=independent_pivots(bars.iloc[:t+1].copy());ww=independent_waves(bars.iloc[:t+1].copy(),pp)
  if ww!=[w for w in full_keys if w[4]<=t]:raise ValueError('future suffix changes R2 waves')
  if pp!=[p for p in piv if p[2]<=t] or rr!=[r for r in resets if r[0]<=t]:raise ValueError('future suffix changes R2 event ledger')
  checked+=len(ww)
 return {'pivots':len(piv),'waves':len(waves),'resets':len(resets),'minimum_pivot_gap':min(gaps) if gaps else None,'prefix_cutoffs':cuts,'confirmed_wave_comparisons':checked}

def verify(bars,out):
 out=Path(out);expected={'report.json','manifest.json','visuals'}
 if out.is_symlink() or not out.is_dir() or {p.name for p in out.iterdir()}!=expected:raise ValueError('output set drift')
 m=json.loads((out/'manifest.json').read_text());raw=(out/'report.json').read_bytes()
 if m['files']['report.json']!={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} or m.get('new_training') is not False or m.get('production_authority') is not False:raise ValueError('manifest drift')
 report=json.loads(raw);rebuilt,candidate,base,r1=analyze(bars)
 for k,v in clean(rebuilt).items():
  if report.get(k)!=v:raise ValueError('report reproduction: '+k)
 if report.get('data_role')!='PREVIOUSLY_CONSUMED_DEVELOPMENT_NOT_FRESH_OOS' or report.get('source_data_sha256')!='bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48':raise ValueError('data identity drift')
 independent=verify_independent(bars,candidate,report)
 from wave_recognizer_r2_v1_visuals import plan,render
 index=json.loads((out/'visuals'/'index.json').read_text());planned=plan(bars,candidate,base)
 if len(planned)!=len(index['panels']) or index.get('manual_acceptance') is not False:raise ValueError('visual plan drift')
 for p,entry in zip(planned,index['panels']):
  for k,v in p.items():
   if entry[k]!=v:raise ValueError('visual selection drift')
  file=out/'visuals'/entry['file'];data=file.read_bytes()
  if hashlib.sha256(data).hexdigest()!=entry['sha256'] or data!=render(bars,candidate,base,p).encode():raise ValueError('visual evidence drift')
  root=ET.fromstring(data);ns={'s':'http://www.w3.org/2000/svg'};candles=root.findall("s:g[@class='candle']",ns)
  if [int(c.attrib['data-bar-index']) for c in candles]!=list(range(p['first'],p['last']+1)):raise ValueError('missing original candles')
 if report['outcomes_used'] or report['one_minute_admitted'] or any(report['authority'].values()):raise ValueError('scope drift')
 return {'status':'passed','independent':independent,'visual_pages':len(index['panels']),'visual_manual_acceptance':False,'causality_passed':True,'production_authority':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--results',required=True);a=p.parse_args()
 if a.inputs!='/work/inputs' or a.results!='/results/study':raise ValueError('fixed paths only')
 print(json.dumps(verify(load_market(a.inputs),a.results),sort_keys=True))
if __name__=='__main__':main()
