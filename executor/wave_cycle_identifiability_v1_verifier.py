"""Read-only aggregate verifier for cycle identifiability audit."""
import argparse,hashlib,json
from pathlib import Path
from wave_cycle_identifiability_v1 import analyze
from wave_cycle_identifiability_v1_entry import load_market,encode,clean
def verify(bars,out):
 out=Path(out);expected={'report.json','manifest.json'}
 if {p.name for p in out.iterdir()}!=expected:raise ValueError('output set drift')
 m=json.loads((out/'manifest.json').read_text());raw=(out/'report.json').read_bytes()
 if m['files']['report.json']!={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}:raise ValueError('hash drift')
 observed=json.loads(raw);rebuilt=clean(analyze(bars))
 for k,v in rebuilt.items():
  if observed[k]!=v:raise ValueError('aggregate reproduction mismatch '+k)
 if observed['authority']['trade'] or observed['authority']['production']:raise ValueError('authority drift')
 return {'status':'passed','aggregate_only':True,'production_authority':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--results',required=True);a=p.parse_args()
 if a.inputs!='/work/inputs' or a.results!='/results/study':raise ValueError('fixed paths only')
 print(json.dumps(verify(load_market(a.inputs),a.results),sort_keys=True))
if __name__=='__main__':main()
