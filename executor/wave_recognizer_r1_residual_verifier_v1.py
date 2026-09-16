"""Read-only #334 verification: unchanged R1 observer, independent masks and clocks.
No alternate detector and no same-source replay presented as independent science.
"""
from __future__ import annotations
import argparse, base64, gzip, hashlib, json, math
from pathlib import Path
import numpy as np
import xml.etree.ElementTree as ET
from wave_recognizer_r1_v1 import ProgressAwareAEngine
from wave_recognizer_r1_v1_entry import encode, load_market
from wave_recognizer_r1_residual_audit_v1 import diagnose, assert_source_identity
from wave_recognizer_r1_residual_probe_v1 import replay


class ObservedFrozenR1(ProgressAwareAEngine):
    """Do not override run or any price transition. Observe the actual reset call."""
    def __init__(self,bars):
        super().__init__(bars);self.observations=[]
    def reset(self,i):
        before=dict(mode=self.mode,candidate=None if self.candidate is None else self.candidate[0],
                    counter=None if self.counter is None else self.counter[0],last_pivot=self.last_pivot_bar,
                    epoch=self.epoch,last_confirmation=self.pivots[-1]['confirmation_bar'] if self.pivots else None)
        super().reset(i)
        self.observations.append(dict(bar=i,before=before))


def independent_checks(bars,report,private):
    engine=ObservedFrozenR1(bars);records,pivots,resets=engine.run();prices=bars.close.to_numpy(float)
    if pivots!=private['R1_pivots'] or resets!=private['R1_resets']:raise ValueError('frozen observer ledger mismatch')
    from two_wave_v0800_scale_map import TemporalMaturityAEngine
    old,_,_=TemporalMaturityAEngine(bars).run();n=len(bars)
    def mask(rs):
        d=np.zeros(n+1,dtype=int)
        for r in rs:d[r.wave.start_bar]+=1;d[r.wave.end_bar+1]-=1
        return np.cumsum(d[:-1])>0
    covered,baseline=mask(records),mask(old)
    boundaries=np.diff(np.r_[False,~covered,False].astype(int))
    gaps=[(int(a),int(b-1)) for a,b in zip(np.flatnonzero(boundaries==1),np.flatnonzero(boundaries==-1)) if a>0 and b<n]
    if len(gaps)!=len(report['cases']) or len(gaps)!=len(private['cases']):raise ValueError('omitted residual case')
    public_by_id={c['id']:c for c in report['cases']};trace={r['bar']:r for r in private['event_trace']}
    if len(trace)!=len(private['event_trace']):raise ValueError('duplicate trace row')
    observations={r['bar']:r for r in engine.observations};found=0;old_total=new_total=0
    for (s,e),detail in zip(gaps,private['cases']):
        if (detail['start'],detail['end'])!=(s,e):raise ValueError('case boundary mismatch')
        row=public_by_id[detail['id']];new=int(baseline[s:e+1].sum());length=e-s+1
        if (row['bars'],row['newly_blind_bars'],row['old_blind_bars'])!=(length,new,length-new):raise ValueError('new/old accounting mismatch')
        offsets=[k for part in row['newly_blind_segments'] for k in range(part['start_offset'],part['end_offset']+1)]
        if offsets!=list(np.flatnonzero(baseline[s:e+1])):raise ValueError('new blind boundaries mismatch')
        old_total+=length-new;new_total+=new
        expected_resets=[r for r in resets if s<=r['bar_index']<=e]
        if len(expected_resets)!=row['resets_inside'] or len(expected_resets)!=len(detail['resets']):raise ValueError('reset coverage mismatch')
        for r,ev,pub in zip(expected_resets,detail['resets'],row['mechanisms']):
            t=r['bar_index'];before=observations[t]['before']
            if ev['reset_bar']!=t or ev['before']!=before or trace[t]['before']!=before:raise ValueError('true pre-reset snapshot mismatch')
            c,q,last=before['candidate'],before['counter'],before['last_pivot'];m=before['mode']
            anchor=max(x for x in (c,last) if x is not None);gap=None if q is None else q-c
            if t-anchor!=49 or pub['progress_age']!=49 or pub['counter_gap']!=gap:raise ValueError('timeout age/gap mismatch')
            delta=m*(prices[t]-prices[c]);newcandidate=delta>0
            cq=q
            if delta<0 and (cq is None or m*(prices[t]-prices[cq])<0):cq=t
            confirm=not newcandidate and cq is not None and cq-c>=4
            if (pub['skipped_new_candidate'],pub['skipped_valid_confirmation'])!=(bool(newcandidate),bool(confirm)):raise ValueError('same-bar evidence mismatch')
            reason='SAME_BAR_EVIDENCE_SKIPPED' if newcandidate or confirm else 'NO_OPPOSITE_COUNTER' if gap is None else 'EARLY_COUNTER_LOCK' if 0<gap<4 else 'INVALID'
            if pub['reason']!=reason:raise ValueError('mechanism predicate mismatch')
            if len(expected_resets)==1:
                part=pub['gap_partition'];npub=pub['new_blind_partition']
                if (part['before_reset_bars'],part['reset_bar'],part['after_reset_bars'])!=(t-s,1,e-t):raise ValueError('before/after clock mismatch')
                if (npub['before_reset'],npub['reset'],npub['after_reset'])!=(int(baseline[s:t].sum()),int(baseline[t]),int(baseline[t+1:e+1].sum())):raise ValueError('new blind phase mismatch')
            found+=1
        for t in range(s,e+1):
            if t not in trace:raise ValueError('missing residual candle trace')
    for t,row in trace.items():
        if row['timestamp']!=str(bars.timestamp.iloc[t]) or row['OHLC']!={k:float(bars[k].iloc[t]) for k in ('open','high','low','close')}:raise ValueError('raw candle trace mismatch')
    expected=dict(bars=n,R1_waves=len(records),R1_resets=len(resets),residual_episodes=len(gaps),residual_bars=old_total+new_total,old_blind_bars_remaining=old_total,new_blind_bars=new_total)
    if report['counts']!=expected:raise ValueError('aggregate population mismatch')
    full=replay(prices)
    if any(row[k]!=full['rows'][t][k] for t,row in trace.items() for k in full['rows'][t]):raise ValueError('trace reproduction mismatch')
    cuts=sorted(set(int(x) for x in np.linspace(0,n-1,min(8,n)))|{max(0,r['bar_index']-1) for r in resets}|{r['bar_index'] for r in resets})
    for t in cuts:
        part=replay(prices[:t+1])
        if part['rows']!=full['rows'][:t+1]:raise ValueError('future suffix alters observed event clock')
    return dict(reset_snapshots_checked=found,trace_rows_checked=len(trace),prefix_cutoffs_checked=len(cuts),independent_masks_and_branch_predicates=True)


