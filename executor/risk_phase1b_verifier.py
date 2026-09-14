from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np,pandas as pd
from scipy.stats import rankdata
HS=(15,30);DEV=(2021,2022,2023);AUD=(2024,2025);SYM=("000688.SH","000852.SH");REPS=5000;SEED=20260914;LAM=1e-6
PSTATE="e74e497ddf075f7b1519ab3afd96dddfeafbeafce7e4bab86a77d9037e23e30d";PCOH="53276c7f25861b8a064288f8662c1a391c0c5af75758376df60e98ab180c4234"
def sha(p):
 with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def auc(y,p):
 y=np.asarray(y,int);a=int(y.sum());b=len(y)-a;r=rankdata(p);return float((r[y==1].sum()-a*(a+1)/2)/(a*b))
def g(x,y,b,c):
 Y=x[y].to_numpy(int)
 def s(p):
  q=np.clip(p,1e-12,1-1e-12);return auc(Y,p),float(np.mean((p-Y)**2)),float(-np.mean(Y*np.log(q)+(1-Y)*np.log(1-q)))
 B=s(x[b].to_numpy(float));C=s(x[c].to_numpy(float));return np.array([C[0]-B[0],B[1]-C[1],B[2]-C[2]])
def fc(p,y):
 q=np.clip(p,1e-6,1-1e-6);z=np.log(q/(1-q));X=np.column_stack([np.ones(len(z)),z]);b=np.zeros(2);P=np.diag([0.,LAM])
 for _ in range(100):
  e=X@b;u=np.where(e>=0,1/(1+np.exp(-e)),np.exp(e)/(1+np.exp(e)));w=np.maximum(u*(1-u),1e-12);d=np.linalg.solve((X.T*w)@X/len(y)+P,X.T@(u-y)/len(y)+P@b);b-=d
  if np.max(np.abs(d))<=1e-10:return b
 raise RuntimeError("calibrator")
def ap(b,p):
 q=np.clip(p,1e-6,1-1e-6);z=np.log(q/(1-q));e=b[0]+b[1]*z;return np.where(e>=0,1/(1+np.exp(-e)),np.exp(e)/(1+np.exp(e)))
def boot(x,y,b,c):
 G=[(z[y].to_numpy(int),z[b].to_numpy(float),z[c].to_numpy(float)) for _,z in x.groupby("trading_day",sort=True)];r=np.random.default_rng(SEED);d=np.empty(REPS)
 for i in range(REPS):
  k=r.integers(0,len(G),len(G));Y=np.concatenate([G[j][0] for j in k]);B=np.concatenate([G[j][1] for j in k]);C=np.concatenate([G[j][2] for j in k]);d[i]=auc(Y,C)-auc(Y,B)
 return float(np.quantile(d,.025))
