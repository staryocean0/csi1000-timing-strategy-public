"""Private full-OHLC audit, deterministic selection; never a live-state feed."""
import hashlib,html,json,math
from pathlib import Path
import numpy as np
from wave_recognizer_r1_v1 import _coverage,_runs,_episodes
from wave_multiscale_dual_gates_v2 import amp


def plan(bars,candidate,base):
    n=len(bars);old=_runs(~_coverage(base['waves'],n));ref=np.array([amp(w) for w in base['waves']])
    misses=_episodes(bars,_coverage(candidate['waves'],n),ref);cases=[]
    h=lambda s,e:hashlib.sha256(f'{s}:{e}'.encode()).hexdigest()[:16]
    old=[(s,e) for s,e in old if s>0 and e<n-1]
    for s,e in sorted(old,key=lambda q:h(*q))[:12]:cases.append(dict(id=h(s,e),kind='FORMER_BLIND_ZONE',start=s,end=e))
    for q in ('Q1','Q2','Q3','Q4'):
        group=sorted([r for r in misses if not r['edge'] and r['amplitude_quartile']==q],key=lambda r:h(r['start'],r['end']))
        for r in (group if q in ('Q3','Q4') else group[:6]):cases.append(dict(id=h(r['start'],r['end']),kind='RESIDUAL_'+q,start=r['start'],end=r['end']))
    for r in misses:
        if r['edge']:cases.append(dict(id=h(r['start'],r['end']),kind='DATA_EDGE',start=r['start'],end=r['end']))
    if candidate['waves']:
        w=max(candidate['waves'],key=lambda w:(w['duration'],-w['start_bar']))
        cases.append(dict(id=h(w['start_bar'],w['end_bar']),kind='LONGEST_WAVE_CONTROL',start=w['start_bar'],end=w['end_bar']))
    panels=[]
    for case in cases:
        s,e=case['start'],case['end'];over=[w for w in candidate['waves'] if w['start_bar']<=e and w['end_bar']>=s]
        left=max(0,min([s-12]+[w['start_bar'] for w in over]));cutoff=min(n-1,max([e+12]+[w['known_from_bar'] for w in over]))
        for page,start in enumerate(range(left,cutoff+1,240)):
            end=min(start+239,cutoff)
            panels.append(dict(case,id=case['id']+'-'+str(page),first=start,last=end,cutoff=cutoff,page=page))
    return panels


