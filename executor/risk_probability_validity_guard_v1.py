from __future__ import annotations
import argparse,csv,json,math,statistics
from pathlib import Path

H=15
HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025)
SELECT_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023)
AUDIT_YEARS=(2024,2025)
CANDIDATES=(('control',0),('g4',4),('g8',8),('g13',13))
PREF={'control':0,'g13':1,'g8':2,'g4':3}
ROWS_MIN=20;POS_MIN=4;NEG_MIN=4
COV_MIN=.70;YEAR_COV_MIN=.50


def f(x):
    try:return float(x)
    except:return float('nan')

def load_weekly(path:Path):
    rows=[]
    with path.open(newline='') as h:
        for r in csv.DictReader(h):
            if int(r['horizon_minutes'])!=H or r['period_level']!='weekly':continue
            rows.append({'label':r['period_label'],'year':int(r['period_label'][:4]),'role':r['role'],'rows':int(r['rows']),'positive':int(r['positive']),'negative':int(r['negative']),'brier':f(r['cal_brier_gain']),'logloss':f(r['cal_logloss_gain']),'ordering':f(r['ordering_gain'])})
    rows.sort(key=lambda r:r['label'])
    return rows

def evaluable(r):return r['rows']>=ROWS_MIN and r['positive']>=POS_MIN and r['negative']>=NEG_MIN and math.isfinite(r['brier']) and math.isfinite(r['logloss'])
def joint(r):return r['brier']>0 and r['logloss']>0

def decide(rows,n):
    out=[];hist=[]
    for r in rows:
        if not evaluable(r):mode='unevaluable';used=[]
        elif n==0:mode='probability';used=[]
        else:
            used=hist[-n:];need=math.ceil(.75*n)
            ok=len(used)>=need and sum(joint(x) for x in used)/len(used)>=.50 and statistics.median(x['brier'] for x in used)>0 and statistics.median(x['logloss'] for x in used)>0
            mode='probability' if ok else 'ranking_only'
        out.append({**r,'mode':mode,'history_evaluable_used':len(used),'candidate_history':n})
        if evaluable(r):hist.append(r)
    return out

def longest_failure_streak(items):
    best=cur=0
    for r in items:
        if r['mode']=='probability' and not joint(r):cur+=1;best=max(best,cur)
        else:cur=0
    return best

def summarize(items,years):
    z=[r for r in items if r['year'] in years and evaluable(r)]
    prob=[r for r in z if r['mode']=='probability']
    cov=len(prob)/len(z) if z else 0.0
    yc={}
    for y in years:
        a=[r for r in z if r['year']==y];p=[r for r in a if r['mode']=='probability'];yc[str(y)]=len(p)/len(a) if a else 0.0
    minyc=min(yc.values()) if yc else 0.0
    if prob:
        jf=sum(joint(r) for r in prob)/len(prob);mb=statistics.median(r['brier'] for r in prob);ml=statistics.median(r['logloss'] for r in prob);st=longest_failure_streak([r for r in items if r['year'] in years])
        pfail=sum(not joint(r) for r in prob)/len(prob)
    else:jf=mb=ml=0.0;st=10**9;pfail=1.0
    rank=[r for r in z if r['mode']=='ranking_only'];rfail=(sum(not joint(r) for r in rank)/len(rank)) if rank else float('nan')
    covpass=cov>=COV_MIN and minyc>=YEAR_COV_MIN
    calpass=jf>=.50 and mb>0 and ml>0 and st<=8
    return {'evaluable':len(z),'probability_mode':len(prob),'ranking_only':len(rank),'probability_mode_coverage':cov,'hard_year_probability_mode_coverages':yc,'minimum_hard_year_probability_mode_coverage':minyc,'coverage_pass':covpass,'joint_calibration_positive_fraction':jf,'median_brier_gain':mb,'median_logloss_gain':ml,'max_calibration_failure_streak':st,'calibration_pass':calpass,'probability_mode_failure_rate':pfail,'ranking_only_failure_rate':rfail,'guard_pass':covpass and calpass}
