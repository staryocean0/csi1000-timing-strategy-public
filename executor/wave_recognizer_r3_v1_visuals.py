"""R3 full-OHLC evidence with former-R1 and R2 floor-leg controls.

Selection is deterministic and private. Rendering inherits the frozen R1 OHLC
geometry but every candidate label is explicitly R3, including confirmation.
No automatic manual acceptance and no live-state feed.
"""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from wave_recognizer_r1_v1_visuals import plan as _base_plan, render as _r1_render
from wave_recognizer_r2_v1_visuals import _r1_residual_cases
from two_wave_v0800_scale_map import MIN_LEG


def _token(prefix,s,e,extra=''):
    return hashlib.sha256(f'{prefix}:{s}:{e}:{extra}'.encode()).hexdigest()[:16]


def _r2_floor_cases(r2):
    rows=[]
    for w in r2['waves']:
        if w['duration']!=MIN_LEG:continue
        rows.append(dict(id=_token('R2FLOOR',w['start_bar'],w['end_bar'],w['wave_id']),kind='R2_MIN_LEG_DURATION_CONTROL',start=w['start_bar'],end=w['end_bar'],wave_id=w['wave_id']))
    return sorted(rows,key=lambda r:r['id'])[:8]


def _add_case(panels,bars,candidate,case):
    n=len(bars);s,e=case['start'],case['end'];over=[w for w in candidate['waves'] if w['start_bar']<=e and w['end_bar']>=s]
    left=max(0,min([s-12]+[w['start_bar'] for w in over]));cutoff=min(n-1,max([e+12]+[w['known_from_bar'] for w in over]))
    for page,start in enumerate(range(left,cutoff+1,240)):
        end=min(start+239,cutoff)
        panels.append(dict(case,id=case['id']+'-'+str(page),first=start,last=end,cutoff=cutoff,page=page))


def plan(bars,candidate,base,r2):
    panels=list(_base_plan(bars,candidate,base))
    for case in _r1_residual_cases(bars,base):_add_case(panels,bars,candidate,case)
    for case in _r2_floor_cases(r2):_add_case(panels,bars,candidate,case)
    return panels


def render(bars,candidate,base,panel):
    svg=_r1_render(bars,candidate,base,panel)
    replacements=(
        ('R1-segment','R3-segment'),
        ('>R1 ','>R3 '),
        ('black solid = R1 L-H-L','black solid = R3 L-H-L'),
        ('vertical dotted = R1 confirmation','vertical dotted = R3 confirmation'),
    )
    for old,new in replacements:svg=svg.replace(old,new)
    if 'vertical dotted = R1 confirmation' in svg or 'black solid = R1 L-H-L' in svg:raise AssertionError('stale candidate legend')
    return svg


def write_pack(directory,bars,candidate,base,r2):
    directory=Path(directory);directory.mkdir();panels=plan(bars,candidate,base,r2);entries=[]
    if len(panels)>1000:raise ValueError('visual pack exceeds reviewed 1000-page bound')
    for p in panels:
        name='case-'+p['id']+'.svg';raw=render(bars,candidate,base,p).encode();(directory/name).write_bytes(raw)
        entries.append(dict(p,file=name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
    index=dict(schema_id='csi1000.recognizer_R3_visuals@1.0',mode='historical_geometry_with_asof_cutoff',manual_acceptance=False,panels=entries,
               mandatory_former_R1_residual_pages=sum(p['kind']=='FORMER_R1_RESIDUAL' for p in panels),
               r2_min_leg_control_pages=sum(p['kind']=='R2_MIN_LEG_DURATION_CONTROL' for p in panels))
    (directory/'index.json').write_text(json.dumps(index,sort_keys=True)+'\n')
    return index
