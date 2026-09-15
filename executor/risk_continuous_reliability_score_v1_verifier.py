from __future__ import annotations
import argparse,csv,json,math,statistics
from pathlib import Path
H=15;HARD=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025);DEV=(2015,2016,2017,2018,2019,2021,2022,2023);AUDIT=(2024,2025)
ROWS=20;POS=4;NEG=4;N=8;HL=4.0

def f(x):
    try:return float(x)
    except:return float('nan')
def load_rows(p):
    out=[]
    with p.open(newline='') as h:
        for r in csv.DictReader(h):
            if int(r['horizon_minutes'])==H and r['period_level']=='weekly':out.append({'label':r['period_label'],'year':int(r['period_label'][:4]),'role':r['role'],'rows':int(r['rows']),'positive':int(r['positive']),'negative':int(r['negative']),'brier':f(r['cal_brier_gain']),'logloss':f(r['cal_logloss_gain']),'ordering':f(r['ordering_gain'])})
    return sorted(out,key=lambda x:x['label'])
def ok(r):return r['rows']>=ROWS and r['positive']>=POS and r['negative']>=NEG and math.isfinite(r['brier']) and math.isfinite(r['logloss'])
def health(r):return .5*float(r['brier']>0)+.5*float(r['logloss']>0)
def ranks(x):
    idx=sorted(range(len(x)),key=lambda i:x[i]);r=[0.0]*len(x);i=0
    while i<len(idx):
        j=i+1
        while j<len(idx) and x[idx[j]]==x[idx[i]]:j+=1
        v=(i+1+j)/2
        for k in range(i,j):r[idx[k]]=v
        i=j
    return r
def pearson(a,b):
    if len(a)<2:return float('nan')
    ma=sum(a)/len(a);mb=sum(b)/len(b);num=sum((x-ma)*(y-mb) for x,y in zip(a,b));da=sum((x-ma)**2 for x in a);db=sum((y-mb)**2 for y in b)
    return num/math.sqrt(da*db) if da and db else float('nan')
def auc(y,s):
    p=sum(y);n=len(y)-p
    if p==0 or n==0:return float('nan')
    rr=ranks(s);return (sum(v for v,t in zip(rr,y) if t)-p*(p+1)/2)/(p*n)
def quantile(x,q):
    z=sorted(x);p=(len(z)-1)*q;lo=int(math.floor(p));hi=int(math.ceil(p));return z[lo] if lo==hi else z[lo]*(hi-p)+z[hi]*(p-lo)
def score(rows):
    hist=[];out=[]
    for r in rows:
        used=hist[-N:];s=float('nan')
        if ok(r) and len(used)==N:
            rev=list(reversed(used));w=[2**(-i/HL) for i in range(N)];s=sum(a*health(b) for a,b in zip(w,rev))/sum(w)
        out.append({**r,'score':s,'history_evaluable_used':len(used),'joint_success':int(r['brier']>0 and r['logloss']>0) if ok(r) else ''})
        if ok(r):hist.append(r)
    return out
def terc(s,q1,q2):return '' if not math.isfinite(s) else ('low' if s<q1 else ('high' if s>=q2 else 'mid'))
def summarize(rows,years,q1,q2,minn,tmin):
    z=[r for r in rows if r['year'] in years and ok(r) and math.isfinite(r['score'])];low=[r for r in z if terc(r['score'],q1,q2)=='low'];high=[r for r in z if terc(r['score'],q1,q2)=='high'];s=[r['score'] for r in z];y=[r['joint_success'] for r in z]
    spb=pearson(ranks(s),ranks([r['brier'] for r in z]));spl=pearson(ranks(s),ranks([r['logloss'] for r in z]));med=lambda a:statistics.median(a) if a else float('nan')
    d={'n':len(z),'low_n':len(low),'high_n':len(high),'support_pass':len(z)>=minn and len(low)>=tmin and len(high)>=tmin and q1<q2,'joint_success_auroc':auc(y,s),'spearman_brier':spb,'spearman_logloss':spl,'low_joint_success':sum(r['joint_success'] for r in low)/len(low) if low else float('nan'),'high_joint_success':sum(r['joint_success'] for r in high)/len(high) if high else float('nan'),'low_median_brier':med([r['brier'] for r in low]),'high_median_brier':med([r['brier'] for r in high]),'low_median_logloss':med([r['logloss'] for r in low]),'high_median_logloss':med([r['logloss'] for r in high])}
    d['directional_pass']=bool(d['support_pass'] and d['joint_success_auroc']>.5 and d['spearman_brier']>0 and d['spearman_logloss']>0 and d['high_joint_success']>d['low_joint_success'] and d['high_median_brier']>d['low_median_brier'] and d['high_median_logloss']>d['low_median_logloss']);return d
