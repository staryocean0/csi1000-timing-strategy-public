"""Independent file-level verifier for issue #352.

Does not import the producer/entry qualification module.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

INPUTS=Path('/work/inputs')
RESULTS=Path('/results/study')
PROTOCOL=Path('/work/segmentation_carrier/protocol.json')
FILES=('1m_official.parquet',*(f'5m_offset_{i}.parquet' for i in range(5)))
PRICE=('open','high','low','close')
EXCLUDED=frozenset({'2016-01-04','2016-01-07','2017-08-24','2020-04-20'})
ABS_TOL=1e-10
REL_TOL=1e-12


def sha(path:Path)->str:
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def blob(path:Path)->str:
    raw=path.read_bytes();return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def expected(name:str):
    if name=='1m_official.parquet':
        values=list(range(571,691))+list(range(781,901))
    else:
        offset=int(name.split('_')[-1].split('.')[0])
        values=list(range(575+offset,691,5))+list(range(785+offset,901,5))
    return values,{f'{m//60:02d}:{m%60:02d}' for m in values}


def parse_bool(values:pd.Series)->pd.Series:
    if values.dtype==bool:return values
    mapped=values.map({True:True,False:False,1:True,0:False,'true':True,'false':False,'True':True,'False':False})
    if mapped.isna().any():raise ValueError('boolean')
    return mapped.astype(bool)


def read_frame(path:Path,name:str,meta:dict)->pd.DataFrame:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1:raise ValueError('input_type')
    if path.stat().st_size!=meta['bytes'] or sha(path)!=meta['sha256'] or blob(path)!=meta['git_blob_sha1']:
        raise ValueError('identity')
    frame=pd.read_parquet(path)
    required={'symbol','timestamp','trading_day',*PRICE}
    if not required.issubset(frame.columns) or len(frame)!=meta['declared_rows']:raise ValueError('schema')
    utc=pd.to_datetime(frame['timestamp'],utc=True,errors='coerce')
    if utc.isna().any() or utc.duplicated().any() or not utc.is_monotonic_increasing:raise ValueError('time')
    local=utc.dt.tz_convert('Asia/Shanghai')
    if 'bar_end_shanghai' in frame:
        other=pd.to_datetime(frame['bar_end_shanghai'],utc=True,errors='coerce')
        if other.isna().any() or not bool((other==utc).all()):raise ValueError('shanghai_time')
    out=frame.copy();out['audit_day']=out['trading_day'].astype(str).str[:10]
    out['audit_clock']=local.dt.strftime('%H:%M');out['audit_minute']=local.dt.hour*60+local.dt.minute
    if set(out['symbol'].astype(str))!={'000852.SH'}:raise ValueError('symbol')
    if out['audit_day'].min()!='2015-01-05' or out['audit_day'].max()!='2020-12-31':raise ValueError('boundary')
    if not bool((local.dt.strftime('%Y-%m-%d')==out['audit_day']).all()):raise ValueError('local_day')
    values=out[list(PRICE)].apply(pd.to_numeric,errors='coerce').to_numpy(float)
    if not np.isfinite(values).all() or np.any(values<=0):raise ValueError('price')
    if np.any(values[:,2]>np.min(values,axis=1)) or np.any(values[:,1]<np.max(values,axis=1)):raise ValueError('ohlc')
    _,clocks=expected(name)
    if not bool(out['audit_clock'].isin(clocks).all()):raise ValueError('clock')
    for day,part in out.groupby('audit_day'):
        if day not in EXCLUDED and set(part['audit_clock'])!=clocks:raise ValueError('incomplete_day')
    if name=='1m_official.parquet':
        if not {'causal_flat_fill','high_frequency_analysis_eligible'}.issubset(out.columns):raise ValueError('flags')
        out['causal_flat_fill']=parse_bool(out['causal_flat_fill'])
        out['high_frequency_analysis_eligible']=parse_bool(out['high_frequency_analysis_eligible'])
    return out


def members(offset:int,close:int):
    if 570<=close<=690:start=570
    elif 780<=close<=900:start=780
    else:return None
    grid=start+offset;first=grid+5
    if close<first or (close-first)%5:return None
    if close==first:return list(range(start if offset==0 else grid,first+1))
    return list(range(close-4,close+1))


def aggregate(part:pd.DataFrame)->np.ndarray:
    x=part[list(PRICE)].to_numpy(float)
    return np.asarray([x[0,0],x[:,1].max(),x[:,2].min(),x[-1,3]],float)


def verify_reconstruction(one:pd.DataFrame,five:pd.DataFrame,offset:int)->dict:
    lookup={(d,int(m)):i for i,(d,m) in enumerate(zip(one['audit_day'],one['audit_minute']))}
    categories=Counter();compared=matched=mismatched=exact=0;max_abs=max_rel=0.0
    _,clocks=expected(f'5m_offset_{offset}.parquet')
    for _,row in five.iterrows():
        day=str(row['audit_day']);clock=str(row['audit_clock']);close=int(row['audit_minute'])
        if day in EXCLUDED:categories['EXCLUDED_DAY']+=1;continue
        if clock not in clocks:categories['UNEXPECTED_CLOCK']+=1;continue
        points=members(offset,close)
        if points is None:categories['BUCKET_CONTRACT_ERROR']+=1;continue
        if offset==0 and points[0] in (570,780):categories['SOURCE_MINUTE_NOT_EXPORTED']+=1;continue
        idx=[lookup.get((day,m)) for m in points]
        if any(i is None for i in idx):categories['MISSING_1M_CONSTITUENT']+=1;continue
        part=one.iloc[idx]
        if not bool(part['high_frequency_analysis_eligible'].all()):categories['INELIGIBLE_1M_DAY']+=1;continue
        if bool(part['causal_flat_fill'].any()):categories['CAUSAL_FLAT_FILL']+=1;continue
        calc=aggregate(part);target=row[list(PRICE)].to_numpy(dtype=float);compared+=1
        delta=np.abs(calc-target);rel=delta/np.maximum(np.maximum(np.abs(calc),np.abs(target)),1e-300)
        max_abs=max(max_abs,float(delta.max()));max_rel=max(max_rel,float(rel.max()))
        good=(delta<=ABS_TOL)|(delta<=REL_TOL*np.maximum(np.abs(calc),np.abs(target)))
        if bool(good.all()):matched+=1
        else:mismatched+=1
        if bool((calc==target).all()):exact+=1
    return {'offset':offset,'total_five_minute_rows':int(len(five)),'compared_bars':compared,'matched_bars':matched,
            'mismatched_bars':mismatched,'exact_equal_bars':exact,'max_abs_error':max_abs,'max_rel_error':max_rel,
            'unsupported_or_other':dict(sorted(categories.items()))}


def full_days(frame:pd.DataFrame,name:str)->set[str]:
    _,clocks=expected(name)
    return {day for day,part in frame.groupby('audit_day') if day not in EXCLUDED and set(part['audit_clock'])==clocks}


def verify_common(frames:dict[str,pd.DataFrame])->dict:
    common=set.intersection(*(full_days(frames[name],name) for name in FILES))
    one=frames['1m_official.parquet']
    eligible={day for day,part in one.groupby('audit_day') if day not in EXCLUDED and bool(part['high_frequency_analysis_eligible'].all())}
    common &= eligible
    minute=one['audit_minute']
    mask=one['audit_day'].isin(common)&(((minute>=574)&(minute<=686))|((minute>=784)&(minute<=896)))
    part=one.loc[mask];filled=int(part['causal_flat_fill'].sum())
    return {'common_complete_eligible_days':len(common),'contract_common_minutes':len(common)*226,
            'exported_common_minute_rows':int(len(part)),'observed_unfilled_common_minutes':int(len(part)-filled),
            'causal_fill_common_minutes':filled,'common_minute_windows':['09:34-11:26','13:04-14:56']}


def json_file(path:Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>8*1024*1024:raise ValueError('result_file')
    return json.loads(path.read_text(),parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))


def main():
    protocol=json_file(PROTOCOL)
    if protocol.get('schema_id')!='csi1000.segmentation_carrier_qualification_protocol@1.0':raise ValueError('protocol')
    if protocol['comparison']!={
        'abs_tolerance':1e-10,'rel_tolerance':1e-12,'components':['open','high','low','close'],
        'causal_flat_fill_bucket':'UNSUPPORTED_NOT_MISMATCH','ineligible_day':'UNSUPPORTED_NOT_MISMATCH',
        'offset0_first_session_buckets':'SOURCE_MINUTE_NOT_EXPORTED','align_by_row_index':False,
        'all_product_denominators_reported':True,'common_physical_support_reported':True}:raise ValueError('comparison_contract')
    frames={name:read_frame(INPUTS/name,name,protocol['files'][name]) for name in FILES}
    report=json_file(RESULTS/'report.json');manifest=json_file(RESULTS/'manifest.json')
    raw=(RESULTS/'report.json').read_bytes()
    meta=manifest.get('files',{}).get('report.json',{})
    if meta!={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}:raise ValueError('manifest_report')
    independent={str(offset):verify_reconstruction(frames['1m_official.parquet'],frames[f'5m_offset_{offset}.parquet'],offset)
                 for offset in range(5)}
    common=verify_common(frames)
    if report.get('reconstruction')!=independent:raise ValueError('reconstruction_mismatch')
    if report.get('common_support')!=common:raise ValueError('common_support_mismatch')
    if report.get('aliasing_conclusion')!='NOT_AUTHORIZED' or report.get('scale_dominance_conclusion')!='NOT_AUTHORIZED':
        raise ValueError('scope_promotion')
    if report.get('R4_selected') is not False or report.get('one_minute_strategy_admitted') is not False:
        raise ValueError('scope_promotion')
    any_mismatch=any(row['mismatched_bars'] for row in independent.values())
    enough=common['common_complete_eligible_days']>0 and all(row['compared_bars']>0 for row in independent.values())
    expected_status='CONSTRUCTION_MISMATCH' if any_mismatch else ('QUALIFIED_WITH_EXPECTED_UNSUPPORTED_BUCKETS' if enough else 'SCHEMA_OR_CLOCK_FAILED')
    if report.get('status')!=expected_status:raise ValueError('status_mismatch')
    result={'status':'passed','independent_status':expected_status,'files_verified':len(frames),
            'compared_bars':sum(row['compared_bars'] for row in independent.values()),
            'mismatched_bars':sum(row['mismatched_bars'] for row in independent.values()),
            'common_complete_eligible_days':common['common_complete_eligible_days'],
            'new_training':False,'production_authority':False}
    print(json.dumps(result,sort_keys=True,separators=(',',':')))


if __name__=='__main__':main()
