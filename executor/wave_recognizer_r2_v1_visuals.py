"""R2 full-OHLC evidence using the frozen R1 selection geometry.

Selection and rendering semantics are inherited exactly from the reviewed R1
visual implementation; only the human-readable candidate label/schema change.
This does not create a live state or an automatic visual acceptance.
"""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from wave_recognizer_r1_v1_visuals import plan as _plan, render as _r1_render


def plan(bars,candidate,base):
    return _plan(bars,candidate,base)


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
    index=dict(schema_id='csi1000.recognizer_R2_visuals@1.0',mode='historical_geometry_with_asof_cutoff',manual_acceptance=False,panels=entries)
    (directory/'index.json').write_text(json.dumps(index,sort_keys=True)+'\n')
    return index
