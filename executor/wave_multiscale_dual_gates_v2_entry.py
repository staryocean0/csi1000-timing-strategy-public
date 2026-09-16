"""Fixed market entry for multiscale dual gates v2."""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
from wave_multiscale_dual_gates_v2 import analyze

FILES=('report.json','base.json','hierarchy.json','A_events.json','A_oof.json','B_events.json','B_oof.json','trades.json')

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
    if path.is_symlink() or not path.is_file():raise ValueError('invalid fixed carrier')
    bars=load_bars(path)
    if len(bars)!=70114 or str(bars.timestamp.iloc[0].date())!='2015-01-05' or str(bars.timestamp.iloc[-1].date())!='2020-12-31':raise ValueError('development boundary drift')
    return bars

def write_results(out,report,ledgers):
    out=Path(out)
    if out.exists():raise ValueError('fresh output directory required')
    out.mkdir(parents=True)
    report=dict(report,data_role='PREVIOUSLY_CONSUMED_DEVELOPMENT_NOT_FRESH_OOS',data_years=[2015,2020],source_data_sha256='bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48',operational_definition='multiscale_graphical_v2_20260916')
    values={'report':report,**ledgers};manifest={}
    for name in FILES:
        raw=encode(values[name[:-5]]);(out/name).write_bytes(raw);manifest[name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    (out/'manifest.json').write_bytes(encode({'files':manifest,'new_training':True,'production_authority':False}))

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    if Path(a.inputs)!=Path('/work/inputs') or Path(a.out)!=Path('/results/study'):raise ValueError('fixed runner paths only')
    bars=load_market(a.inputs);report,ledgers=analyze(bars);write_results(a.out,report,ledgers)
if __name__=='__main__':main()