def reconstruct(metrics):
    rows=score(load_rows(metrics));devs=[r['score'] for r in rows if r['year'] in DEV and ok(r) and math.isfinite(r['score'])];q1=quantile(devs,1/3);q2=quantile(devs,2/3)
    for r in rows:r['tercile']=terc(r['score'],q1,q2);r['sample_group']='development' if r['year'] in DEV else ('repeat_audit' if r['year'] in AUDIT else 'other')
    z=[r for r in rows if r['year'] in HARD and ok(r)];sc=[r for r in z if math.isfinite(r['score'])];yc={str(y):len([r for r in z if r['year']==y and math.isfinite(r['score'])])/len([r for r in z if r['year']==y]) for y in HARD};cov={'evaluable':len(z),'scored':len(sc),'score_coverage':len(sc)/len(z),'hard_year_score_coverages':yc,'minimum_hard_year_score_coverage':min(yc.values())};cov['coverage_pass']=cov['score_coverage']>=.95 and cov['minimum_hard_year_score_coverage']>=.80
    dev=summarize(rows,DEV,q1,q2,200,30);audit=summarize(rows,AUDIT,q1,q2,80,15);supported=bool(cov['coverage_pass'] and dev['directional_pass'] and audit['directional_pass'])
    result={'schema_id':'risk_tool_v2_15m_continuous_reliability_score_result@1.0','score_supported':supported,'score_formula':'8 prior evaluable endpoints; endpoint health=0.5*I(Brier>0)+0.5*I(LogLoss>0); recency weight=2^(-(lag-1)/4)','development_tercile_cutpoints':{'q33':q1,'q67':q2},'coverage':cov,'development':dev,'repeat_audit_2024_2025':audit,'current_v3_authority_immutable':True,'probability_modified':False,'ordering_modified':False,'year_2026_read':False,'pnl':False,'production_authority':False}
    return rows,result
def close(a,b,path='root'):
    if isinstance(a,dict):
        if set(a)!=set(b):raise RuntimeError(path+'_keys')
        for k in a:close(a[k],b[k],path+'.'+k)
    elif isinstance(a,(int,float)) and isinstance(b,(int,float)):
        if not math.isclose(float(a),float(b),rel_tol=0,abs_tol=1e-12) and not (math.isnan(float(a)) and math.isnan(float(b))):raise RuntimeError(path+'_numeric')
    elif a!=b:raise RuntimeError(path+'_value')
def main():
    p=argparse.ArgumentParser();p.add_argument('--metrics',type=Path,required=True);p.add_argument('--results',type=Path,required=True);a=p.parse_args();rows,res=reconstruct(a.metrics.resolve());got=json.loads((a.results/'RELIABILITY_RESULT.json').read_text());close(got,res)
    ep=list(csv.DictReader((a.results/'RELIABILITY_ENDPOINTS.csv').open(newline='')))
    if len(ep)!=len(rows):raise RuntimeError('endpoint_row_count_mismatch')
    for g,e in zip(ep,rows):
        if g['label']!=e['label'] or int(g['history_evaluable_used'])!=e['history_evaluable_used']:raise RuntimeError('endpoint_identity_mismatch')
        gs=f(g['score']);es=e['score']
        if not ((math.isnan(gs) and math.isnan(es)) or math.isclose(gs,es,rel_tol=0,abs_tol=1e-12)):raise RuntimeError('endpoint_score_mismatch')
    print(json.dumps({'status':'passed','score_supported':res['score_supported'],'development_auroc':res['development']['joint_success_auroc'],'repeat_audit_auroc':res['repeat_audit_2024_2025']['joint_success_auroc']},sort_keys=True))
if __name__=='__main__':main()
