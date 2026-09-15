from __future__ import annotations
import argparse,csv,json,math,statistics
from pathlib import Path

H=15
HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025)
DEV_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023)
AUDIT_YEARS=(2024,2025)
ROWS_MIN=20;POS_MIN=4;NEG_MIN=4
HISTORY=8;HALF_LIFE=4.0
COV_MIN=.95;YEAR_COV_MIN=.80
DEV_MIN=200;AUDIT_MIN=80;DEV_TERCILE_MIN=30;AUDIT_TERCILE_MIN=15


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
def health(r):return .5*float(r['brier']>0)+.5*float(r['logloss']>0)

def score_rows(rows):
    out=[];hist=[]
    for r in rows:
        used=hist[-HISTORY:]
        score=float('nan')
        if evaluable(r) and len(used)==HISTORY:
            rev=list(reversed(used));weights=[2**(-i/HALF_LIFE) for i in range(HISTORY)]
            score=sum(w*health(x) for w,x in zip(weights,rev))/sum(weights)
        out.append({**r,'score':score,'history_evaluable_used':len(used),'joint_success':int(joint(r)) if evaluable(r) else ''})
        if evaluable(r):hist.append(r)
    return out

def rankdata(xs):
    order=sorted(range(len(xs)),key=lambda i:xs[i]);r=[0.0]*len(xs);i=0
    while i<len(order):
        j=i+1
        while j<len(order) and xs[order[j]]==xs[order[i]]:j+=1
        avg=(i+1+j)/2.0
        for k in range(i,j):r[order[k]]=avg
        i=j
    return r

def pearson(a,b):
    if len(a)<2:return float('nan')
    ma=sum(a)/len(a);mb=sum(b)/len(b);num=sum((x-ma)*(y-mb) for x,y in zip(a,b));da=sum((x-ma)**2 for x in a);db=sum((y-mb)**2 for y in b)
    return num/math.sqrt(da*db) if da>0 and db>0 else float('nan')
def spearman(a,b):return pearson(rankdata(a),rankdata(b))
def auc_binary(y,s):
    pos=sum(y);neg=len(y)-pos
    if pos==0 or neg==0:return float('nan')
    rr=rankdata(s);rank_pos=sum(v for v,t in zip(rr,y) if t==1)
    return (rank_pos-pos*(pos+1)/2)/(pos*neg)
def quantile(xs,q):
    z=sorted(xs)
    if not z:return float('nan')
    p=(len(z)-1)*q;lo=int(math.floor(p));hi=int(math.ceil(p))
    return z[lo] if lo==hi else z[lo]*(hi-p)+z[hi]*(p-lo)
def median(xs):return statistics.median(xs) if xs else float('nan')

def coverage_summary(rows):
    z=[r for r in rows if r['year'] in HARD_YEARS and evaluable(r)];s=[r for r in z if math.isfinite(r['score'])]
    yc={}
    for y in HARD_YEARS:
        a=[r for r in z if r['year']==y];b=[r for r in a if math.isfinite(r['score'])];yc[str(y)]=len(b)/len(a) if a else 0.0
    cov=len(s)/len(z) if z else 0.0;minyc=min(yc.values()) if yc else 0.0
    return {'evaluable':len(z),'scored':len(s),'score_coverage':cov,'hard_year_score_coverages':yc,'minimum_hard_year_score_coverage':minyc,'coverage_pass':cov>=COV_MIN and minyc>=YEAR_COV_MIN}

def assign_tercile(score,q1,q2):
    if not math.isfinite(score):return ''
    if score<q1:return 'low'
    if score>=q2:return 'high'
    return 'mid'
