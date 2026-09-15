from __future__ import annotations
import argparse,csv,json,math,statistics
from pathlib import Path
H=15;HARD=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025);SELECT=(2015,2016,2017,2018,2019,2021,2022,2023);AUDIT=(2024,2025)
CANDS=(('control',0),('g4',4),('g8',8),('g13',13));PREF={'control':0,'g13':1,'g8':2,'g4':3};ROWS=20;POS=4;NEG=4

def f(x):
    try:return float(x)
    except:return float('nan')
def load_rows(path):
    out=[]
    with path.open(newline='') as h:
        for r in csv.DictReader(h):
            if int(r['horizon_minutes'])==15 and r['period_level']=='weekly':out.append({'label':r['period_label'],'year':int(r['period_label'][:4]),'role':r['role'],'rows':int(r['rows']),'positive':int(r['positive']),'negative':int(r['negative']),'brier':f(r['cal_brier_gain']),'logloss':f(r['cal_logloss_gain']),'ordering':f(r['ordering_gain'])})
    return sorted(out,key=lambda x:x['label'])
def ev(r):return r['rows']>=ROWS and r['positive']>=POS and r['negative']>=NEG and math.isfinite(r['brier']) and math.isfinite(r['logloss'])
def jp(r):return r['brier']>0 and r['logloss']>0
def modes(rows,n):
    ans=[];hist=[]
    for r in rows:
        if not ev(r):m='unevaluable';u=[]
        elif n==0:m='probability';u=[]
        else:
            u=hist[-n:];need=math.ceil(.75*n);ok=len(u)>=need and sum(jp(x) for x in u)/len(u)>=.5 and statistics.median(x['brier'] for x in u)>0 and statistics.median(x['logloss'] for x in u)>0;m='probability' if ok else 'ranking_only'
        ans.append({**r,'mode':m,'history_evaluable_used':len(u),'candidate_history':n})
        if ev(r):hist.append(r)
    return ans
def streak(rows,years):
    b=c=0
    for r in rows:
        if r['year'] in years and r['mode']=='probability' and not jp(r):c+=1;b=max(b,c)
        else:c=0
    return b
def sumry(rows,years):
    z=[r for r in rows if r['year'] in years and ev(r)];p=[r for r in z if r['mode']=='probability'];q=[r for r in z if r['mode']=='ranking_only'];cov=len(p)/len(z) if z else 0.;yc={}
    for y in years:
        a=[r for r in z if r['year']==y];yc[str(y)]=sum(r['mode']=='probability' for r in a)/len(a) if a else 0.
    mn=min(yc.values()) if yc else 0.;jf=sum(jp(r) for r in p)/len(p) if p else 0.;mb=statistics.median(r['brier'] for r in p) if p else 0.;ml=statistics.median(r['logloss'] for r in p) if p else 0.;st=streak(rows,years);pf=sum(not jp(r) for r in p)/len(p) if p else 1.;rf=sum(not jp(r) for r in q)/len(q) if q else float('nan');cp=cov>=.70 and mn>=.50;cal=jf>=.50 and mb>0 and ml>0 and st<=8
    return {'evaluable':len(z),'probability_mode':len(p),'ranking_only':len(q),'probability_mode_coverage':cov,'hard_year_probability_mode_coverages':yc,'minimum_hard_year_probability_mode_coverage':mn,'coverage_pass':cp,'joint_calibration_positive_fraction':jf,'median_brier_gain':mb,'median_logloss_gain':ml,'max_calibration_failure_streak':st,'calibration_pass':cal,'probability_mode_failure_rate':pf,'ranking_only_failure_rate':rf,'guard_pass':cp and cal}
def build(path):
    rr=load_rows(path);cs=[];cache={}
    for cid,n in CANDS:
        m=modes(rr,n);s=sumry(m,SELECT);cs.append({'candidate':cid,'history_evaluable_endpoints':n,**{k:v for k,v in s.items() if k!='hard_year_probability_mode_coverages'}});cache[cid]=m
    ok=[x for x in cs if x['coverage_pass']];key=lambda x:(x['max_calibration_failure_streak'],-x['joint_calibration_positive_fraction'],-x['median_brier_gain'],-x['median_logloss_gain'],-x['probability_mode_coverage'],PREF[x['candidate']]);sel=min(ok,key=key)['candidate'] if ok else None
    if sel is None:return cs,[],{'schema_id':'risk_tool_v2_15m_probability_validity_guard_result@1.0','selected_candidate':None,'guard_supported':False,'reason':'no_candidate_passed_coverage_gate','year_2026_read':False,'production_authority':False}
    mm=cache[sel];full=sumry(mm,HARD);audit=sumry(mm,AUDIT);res={'schema_id':'risk_tool_v2_15m_probability_validity_guard_result@1.0','selected_candidate':sel,'guard_supported':bool(full['guard_pass'] and audit['guard_pass']),'output_contract':'probability_when_guard_true_else_ranking_only','full_hard_years':full,'repeat_audit_2024_2025':audit,'selection_uses_2024_2025':False,'ordering_modified':False,'probability_refit':False,'current_v3_authority_immutable':True,'year_2026_read':False,'pnl':False,'production_authority':False};return cs,mm,res
def eq(a,b,path='root'):
    if isinstance(a,dict) and isinstance(b,dict):
        if set(a)!=set(b):raise RuntimeError(path+'_keys')
        for k in a:eq(a[k],b[k],path+'.'+k)
    elif isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):raise RuntimeError(path+'_len')
        for i,(x,y) in enumerate(zip(a,b)):eq(x,y,path+f'[{i}]')
    elif isinstance(a,(int,float)) and isinstance(b,(int,float)):
        if math.isnan(float(a)) and math.isnan(float(b)):return
        if abs(float(a)-float(b))>1e-12:raise RuntimeError(path+'_num')
    elif a!=b:raise RuntimeError(path+'_value')
def main():
    p=argparse.ArgumentParser();p.add_argument('--metrics',type=Path,required=True);p.add_argument('--results',type=Path,required=True);a=p.parse_args();cs,mm,res=build(a.metrics.resolve());got=json.loads((a.results/'GUARD_RESULT.json').read_text());eq(got,res,'guard_result');s=json.loads((a.results/'SUMMARY.json').read_text());
    if s.get('selected_candidate')!=res.get('selected_candidate') or bool(s.get('guard_supported'))!=bool(res.get('guard_supported')) or s.get('year_2026_read') is not False:raise RuntimeError('summary_mismatch')
    print(json.dumps({'status':'passed','selected_candidate':res.get('selected_candidate'),'guard_supported':res.get('guard_supported')},sort_keys=True))
if __name__=='__main__':main()
