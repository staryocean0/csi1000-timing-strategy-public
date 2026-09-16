"""#334 diagnostic only: unchanged R1, all five gaps and old/new blind accounting.
Raw prices, bar indices and event traces remain inside private results.
"""
from __future__ import annotations
import argparse, base64, gzip, hashlib, json
from collections import Counter
from pathlib import Path
from wave_recognizer_r1_residual_probe_v1 import episode_partition, reference_scope, verified_frozen_replay

R1_BLOB='32ffb3db77a7861f88ba6332809072d00b3a78a6'
DATA_SHA='bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48'

def assert_source_identity():
    p=Path(__file__).with_name('wave_recognizer_r1_v1.py')
    if p.is_symlink() or not p.is_file():raise ValueError('frozen R1 missing')
    raw=p.read_bytes().replace(b'\r\n',b'\n')
    if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=R1_BLOB:raise ValueError('R1 source changed')

def diagnose(bars):
    from wave_recognizer_r1_v1 import analyze, _coverage, _episodes, _runs
    from wave_multiscale_dual_gates_v2 import amp
    assert_source_identity()
    old_report,candidate,baseline=analyze(bars)
    ledger=verified_frozen_replay(bars);n=len(bars)
    original=_coverage(baseline['waves'],n);current=_coverage(candidate['waves'],n)
    ref=[amp(w) for w in baseline['waves']]
    gaps=[e for e in _episodes(bars,current,ref) if not e['edge']]
    evidence={r['reset_bar']:r for r in ledger['reset_evidence']}
    cases=[];details=[];selected=set()
    for gap in gaps:
        s,e=gap['start'],gap['end']
        identity=hashlib.sha256(f"{s}:{e}:{gap['amplitude_quartile']}".encode()).hexdigest()[:16]
        resets=[r for r in candidate['resets'] if s<=r['bar_index']<=e]
        new=int(original[s:e+1].sum())
        row=dict(id=identity,bars=e-s+1,amplitude_quartile=gap['amplitude_quartile'],
                 raw_log_range=gap['raw_log_range'],newly_blind_bars=new,old_blind_bars=e-s+1-new,
                 resets_inside=len(resets),mechanisms=[],newly_blind_segments=[])
        private=dict(id=identity,start=s,end=e,resets=[],baseline_waves=[],R1_neighbor_waves=[])
        for a,b in _runs(original[s:e+1]):
            row['newly_blind_segments'].append(dict(start_offset=a,end_offset=b,bars=b-a+1))
        for reset in resets:
            t=reset['bar_index'];state=ledger['rows'][t]['before'];ev=evidence[t]
            public={k:v for k,v in ev.items() if k!='reset_bar'}
            ps=[p for p in candidate['pivots'] if p['epoch']==reset['epoch']+1 and p['confirmation_bar']>=t]
            seeds=[p for p in ps if p['left_censored']];proper=[p for p in ps if not p['left_censored']]
            following=[w for w in candidate['waves'] if w['start_bar']>e]
            first_wave=following[0] if following else None
            public.update(first_bootstrap_confirmation_delay=None if not seeds else seeds[0]['confirmation_bar']-t,
                          bootstrap_seed_occurrence_offset=None if not seeds else seeds[0]['occurrence_bar']-t,
                          first_noncensored_confirmation_delay=None if not proper else proper[0]['confirmation_bar']-t,
                          next_complete_wave_start_offset=None if first_wave is None else first_wave['start_bar']-t,
                          next_complete_wave_confirmation_delay=None if first_wave is None else first_wave['known_from_bar']-t)
            if len(resets)==1:
                public['gap_partition']=episode_partition(s,e,t,original)
                public['new_blind_partition']=dict(before_reset=int(original[s:t].sum()),reset=int(original[t]),after_reset=int(original[t+1:e+1].sum()))
            start=state['candidate'] if state['candidate'] is not None else t
            public['actions_since_candidate']=dict(Counter(r['action'] for r in ledger['rows'][start+1:t]))
            public['previous_pivot_age']=None if state['last_pivot'] is None else t-state['last_pivot']
            public['previous_pivot_confirmation_age']=None if state['last_confirmation'] is None else t-state['last_confirmation']
            counter=state['counter']
            public['counter_frozen_bars']=None if counter is None else t-counter
            public['prolonged_short_counter_span']=bool(counter is not None and 0<counter-start<4 and t-counter>=4)
            public['candidate_to_reset_close_log_range']=float(__import__('math').log(float(bars.close.iloc[start:t+1].max())/float(bars.close.iloc[start:t+1].min())))
            row['mechanisms'].append(public)
            private['resets'].append(dict(public,reset_bar=t,before=state,after=ledger['rows'][t]['after']))
            support_start=max(0,min(x for x in (s-64,state['candidate'],state['counter'],state['last_pivot']) if x is not None))
            support_end=min(n-1,max(e+64,first_wave['known_from_bar'] if first_wave else e))
            selected.update(range(support_start,support_end+1))
        if not resets:
            row['mechanisms'].append(dict(reason='NO_RESET_INSIDE_GAP'))
            selected.update(range(max(0,s-64),min(n,e+65)))
        private['baseline_waves']=[w for w in baseline['waves'] if w['start_bar']<=e and w['end_bar']>=s]
        private['R1_neighbor_waves']=[w for w in candidate['waves'] if w['start_bar']<=e+128 and w['end_bar']>=s-128]
        cases.append(row);details.append(private)
    total=sum(c['bars'] for c in cases);new=sum(c['newly_blind_bars'] for c in cases);old=sum(c['old_blind_bars'] for c in cases)
    if total!=old_report['counts']['nonedge_blind_bars'] or old+new!=total:raise ValueError('gap accounting')
    report=dict(schema_id='csi1000.r1_residual_event_clock_audit@1.0',status='DIAGNOSTIC_NOT_REPAIR_ACCEPTANCE',
                source_R1_blob=R1_BLOB,data_sha256=DATA_SHA,scope=reference_scope(),frozen_R1_unchanged=True,
                counts=dict(bars=n,R1_waves=len(candidate['waves']),R1_resets=len(candidate['resets']),residual_episodes=len(cases),
                            residual_bars=total,old_blind_bars_remaining=old,new_blind_bars=new),
                cases=cases,mechanism_counts=dict(Counter(m['reason'] for c in cases for m in c['mechanisms'])),
                full_OHLC_manual_acceptance=False,
                interpretation='EARLY_COUNTER_LOCK names the observed invariant plus duration, not a proven general root cause. Same-bar predicates do not simulate R2.')
    trace=[dict(ledger['rows'][t],timestamp=str(bars.timestamp.iloc[t]),OHLC={k:float(bars[k].iloc[t]) for k in ('open','high','low','close')}) for t in sorted(selected)]
    private=dict(cases=details,event_trace=trace,R1_pivots=ledger['pivots'],R1_resets=ledger['resets'])
    return report,private,candidate,baseline

