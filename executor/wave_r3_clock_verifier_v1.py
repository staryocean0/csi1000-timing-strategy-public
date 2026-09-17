"""Independent file-level #345 verification; saved observations are not trusted."""
from collections import Counter
import hashlib
import sys
from pathlib import Path
import numpy as np
from wave_recognizer_r3_v1 import analyze
from wave_recognizer_r3_v1_entry import encode, load_market
from wave_recognizer_r3_v1_verifier import independent_waves
from wave_recognizer_r3_v1_visuals import plan, render
from wave_r3_clock_probe_v1 import replay, pivot_key, observe_frozen
from wave_r3_clock_audit_v1 import summarize
from wave_r3_clock_checks_v1 import independent_coverage, check_subset_counts, check_trace
from wave_r3_clock_files_v1 import verify_manifest, read_json, read_bytes, read_trace, no_links
from wave_r3_clock_entry_v1 import enforce_parent

INPUT = Path('/work/inputs')
OUTPUT = Path('/results/study')

def independent_reset_label(row, prices):
    state = row['pre']
    t = row['bar_index']
    k,c,m = state['candidate'],state['pending_counter'],state['mode']
    anchors = [x for x in (k,state['last_pivot']) if x is not None]
    if not anchors or t-max(anchors)!=49:
        raise ValueError('reset is not at frozen progress boundary')
    if k is None or m is None:
        return 'TIMEOUT_WITH_NO_ACTIVE_CANDIDATE'
    current = prices[t]
    improves = current>prices[k] if m==1 else current<prices[k]
    if improves:
        return 'RESET_PREEMPTS_SAME_BAR_CANDIDATE_PROGRESS'
    opposite = current<prices[k] if m==1 else current>prices[k]
    replaces = opposite and (c is None or (current<prices[c] if m==1 else current>prices[c]))
    if replaces:
        return 'TIMEOUT_WITH_COUNTER_SUPERSESSION_ON_RESET_BAR'
    if c is None:
        return 'TIMEOUT_WITH_NO_PENDING_COUNTER'
    if t-c<4:
        return 'TIMEOUT_WITH_COUNTER_NOT_YET_MATURE'
    return 'RESET_PREEMPTS_ELIGIBLE_COUNTER_MATURITY' if c-k>=4 else 'RESET_PREEMPTS_SUBSCALE_REJECTION'

def independent_case_checks(bars, summary, candidate, events, rows):
    n = len(bars)
    mask = independent_coverage(candidate['waves'],n)
    edges = np.diff(np.r_[False,~mask,False].astype(int))
    spans = [(int(a),int(b)-1) for a,b in zip(np.where(edges==1)[0],np.where(edges==-1)[0]) if a>0 and b<n]
    actual = summary['residual_cases']
    if [c['bars'] for c in actual]!=[b-a+1 for a,b in spans]:
        raise ValueError('independent residual length mismatch')
    prices = bars.close.to_numpy(float)
    labels = []
    for c,(a,b) in zip(actual,spans):
        identity = hashlib.sha256(f"{a}:{b}:{c['amplitude_quartile']}".encode()).hexdigest()[:16]
        if c['case_id']!=identity:
            raise ValueError('independent residual identity mismatch')
        resets = [r['bar_index'] for r in events['resets'] if a<=r['bar_index']<=b]
        if c['reset_count']!=len(resets) or len(c['reset_evidence'])!=len(resets):
            raise ValueError('reset omission in residual')
        if resets:
            expected = dict(before_first_reset_bars=min(resets)-a, reset_bars=len(resets),
                            after_first_reset_nonreset_bars=b-min(resets)+1-len(resets))
            if c['gap_phase_accounting']!=expected:
                raise ValueError('independent gap phase mismatch')
        for t,detail in zip(resets,c['reset_evidence']):
            label = independent_reset_label(rows[t],prices)
            if detail['reset_bar_predicates']['classification']!=label:
                raise ValueError('independent reset classification mismatch')
            labels.append(label)
    all_labels = Counter(independent_reset_label(rows[r['bar_index']],prices) for r in events['resets'])
    if dict(sorted(all_labels.items()))!=summary['reset_classification_counts']:
        raise ValueError('independent reset count mismatch')
    return dict(nonedge_cases=len(spans),nonedge_bars=sum(b-a+1 for a,b in spans),reset_labels=dict(all_labels))

def independent_latency(candidate, events, saved, summary):
    if len(saved)!=len(candidate['waves']):
        raise ValueError('latency row count mismatch')
    table={(x['epoch'],x['candidate_occurrence_bar'],x['maturity_bar']):x for x in events['maturities']}
    joint = Counter()
    for w,row in zip(candidate['waves'],saved):
        end,known = w['end_bar'],w['known_from_bar']
        event = table[(w['epoch'],end,known)]
        middle = event['counter_occurrence_bar']
        expected = dict(wave_id=w['wave_id'],epoch=w['epoch'],final_low_occurrence=end,
            counter_occurrence=middle,known_from_bar=known,occurrence_separation=middle-end,
            counter_survival=known-middle,confirmation_delay=known-end)
        if row!=expected or middle-end<4 or known-middle!=4:
            raise ValueError('independent final-low latency mismatch')
        joint[(middle-end,known-middle,known-end)]+=1
    expected_joint=[dict(occurrence_separation=g,counter_survival=s,confirmation_delay=d,count=c)
                    for (g,s,d),c in sorted(joint.items())]
    if summary['final_low_latency']['joint_frequency']!=expected_joint:
        raise ValueError('independent joint distribution mismatch')
    return len(saved)