def verify(bars,out,expected_market=False):
    assert_source_identity();out=Path(out)
    if out.is_symlink() or not out.is_dir():raise ValueError('invalid output directory')
    all_files={p.relative_to(out).as_posix():p for p in out.rglob('*') if p.is_file()}
    if any(p.is_symlink() for p in out.rglob('*')):raise ValueError('symlink in output')
    if 'manifest.json' not in all_files:raise ValueError('manifest missing')
    m=json.loads(all_files['manifest.json'].read_text())
    if set(m['files'])!=set(all_files)-{'manifest.json'}:raise ValueError('undeclared result file')
    if m['new_training'] is not False or m['production_authority'] is not False:raise ValueError('scope drift')
    for name,meta in m['files'].items():
        p=all_files[name]
        if p.stat().st_size>30_000_000:raise ValueError('result bound exceeded')
        raw=p.read_bytes()
        if meta!={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}:raise ValueError('result hash mismatch')
    report=json.loads(all_files['report.json'].read_text());private=json.loads(all_files['private_event_trace.json'].read_text())
    reproduced,priv,candidate,base=diagnose(bars)
    if encode(report)!=encode(reproduced) or encode(private)!=encode(priv):raise ValueError('diagnostic reproduction mismatch')
    independent=independent_checks(bars,report,private)
    if expected_market and report['counts']!=dict(bars=70114,R1_waves=2704,R1_resets=5,residual_episodes=5,residual_bars=414,old_blind_bars_remaining=322,new_blind_bars=92):raise ValueError('frozen R1 market identity mismatch')
    from wave_recognizer_r1_v1_visuals import plan,render
    index=json.loads(all_files['visuals/index.json'].read_text());panels=plan(bars,candidate,base)
    if len(panels)!=len(index['panels']) or index['manual_acceptance'] is not False:raise ValueError('visual plan drift')
    for p,entry in zip(panels,index['panels']):
        if any(entry[k]!=v for k,v in p.items()):raise ValueError('visual metadata drift')
        raw=all_files['visuals/'+entry['file']].read_bytes()
        if raw!=render(bars,candidate,base,p).encode():raise ValueError('not frozen R1 visual evidence')
        root=ET.fromstring(raw);ns={'s':'http://www.w3.org/2000/svg'}
        if [int(c.attrib['data-bar-index']) for c in root.findall("s:g[@class='candle']",ns)]!=list(range(p['first'],p['last']+1)):raise ValueError('candles omitted')
    transport=[json.loads(line) for line in all_files['visual_readback.jsonl'].read_text().splitlines()]
    if len(transport)!=len(panels):raise ValueError('readback omitted panels')
    for row,entry in zip(transport,index['panels']):
        if row['file']!=entry['file'] or row['bytes']>250_000:raise ValueError('readback identity/bounds')
        raw=gzip.decompress(base64.b64decode(row['gzip_base64'],validate=True))
        if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256'] or raw!=all_files['visuals/'+row['file']].read_bytes():raise ValueError('lossy visual readback')
    if any(report['scope']['authority'].values()) or report['scope']['R2_selected'] or report['scope']['one_minute_admitted']:raise ValueError('authority promotion')
    return dict(status='passed',independent=independent,visual_pages=len(panels),manual_visual_acceptance=False,R2_selected=False,new_training=False,production_authority=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--results',required=True);a=p.parse_args()
    if a.inputs!='/work/inputs' or a.results!='/results/study':raise ValueError('fixed isolated paths only')
    print(json.dumps(verify(load_market(a.inputs),a.results,expected_market=True),sort_keys=True))

if __name__=='__main__':main()
