"""Fixed dual-gate market entry. Must run inside the approved isolated runner.

Source-only synthetic tests call analyze() directly; they do not set runner
identity or read market files. This entry never downloads data or publishes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from wave_dual_gate_analysis_v1 import analyze

FILES=('report.json','base.json','hierarchy_A.json','hierarchy_B.json','events.json','oof.json','trades.json','sensitivity_trades.json')


def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,(bool,np.bool_)):return bool(x)
    if isinstance(x,(int,np.integer)):return int(x)
    if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
    if x is None or isinstance(x,str):return x
    raise TypeError(f'unsupported result value: {type(x).__name__}')


def encode(x):return (json.dumps(clean(x),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def load_market(inputs):
    from two_wave_v0800_scale_map import load_bars
    path=Path(inputs)/'5m_offset_0.parquet'
    if path.is_symlink() or not path.is_file():raise ValueError('invalid fixed carrier')
    bars=load_bars(path)
    if len(bars)!=70114 or str(bars.timestamp.iloc[0].date())!='2015-01-05' or str(bars.timestamp.iloc[-1].date())!='2020-12-31':
        raise ValueError('development boundary drift')
    return bars


def write_results(out,report,ledgers):
    out=Path(out)
    if out.exists():raise ValueError('fresh output directory required')
    out.mkdir(parents=True)
    report=dict(report,schema_id='csi1000.wave_dual_gate_trial@1.0',status='COMPUTED_NOT_PRODUCTION',
        data_role='PREVIOUSLY_CONSUMED_DEVELOPMENT',data_years=[2015,2020],source_data_sha256='bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48',
        operational_definition='20260916_v1_with_pre_market_implementation_addendum')
    values={'report':report,**ledgers}
    files={}
    for name in FILES:
        raw=encode(values[name[:-5]]);(out/name).write_bytes(raw)
        files[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    (out/'manifest.json').write_bytes(encode(dict(files=files,new_training=True,production_authority=False)))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args()
    if Path(args.inputs)!=Path('/work/inputs') or Path(args.out)!=Path('/results/study'):
        raise ValueError('market entry accepts only frozen runner paths')
    bars=load_market(args.inputs);report,ledgers=analyze(bars);write_results(args.out,report,ledgers)


if __name__=='__main__':main()