def sample_summary(rows,years,q1,q2,minn,tercile_min):
    z=[r for r in rows if r['year'] in years and evaluable(r) and math.isfinite(r['score'])]
    for r in z:r['tercile']=assign_tercile(r['score'],q1,q2)
    low=[r for r in z if r['tercile']=='low'];high=[r for r in z if r['tercile']=='high']
    y=[int(r['joint_success']) for r in z];s=[r['score'] for r in z]
    out={'n':len(z),'low_n':len(low),'high_n':len(high),'support_pass':len(z)>=minn and len(low)>=tercile_min and len(high)>=tercile_min and q1<q2,
         'joint_success_auroc':auc_binary(y,s),'spearman_brier':spearman(s,[r['brier'] for r in z]),'spearman_logloss':spearman(s,[r['logloss'] for r in z]),
         'low_joint_success':sum(int(r['joint_success']) for r in low)/len(low) if low else float('nan'),'high_joint_success':sum(int(r['joint_success']) for r in high)/len(high) if high else float('nan'),
         'low_median_brier':median([r['brier'] for r in low]),'high_median_brier':median([r['brier'] for r in high]),'low_median_logloss':median([r['logloss'] for r in low]),'high_median_logloss':median([r['logloss'] for r in high])}
    out['directional_pass']=bool(out['support_pass'] and out['joint_success_auroc']>.5 and out['spearman_brier']>0 and out['spearman_logloss']>0 and out['high_joint_success']>out['low_joint_success'] and out['high_median_brier']>out['low_median_brier'] and out['high_median_logloss']>out['low_median_logloss'])
    return out

def build(metrics:Path):
    rows=score_rows(load_weekly(metrics));dev_scores=[r['score'] for r in rows if r['year'] in DEV_YEARS and evaluable(r) and math.isfinite(r['score'])]
    q1=quantile(dev_scores,1/3);q2=quantile(dev_scores,2/3)
    for r in rows:r['tercile']=assign_tercile(r['score'],q1,q2);r['sample_group']='development' if r['year'] in DEV_YEARS else ('repeat_audit' if r['year'] in AUDIT_YEARS else 'other')
    cov=coverage_summary(rows);dev=sample_summary(rows,DEV_YEARS,q1,q2,DEV_MIN,DEV_TERCILE_MIN);audit=sample_summary(rows,AUDIT_YEARS,q1,q2,AUDIT_MIN,AUDIT_TERCILE_MIN)
    supported=bool(cov['coverage_pass'] and dev['directional_pass'] and audit['directional_pass'])
    result={'schema_id':'risk_tool_v2_15m_continuous_reliability_score_result@1.0','score_supported':supported,'score_formula':'8 prior evaluable endpoints; endpoint health=0.5*I(Brier>0)+0.5*I(LogLoss>0); recency weight=2^(-(lag-1)/4)','development_tercile_cutpoints':{'q33':q1,'q67':q2},'coverage':cov,'development':dev,'repeat_audit_2024_2025':audit,'current_v3_authority_immutable':True,'probability_modified':False,'ordering_modified':False,'year_2026_read':False,'pnl':False,'production_authority':False}
    return rows,result

def write_csv(path,rows):
    fields=['label','year','role','rows','positive','negative','brier','logloss','ordering','score','history_evaluable_used','joint_success','tercile','sample_group']
    with path.open('w',newline='') as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows([{k:r.get(k,'') for k in fields} for r in rows])
def run(metrics:Path,out:Path):
    rows,result=build(metrics);out.mkdir(parents=True,exist_ok=False);write_csv(out/'RELIABILITY_ENDPOINTS.csv',rows)
    (out/'RELIABILITY_RESULT.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=True)+'\n')
    summary={'schema_id':'risk_tool_v2_15m_continuous_reliability_score_summary@1.0','profile':'risk-v2-15m-continuous-reliability-score-v1','score_supported':result['score_supported'],'score_coverage':result['coverage']['score_coverage'],'minimum_hard_year_score_coverage':result['coverage']['minimum_hard_year_score_coverage'],'development_auroc':result['development']['joint_success_auroc'],'repeat_audit_auroc':result['repeat_audit_2024_2025']['joint_success_auroc'],'development_directional_pass':result['development']['directional_pass'],'repeat_audit_directional_pass':result['repeat_audit_2024_2025']['directional_pass'],'current_v3_authority_immutable':True,'year_2026_read':False,'production_authority':False}
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2,sort_keys=True,allow_nan=True)+'\n')
def main():
    p=argparse.ArgumentParser();p.add_argument('--metrics',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.metrics.resolve(),a.out.resolve())
if __name__=='__main__':main()