def close(a,b,t=1e-11):return bool(np.allclose(np.asarray(a,float),np.asarray(b,float),rtol=0,atol=t,equal_nan=True))
def main():
 p=argparse.ArgumentParser();p.add_argument("--results",type=Path,required=True);a=p.parse_args();r=a.results
 if sha(r/"state_rows.parquet")!=PSTATE or sha(r/"cohort_rows.parquet")!=PCOH:raise RuntimeError("parent hash")
 x=pd.read_parquet(r/"cohort_rows.parquet");S=json.loads((r/"SUMMARY.json").read_text());F=json.loads((r/"CALIBRATION_FREEZE.json").read_text());G=json.loads((r/"FRESH_OOS_GATE.json").read_text());M=pd.read_csv(r/"HORIZON_METRICS.csv")
 eligible=[]
 for h in HS:
  y=f"normal_within_{h}m";b=f"p_B_{h}m";c=f"p_C_{h}m";D=x[x.year.isin(DEV)&x[y].notna()].copy();A=x[x.year.isin(AUD)&x[y].notna()].copy();raw=g(D,y,b,c);lo=boot(D,y,b,c);Y={v:g(D[D.year.eq(v)],y,b,c) for v in DEV};DS={s:g(D[D.symbol.eq(s)],y,b,c) for s in SYM};AR=g(A,y,b,c);AY={v:g(A[A.year.eq(v)],y,b,c) for v in AUD};AS={s:g(A[A.symbol.eq(s)],y,b,c) for s in SYM}
  parts=[];fits={}
  for v in DEV:
   tr=D[D.year.ne(v)];te=D[D.year.eq(v)].copy();B=fc(tr[b].to_numpy(),tr[y].to_numpy(int));C=fc(tr[c].to_numpy(),tr[y].to_numpy(int));te["cb"]=ap(B,te[b]);te["cc"]=ap(C,te[c]);parts.append(te);fits[str(v)]={"B":B,"C":C}
  Z=pd.concat(parts);CG=g(Z,y,"cb","cc");B=fc(D[b].to_numpy(),D[y].to_numpy(int));C=fc(D[c].to_numpy(),D[y].to_numpy(int));A["cb"]=ap(B,A[b]);A["cc"]=ap(C,A[c]);CA=g(A,y,"cb","cc");CAY={v:g(A[A.year.eq(v)],y,"cb","cc") for v in AUD};CAS={s:g(A[A.symbol.eq(s)],y,"cb","cc") for s in SYM}
  og=[raw[0]>0,lo>0,sum(Y[v][0]>=0 for v in DEV)>=2,all(DS[s][0]>=0 for s in SYM),AR[0]>=0,all(AY[v][0]>=0 for v in AUD),all(AS[s][0]>=0 for s in SYM)];oo=all(og)
  pg=[oo,CG[1]>0,CG[2]>0,sum(g(Z[Z.year.eq(v)],y,"cb","cc")[1]>=0 and g(Z[Z.year.eq(v)],y,"cb","cc")[2]>=0 for v in DEV)>=2,CA[1]>=0,CA[2]>=0,all(CAY[v][1]>=0 and CAY[v][2]>=0 for v in AUD),all(CAS[s][1]>=0 and CAS[s][2]>=0 for s in SYM)];po=all(pg);status="ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS" if oo and po else ("ORDERING_ONLY_CALIBRATION_NOT_SUPPORTED" if oo else "NOT_SUPPORTED")
  q=S["horizons"][str(h)]
  if q["status"]!=status or q["ordering_gates"]!=og or q["calibration_gates"]!=pg:raise RuntimeError("summary verdict mismatch")
  if not close([q["raw_dev"]["auroc_gain"],q["raw_dev"]["brier_gain"],q["raw_dev"]["logloss_gain"],q["bootstrap_lower"],q["raw_audit"]["auroc_gain"],q["cal_dev"]["brier_gain"],q["cal_dev"]["logloss_gain"],q["cal_audit"]["brier_gain"],q["cal_audit"]["logloss_gain"]],[raw[0],raw[1],raw[2],lo,AR[0],CG[1],CG[2],CA[1],CA[2]]):raise RuntimeError("metric mismatch")
  fr=F["fits"][str(h)]
  for v in DEV:
   if not close(fr["development_loyo"][str(v)]["B"],fits[str(v)]["B"]) or not close(fr["development_loyo"][str(v)]["C"],fits[str(v)]["C"]):raise RuntimeError("calibration mismatch")
  if not close(fr["audit"]["B"],B) or not close(fr["audit"]["C"],C):raise RuntimeError("audit calibration mismatch")
  row=M[M.horizon_minutes.eq(h)].iloc[0]
  if row.status!=status or not close([row.dev_auroc_gain,row.dev_bootstrap_lower,row.dev_cal_brier_gain,row.dev_cal_logloss_gain,row.audit_auroc_gain,row.audit_cal_brier_gain,row.audit_cal_logloss_gain],[raw[0],lo,CG[1],CG[2],AR[0],CA[1],CA[2]]):raise RuntimeError("csv mismatch")
  if status=="ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS":eligible.append(h)
 if S["eligible_fresh_oos_horizons_minutes"]!=eligible or bool(S["fresh_oos_unlocked"])!=bool(eligible) or G["eligible_horizons_minutes"]!=eligible or bool(G["unlocked"])!=bool(eligible) or S["year_2026_read"] is not False or G["year_2026_read"] is not False:raise RuntimeError("fresh OOS gate mismatch")
 print(json.dumps({"status":"passed","verified_horizons":[15,30],"year_2026_read":False,"production_authority":False},sort_keys=True))
if __name__=="__main__":
 try:main()
 except Exception as e:print(json.dumps({"status":"failed","reason":"phase1b_verifier_exception","exception_type":type(e).__name__},sort_keys=True));sys.exit(1)