def render(bars,candidate,base,panel):
    first,last,cutoff=panel['first'],panel['last'],panel['cutoff'];n=last-first+1
    lo=math.log(float(bars.low.iloc[first:last+1].min()));hi=math.log(float(bars.high.iloc[first:last+1].max()));pad=max((hi-lo)*.08,1e-6);lo-=pad;hi+=pad
    x=lambda i:85+(i-first)*1080/max(1,n-1);y=lambda v:625-(math.log(v)-lo)/(hi-lo)*475
    esc=lambda v:html.escape(str(v),quote=True);width=min(8.,.65*1080/max(1,n-1))
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="830" viewBox="0 0 1280 830">','<rect width="1280" height="830" fill="white"/>',
         f'<metadata first="{first}" last="{last}" cutoff="{cutoff}" candles="{n}"/>',
         f'<text x="55" y="30" font-size="21">R1 {esc(panel["kind"])} | {esc(panel["id"])}</text>',
         '<text x="55" y="58" font-size="14">Historical audit: gray dashed = frozen baseline; black solid = R1 L-H-L; vertical dotted = R1 confirmation.</text>',
         '<text x="55" y="82" font-size="14">All OHLC candles shown. Hollow = close >= open. Occurrence geometry is NOT backfilled live knowledge.</text>',
         f'<text x="55" y="106" font-size="14">Shaded area = audit interval. Snapshot cutoff: {esc(bars.timestamp.iloc[cutoff])}. Page {panel["page"]+1}.</text>']
    a=max(first,panel['start']);b=min(last,panel['end'])
    if a<=b:out.append(f'<rect x="{x(a)-width:.3f}" y="150" width="{max(width*2,x(b)-x(a)+width*2):.3f}" height="475" fill="#eeeeee"/>')
    for i in range(first,last+1):
        v=bars.iloc[i];oo,hh,ll,cc=map(float,(v.open,v.high,v.low,v.close));top=min(y(oo),y(cc));height=max(.6,abs(y(oo)-y(cc)))
        out.append(f'<g class="candle" data-bar-index="{i}"><line x1="{x(i):.3f}" x2="{x(i):.3f}" y1="{y(hh):.3f}" y2="{y(ll):.3f}" stroke="black"/><rect x="{x(i)-width/2:.3f}" y="{top:.3f}" width="{width:.3f}" height="{height:.3f}" fill="{"white" if cc>=oo else "black"}" stroke="black"/></g>')
    for label,inv,stroke,dash in [('baseline',base,'#777','6,3'),('R1',candidate,'black','')]:
        for w in inv['waves']:
            if w['known_from_bar']>cutoff or w['end_bar']<first or w['start_bar']>last:continue
            points=[(w['start_bar'],w['start_low']),(w['high_bar'],w['high']),(w['end_bar'],w['end_low'])]
            for (i,a),(j,b) in zip(points,points[1:]):
                l=max(first,i);r=min(last,j)
                if l>r:continue
                interp=lambda t:math.exp(math.log(a)+(t-i)/(j-i)*math.log(b/a))
                out.append(f'<line class="{label}-segment" x1="{x(l):.3f}" x2="{x(r):.3f}" y1="{y(interp(l)):.3f}" y2="{y(interp(r)):.3f}" stroke="{stroke}" stroke-width="2" stroke-dasharray="{dash}"/>')
            if label=='R1':
                for (i,p),name in zip(points,['L','H','L']):
                    if first<=i<=last:out.append(f'<circle cx="{x(i):.3f}" cy="{y(p):.3f}" r="4" fill="white" stroke="black"/><text x="{x(i)+5:.3f}" y="{y(p)-6:.3f}" font-size="12">{name}</text>')
                c=w['known_from_bar']
                if first<=c<=last:out.append(f'<line class="confirmation" x1="{x(c):.3f}" x2="{x(c):.3f}" y1="150" y2="625" stroke="black" stroke-dasharray="2,6" opacity="0.45"/>')
    for i in sorted(set(first+round((n-1)*j/4) for j in range(5))):out.append(f'<text x="{x(i):.3f}" y="660" text-anchor="middle" font-size="12">{esc(bars.timestamp.iloc[i])}</text>')
    for j in range(5):
        price=math.exp(lo+(hi-lo)*j/4);out.append(f'<text x="5" y="{y(price):.3f}" font-size="12">{price:.2f}</text>')
    out.extend(['<text x="55" y="708" font-size="14">Pivots: CLOSE-selected occurrence; geometry: wick LOW/HIGH on those bars. No invented O/H/L/C.</text>',
                '<text x="55" y="733" font-size="14">Review both recovery and under-segmentation. Long one-way legs are not forced into artificial cycles.</text>',
                '<text x="55" y="758" font-size="14">This image is evidence for manual review, not automatic recognition acceptance or a trading signal.</text>','</svg>'])
    return '\n'.join(out)+'\n'


def write_pack(directory,bars,candidate,base):
    directory=Path(directory);directory.mkdir();panels=plan(bars,candidate,base);entries=[]
    if len(panels)>1000:raise ValueError('visual pack exceeds reviewed 1000-page bound')
    for p in panels:
        name='case-'+p['id']+'.svg';raw=render(bars,candidate,base,p).encode();(directory/name).write_bytes(raw)
        entries.append(dict(p,file=name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
    index=dict(schema_id='csi1000.recognizer_R1_visuals@1.0',mode='historical_geometry_with_asof_cutoff',manual_acceptance=False,panels=entries)
    (directory/'index.json').write_text(json.dumps(index,sort_keys=True)+'\n')
    return index