def key(s,cid):return (s['max_calibration_failure_streak'],-s['joint_calibration_positive_fraction'],-s['median_brier_gain'],-s['median_logloss_gain'],-s['probability_mode_coverage'],PREF[cid])

def build(metrics:Path):
    rows=load_weekly(metrics);cands=[];cache={}
    for cid,n in CANDIDATES:
        modes=decide(rows,n);dev=summarize(modes,SELECT_YEARS);cands.append({'candidate':cid,'history_evaluable_endpoints':n,**{k:v for k,v in dev.items() if k!='hard_year_probability_mode_coverages'}});cache[cid]=modes
    eligible=[r for r in cands if r['coverage_pass']]
    selected=min(eligible,key=lambda r:key(r,r['candidate']))['candidate'] if eligible else None
    if selected is None:return cands,[],{'schema_id':'risk_tool_v2_15m_probability_validity_guard_result@1.0','selected_candidate':None,'guard_supported':False,'reason':'no_candidate_passed_coverage_gate','year_2026_read':False,'production_authority':False}
    modes=cache[selected];full=summarize(modes,HARD_YEARS);audit=summarize(modes,AUDIT_YEARS)
    supported=bool(full['guard_pass'] and audit['guard_pass'])
    result={'schema_id':'risk_tool_v2_15m_probability_validity_guard_result@1.0','selected_candidate':selected,'guard_supported':supported,'output_contract':'probability_when_guard_true_else_ranking_only','full_hard_years':full,'repeat_audit_2024_2025':audit,'selection_uses_2024_2025':False,'ordering_modified':False,'probability_refit':False,'current_v3_authority_immutable':True,'year_2026_read':False,'pnl':False,'production_authority':False}
    return cands,modes,result

def write_csv(path,rows,fields):
    with path.open('w',newline='') as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows([{k:r.get(k,'') for k in fields} for r in rows])
def run(metrics:Path,out:Path):
    cands,modes,result=build(metrics);out.mkdir(parents=True,exist_ok=False)
    write_csv(out/'GUARD_CANDIDATES.csv',cands,['candidate','history_evaluable_endpoints','evaluable','probability_mode','ranking_only','probability_mode_coverage','minimum_hard_year_probability_mode_coverage','coverage_pass','joint_calibration_positive_fraction','median_brier_gain','median_logloss_gain','max_calibration_failure_streak','calibration_pass','probability_mode_failure_rate','ranking_only_failure_rate','guard_pass'])
    if modes:write_csv(out/'GUARD_ENDPOINT_MODES.csv',modes,['label','year','role','rows','positive','negative','brier','logloss','ordering','mode','history_evaluable_used','candidate_history'])
    (out/'GUARD_RESULT.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=True)+'\n')
    summary={'schema_id':'risk_tool_v2_15m_probability_validity_guard_summary@1.0','profile':'risk-v2-15m-probability-validity-guard-v1','selected_candidate':result.get('selected_candidate'),'guard_supported':result['guard_supported'],'probability_mode_coverage':result.get('full_hard_years',{}).get('probability_mode_coverage'),'minimum_hard_year_probability_mode_coverage':result.get('full_hard_years',{}).get('minimum_hard_year_probability_mode_coverage'),'retained_joint_positive_fraction':result.get('full_hard_years',{}).get('joint_calibration_positive_fraction'),'retained_max_failure_streak':result.get('full_hard_years',{}).get('max_calibration_failure_streak'),'repeat_audit_pass':result.get('repeat_audit_2024_2025',{}).get('guard_pass'),'current_v3_authority_immutable':True,'year_2026_read':False,'production_authority':False}
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2,sort_keys=True,allow_nan=True)+'\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--metrics',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.metrics.resolve(),a.out.resolve())
if __name__=='__main__':main()