def write_outputs(bars,out):
    from wave_recognizer_r1_v1_entry import encode
    from wave_recognizer_r1_v1_visuals import write_pack
    report,private,candidate,baseline=diagnose(bars)
    out=Path(out)
    if out.exists():raise ValueError('fresh output required')
    out.mkdir(parents=True)
    for name,value in (('report.json',report),('private_event_trace.json',private)):(out/name).write_bytes(encode(value))
    index=write_pack(out/'visuals',bars,candidate,baseline)
    # Standard lossless compressed transport of existing SVG evidence, not new charts.
    readback=[]
    for p in index['panels']:
        raw=(out/'visuals'/p['file']).read_bytes()
        readback.append(json.dumps(dict(file=p['file'],sha256=p['sha256'],bytes=p['bytes'],gzip_base64=base64.b64encode(gzip.compress(raw,mtime=0)).decode()),sort_keys=True))
    (out/'visual_readback.jsonl').write_text('\n'.join(readback)+'\n',encoding='utf-8')
    files={}
    for p in sorted(out.rglob('*')):
        if p.is_file():
            raw=p.read_bytes();files[p.relative_to(out).as_posix()]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    (out/'manifest.json').write_bytes(encode(dict(files=files,new_training=False,production_authority=False,raw_trace_destination='PRIVATE_ARCHIVE_ONLY',manual_visual_acceptance=False)))

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    if a.inputs!='/work/inputs' or a.out!='/results/study':raise ValueError('fixed isolated paths only')
    from wave_recognizer_r1_v1_entry import load_market
    write_outputs(load_market(a.inputs),Path(a.out))

if __name__=='__main__':main()
