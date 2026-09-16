"""R2 full-OHLC evidence with mandatory former-R1 residual review.

The frozen R1 visual geometry/rendering is reused. R2 additionally forces every
non-edge substantial R1 residual into the visual plan whether R2 recovers it or
not. This is evidence selection only; it does not change recognizer semantics.
"""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import numpy as np
from wave_recognizer_r1_v1_visuals import plan as _plan, render as _r1_render
from wave_recognizer_r1_v1 import candidate_inventory as r1_inventory, _coverage, _episodes
from wave_multiscale_dual_gates_v2 import amp


def _r1_residual_cases(bars,base):
    n=len(bars);r1=r1_inventory(bars);ref=np.asarray([amp(w) for w in base['waves']],float)
    misses=_episodes(bars,_coverage(r1['waves'],n),ref);cases=[]
    for r in misses:
        if r['edge'] or r['amplitude_quartile'] not in ('Q3','Q4'):continue
        token=hashlib.sha256(f"R1:{r['start']}:{r['end']}".encode()).hexdigest()[:16]
        cases.append(dict(id=token,kind='FORMER_R1_RESIDUAL',start=r['start'],end=r['end']))
    return sorted(cases,key=lambda r:(r['start'],r['end']))


def plan(bars,candidate,base):
    panels=list(_plan(bars,candidate,base));n=len(bars)
    for case in _r1_residual_cases(bars,base):
        s,e=case['start'],case['end'];over=[w for w in candidate['waves'] if w['start_bar']<=e and w['end_bar']>=s]
        left=max(0,min([s-12]+[w['start_bar'] for w in over]));cutoff=min(n-1,max([e+12]+[w['known_from_bar'] for w in over]))
        for page,start in enumerate(range(left,cutoff+1,240)):
            end=min(start+239,cutoff)
            panels.append(dict(case,id=case['id']+'-'+str(page),first=start,last=end,cutoff=cutoff,page=page))
    return panels


def render(bars,candidate,base,panel):
    svg=_r1_render(bars,candidate,base,panel)
    svg=svg.replace('R1-segment','R2-segment')
    svg=svg.replace('>R1 ','>R2 ')
    svg=svg.replace('black solid = R1 L-H-L','black solid = R2 L-H-L')
    return svg


def write_pack(directory,bars,candidate,base):
    directory=Path(directory);directory.mkdir();panels=plan(bars,candidate,base);entries=[]
    if len(panels)>1000:raise ValueError('visual pack exceeds reviewed 1000-page bound')
    for p in panels:
        name='case-'+p['id']+'.svg';raw=render(bars,candidate,base,p).encode();(directory/name).write_bytes(raw)
        entries.append(dict(p,file=name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
    index=dict(schema_id='csi1000.recognizer_R2_visuals@1.0',mode='historical_geometry_with_asof_cutoff',manual_acceptance=False,panels=entries,
               mandatory_former_R1_residual_pages=sum(p['kind']=='FORMER_R1_RESIDUAL' for p in panels))
    (directory/'index.json').write_text(json.dumps(index,sort_keys=True)+'\n')
    return index
