"""Independent read-only verifier for blindspot relocation V1."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from wave_blindspot_relocation_v1 import analyze, causal_state
from wave_blindspot_relocation_v1_entry import clean, load_market
from wave_cycle_identifiability_v1 import analyze as old_identifiability
from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_scale_specific_continuity_v1_verifier import verify_original_base


def _prepared(stage):
    return {
        'pivots': stage['pivots'],
        'pivot_known': [p['known_from_bar'] for p in stage['pivots']],
        'waves': stage['waves'],
        'wave_known': [w['known_from_bar'] for w in stage['waves']],
        'stream': stage['stream'],
        'node_known': [n['known_from_bar'] for n in stage['stream']],
    }


def verify_prefixes(bars, samples=6):
    base=base_inventory(bars);full=continuity_hierarchy(base,1,3)
    lo=min(5000,max(100,len(bars)//4));hi=max(lo,len(bars)-1000)
    cutoffs=sorted(set(int(x) for x in np.linspace(lo,hi,samples)));checked=0
    for t in cutoffs:
        prefix=bars.iloc[:t+1].copy();pb=base_inventory(prefix);ph=continuity_hierarchy(pb,1,3)
        for stage_index in (1,2):
            a=causal_state(_prepared(full['stages'][stage_index]),t)
            b=causal_state(_prepared(ph['stages'][stage_index]),t)
            if a['status']!=b['status']:
                raise ValueError('causal state prefix status drift')
            if a['status']=='RESOLVED':
                for k in ('descriptor','leg','phase','crossing'):
                    if a[k]!=b[k]: raise ValueError('causal state prefix label drift')
                for k in ('period','amplitude','age_ratio'):
                    if not math.isclose(a[k],b[k],rel_tol=0,abs_tol=1e-12):
                        raise ValueError('causal state prefix numeric drift')
            checked+=1
    return {'cutoffs':cutoffs,'level_states_checked':checked}


def verify_frozen_blind_population(bars, observed):
    old=old_identifiability(bars)
    if old['counts']['blind_bars']!=observed['counts']['blind_bars']:
        raise ValueError('frozen blind bar population drift')
    if old['counts']['blind_episodes']!=observed['counts']['blind_episodes']:
        raise ValueError('frozen blind episode population drift')
    old_reasons=old['overall']['reason_counts']
    if old_reasons.get('RESET_ROOT_BREAK',0)!=observed['counts']['reset_root_break_episodes']:
        raise ValueError('frozen RESET_ROOT_BREAK population drift')
    if old['overall']['amplitude_quartile_counts']!=observed['amplitude_quartile_counts']:
        raise ValueError('frozen blind amplitude buckets drift')
    return {
        'blind_bars_checked':old['counts']['blind_bars'],
        'blind_episodes_checked':old['counts']['blind_episodes'],
        'reset_root_break_checked':old_reasons.get('RESET_ROOT_BREAK',0),
    }


def verify_report(bars, out):
    out=Path(out)
    if out.is_symlink() or not out.is_dir() or {p.name for p in out.iterdir()}!={'report.json','manifest.json'}:
        raise ValueError('output set drift')
    manifest=json.loads((out/'manifest.json').read_text())
    raw=(out/'report.json').read_bytes();meta={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    if manifest['files']['report.json']!=meta or manifest.get('production_authority') is not False:
        raise ValueError('manifest/hash/authority drift')
    observed=json.loads(raw);rebuilt=clean(analyze(bars))
    for k,v in rebuilt.items():
        if observed.get(k)!=v: raise ValueError('aggregate reconstruction mismatch '+k)
    if observed.get('data_role')!='PREVIOUSLY_CONSUMED_DEVELOPMENT_NOT_FRESH_OOS':
        raise ValueError('data role drift')
    if observed.get('source_data_sha256')!='bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48':
        raise ValueError('data identity drift')
    if observed.get('one_minute_admitted') or observed.get('outcomes_used') or any(observed['authority'].values()):
        raise ValueError('research boundary drift')
    base=base_inventory(bars)
    original=verify_original_base(bars,base)
    frozen=verify_frozen_blind_population(bars,observed)
    prefix=verify_prefixes(bars)
    return {
        'status':'passed','original_base':original,'frozen_blind_population':frozen,
        'prefix':prefix,'aggregate_only':True,'production_authority':False,
    }


verify = verify_report

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--results',required=True);a=p.parse_args()
    if a.inputs!='/work/inputs' or a.results!='/results/study':
        raise ValueError('fixed paths only')
    print(json.dumps(verify_report(load_market(a.inputs),a.results),sort_keys=True))


if __name__=='__main__': main()
