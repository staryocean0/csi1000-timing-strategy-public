"""Read-only verifier for C3/router study."""
import argparse,hashlib,json
from pathlib import Path
from wave_c3_router_v1 import analyze
from wave_c3_router_v1_entry import FILES,load_market,encode,clean

def verify(bars,out):
    out=Path(out);expected=set(FILES)|{'manifest.json'}
    if {p.name for p in out.iterdir()}!=expected:raise ValueError('file set drift')
    mf=json.loads((out/'manifest.json').read_text());vals={}
    for name in FILES:
        raw=(out/name).read_bytes();meta=mf['files'][name]
        if meta!={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}:raise ValueError('hash drift')
        vals[name[:-5]]=json.loads(raw)
    report=vals.pop('report');r,l=analyze(bars)
    for k,v in r.items():
        if clean(v)!=report[k]:raise ValueError('report drift '+k)
    for k,v in l.items():
        if encode(v)!=encode(vals[k]):raise ValueError('ledger drift '+k)
    if report['authority']!={'scale_law':False,'router':False,'trade':False,'production':False}:raise ValueError('authority drift')
    return {'status':'passed','new_training':True,'production_authority':False,'c3_waves':report['recurrence']['complete_C3_waves'],'router_events':report['router']['eligible_context_episodes']}
def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--results',required=True);a=p.parse_args()
    if a.inputs!='/work/inputs' or a.results!='/results/study':raise ValueError('fixed paths')
    print(json.dumps(verify(load_market(a.inputs),a.results),sort_keys=True))
if __name__=='__main__':main()
