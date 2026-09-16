"""Fixed market entry for C3/router study."""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
from wave_c3_router_v1 import analyze
FILES=('report.json','base.json','hierarchy.json','c3_inventory.json','router_events.json','router_oof.json')
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,(bool,np.bool_)):return bool(x)
    if isinstance(x,(int,np.integer)):return int(x)
    if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
    if x is None or isinstance(x,str):return x
    raise TypeError(type(x).__name__)
def encode(x):return (json.dumps(clean(x),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def load_market(inputs):
    from two_wave_v0800_scale_map import load_bars
    path=Path(inputs)/'5m_offset_0.parquet'
    if path.is_symlink() or not path.is_file():raise ValueError('invalid carrier')
    bars=load_bars(path)
    if len(bars)!=70114 or str(bars.timestamp.iloc[0].date())!='2015-01-05' or str(bars.timestamp.iloc[-1].date())!='2020-12-31':raise ValueError('boundary drift')
    return bars
def write_results(out,report,ledgers):
    out=Path(out)
    if out.exists():raise ValueError('fresh output required')
    out.mkdir(parents=True);report=dict(report,data_role='PREVIOUSLY_CONSUMED_DEVELOPMENT_NOT_FRESH_OOS',data_years=[2015,2020],source_data_sha256='bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48')
    values={'report':report,**ledgers};mf={}
    for name in FILES:
        raw=encode(values[name[:-5]]);(out/name).write_bytes(raw);mf[name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    (out/'manifest.json').write_bytes(encode({'files':mf,'new_training':True,'production_authority':False}))
def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    if Path(a.inputs)!=Path('/work/inputs') or Path(a.out)!=Path('/results/study'):raise ValueError('fixed paths')
    bars=load_market(a.inputs);r,l=analyze(bars);write_results(a.out,r,l)
if __name__=='__main__':main()
