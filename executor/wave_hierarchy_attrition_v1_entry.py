"""Fixed market entry for aggregate hierarchy attrition audit."""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
from wave_hierarchy_attrition_v1 import analyze
FILES=('report.json',)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(bool,np.bool_)):return bool(x)
 if isinstance(x,(int,np.integer)):return int(x)
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 if x is None or isinstance(x,str):return x
 raise TypeError(type(x).__name__)
def encode(x):return (json.dumps(clean(x),sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def load_market(inputs):
 from two_wave_v0800_scale_map import load_bars
 p=Path(inputs)/'5m_offset_0.parquet'
 if p.is_symlink() or not p.is_file():raise ValueError('invalid fixed carrier')
 b=load_bars(p)
 if len(b)!=70114 or str(b.timestamp.iloc[0].date())!='2015-01-05' or str(b.timestamp.iloc[-1].date())!='2020-12-31':raise ValueError('development boundary drift')
 return b
def write_results(out,report):
 out=Path(out)
 if out.exists():raise ValueError('fresh output required')
 out.mkdir(parents=True);report=dict(report,data_role='PREVIOUSLY_CONSUMED_DEVELOPMENT_NOT_FRESH_OOS',source_data_sha256='bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48')
 raw=encode(report);(out/'report.json').write_bytes(raw);m={'files':{'report.json':{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}},'production_authority':False}
 (out/'manifest.json').write_bytes(encode(m))
def main():
 p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 if Path(a.inputs)!=Path('/work/inputs') or Path(a.out)!=Path('/results/study'):raise ValueError('fixed paths only')
 b=load_market(a.inputs);write_results(a.out,analyze(b))
if __name__=='__main__':main()