def verify_bundle(bars, output, *, formal):
    root = Path(output)
    verify_manifest(root)
    rows = read_trace(root)
    events = read_json(root,'events.json')
    expected = replay(bars.close.to_numpy(float))
    if set(events)!={'pivots','resets','rejections','maturities'} or rows!=expected['rows']:
        raise ValueError('independent saved trace mismatch')
    for key in events:
        if events[key]!=expected[key]:
            raise ValueError('independent saved event mismatch: '+key)
    del expected
    parent,candidate,base,r1,r2 = analyze(bars)
    wave_keys = independent_waves(bars,[tuple(pivot_key(x)) for x in events['pivots']])
    observed_keys = [(w['epoch'],w['start_bar'],w['high_bar'],w['end_bar'],w['known_from_bar'],
                      w['start_low'],w['high'],w['end_low']) for w in candidate['waves']]
    if wave_keys!=observed_keys:
        raise ValueError('independent wick wave mismatch')
    parent_expected = dict(parent,data_role='PREVIOUSLY_CONSUMED_DEVELOPMENT_NOT_FRESH_OOS',
        source_data_sha256='bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48')
    raw = read_bytes(root,'parent/report.json')
    if raw!=encode(parent_expected):
        raise ValueError('parent report reproduction mismatch')
    pm=read_json(root,'parent/manifest.json')
    if pm!={'files':{'report.json':{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}},
            'new_training':False,'production_authority':False}:
        raise ValueError('parent manifest mismatch')
    summary = read_json(root,'report.json')
    # Same-source summary reproduction is NOT the independent state-machine check.
    rebuilt = summarize(bars,parent,candidate,base,r1,r2,rows)
    if read_bytes(root,'report.json')!=encode(rebuilt):
        raise ValueError('summary reproduction mismatch')
    subset = check_subset_counts(summary,base,r1,candidate,len(bars))
    case_checks = independent_case_checks(bars,summary,candidate,events,rows)
    latency_count = independent_latency(candidate,events,read_json(root,'latency.json'),summary)
    index = read_json(root,'visuals/index.json')
    planned = plan(bars,candidate,base,r2)
    if len(index['panels'])!=len(planned) or index['manual_acceptance'] is not False:
        raise ValueError('visual index mismatch')
    allowed_visuals = {'index.json'}
    for panel,item in zip(planned,index['panels']):
        raw = render(bars,candidate,base,panel).encode()
        expected_item=dict(panel,file='case-'+panel['id']+'.svg',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if item!=expected_item or read_bytes(root,'visuals/'+item['file'])!=raw:
            raise ValueError('parent visual mismatch')
        allowed_visuals.add(item['file'])
    if {p.name for p in (root/'visuals').iterdir()}!=allowed_visuals:
        raise ValueError('visual file-set mismatch')
    if formal:
        enforce_parent(root,summary)
    cuts = set(int(x) for x in np.linspace(0,len(bars)-1,min(8,len(bars))))
    cuts.update(t for r in events['resets'] for t in (r['bar_index']-1,r['bar_index']) if t>=0)
    for t in sorted(cuts):
        observed,short = observe_frozen(bars.iloc[:t+1].copy())
        check_trace(bars.iloc[:t+1],observed,short)
        if short!=rows[:t+1]:
            raise ValueError('frozen prefix state mismatch')
        for key,field,values in [('pivots','confirmation_bar',observed[1]),('resets','bar_index',observed[2]),
                                 ('rejections','maturity_bar',observed[3]),('maturities','maturity_bar',observed[4])]:
            if values!=[x for x in events[key] if x[field]<=t]:
                raise ValueError('frozen prefix event mismatch')
    return dict(status='passed',trace_rows=len(rows),latency_rows=latency_count,
        independent_cases=case_checks,independent_subset=subset,prefix_cutoffs_checked=len(cuts),
        parent_evidence_identity_preserved=bool(formal),visual_pages=len(planned),
        causality_passed=True,visual_manual_acceptance=False,R3_readiness_passed=False,
        R4_selected=False,production_authority=False)

def main():
    if sys.argv[1:]:
        raise ValueError('verifier accepts no arguments')
    no_links(INPUT/'5m_offset_0.parquet')
    result=verify_bundle(load_market(INPUT),OUTPUT,formal=True)
    print(encode(result).decode(),end='')

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print('R3_CLOCK_VERIFY_STOPPED:'+type(exc).__name__,file=sys.stderr)
        raise SystemExit(1)
