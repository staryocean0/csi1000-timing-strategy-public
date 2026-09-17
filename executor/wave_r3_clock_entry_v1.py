"""No-argument #345 entry. Only the frozen input and fresh result root are used."""
import hashlib
import sys
from pathlib import Path
from wave_recognizer_r3_v1 import analyze
from wave_recognizer_r3_v1_entry import load_market, write_results, encode
from wave_recognizer_r3_v1_visuals import write_pack
from wave_r3_clock_probe_v1 import observe_frozen
from wave_r3_clock_audit_v1 import summarize, latency_rows
from wave_r3_clock_checks_v1 import check_trace, check_subset_counts
from wave_r3_clock_files_v1 import fresh_root, no_links, write_bytes, write_trace, write_manifest, read_json

INPUT = Path('/work/inputs')
OUTPUT = Path('/results/study')
PROTOCOL = Path(__file__).with_name('wave_r3_clock_protocol_v1.json')

def enforce_parent(root, summary):
    import json
    p = json.loads(PROTOCOL.read_text())
    checks = {'parent/report.json':p['parent_report_sha256'],
              'visuals/index.json':p['parent_visual_index_sha256']}
    for name, expected in checks.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('frozen parent evidence identity mismatch')
    if {c['case_id']:c['bars'] for c in summary['residual_cases']}!=p['fixed_residuals']:
        raise ValueError('fixed residual population mismatch')
    recovery = summary['R1_recovery']
    if (recovery['episodes'],recovery['bars'],recovery['exact_92_subset_bars'])!=(5,414,92):
        raise ValueError('fixed R1 recovery population mismatch')
    if summary['bars']!=70114 or summary['final_low_latency']['waves_accounted']!=1932:
        raise ValueError('fixed carrier or wave population mismatch')
    index = read_json(root,'visuals/index.json')
    if len(index['panels'])!=33 or len(summary['R2_floor_controls'])!=8:
        raise ValueError('fixed visual population mismatch')
    j = summary['joint_short_low_amplitude']
    if j['T0_bars']!=21 or j['original_amplitude_Q1']!=0.006026317779015855:
        raise ValueError('diagnostic reference mismatch')

def emit_bundle(bars, output, *, formal):
    # In-memory synthetic test seam, never a runtime path/command argument.
    root = fresh_root(output)
    parent,candidate,base,r1,r2 = analyze(bars)
    observed,rows = observe_frozen(bars)
    check_trace(bars,observed,rows)
    summary = summarize(bars,parent,candidate,base,r1,r2,rows)
    check_subset_counts(summary,base,r1,candidate,len(bars))
    write_results(root/'parent',parent)
    write_pack(root/'visuals',bars,candidate,base,r2)
    if formal:
        enforce_parent(root,summary)
    events = dict(zip(('pivots','resets','rejections','maturities'),observed[1:]))
    write_bytes(root,'events.json',encode(events))
    write_bytes(root,'latency.json',encode(latency_rows(candidate)))
    write_trace(root,rows)
    write_bytes(root,'report.json',encode(summary))
    write_manifest(root)
    return summary

def main():
    if sys.argv[1:]:
        raise ValueError('entry accepts no arguments')
    no_links(INPUT/'5m_offset_0.parquet')
    if {p.name for p in INPUT.iterdir()}!={'5m_offset_0.parquet'}:
        raise ValueError('fixed input directory contains unexpected file')
    bars = load_market(INPUT)  # Original loader verifies exact bytes/hash and OHLC validity.
    emit_bundle(bars,OUTPUT,formal=True)

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print('R3_CLOCK_ENTRY_STOPPED:'+type(exc).__name__,file=sys.stderr)
        raise SystemExit(1)
