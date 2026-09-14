from __future__ import annotations
import argparse,hashlib,importlib.util,json,tempfile
from pathlib import Path
import numpy as np,pandas as pd
from scipy.stats import rankdata
HS=(15,30);DEV=(2021,2022,2023);AUD=(2024,2025);SYM=("000688.SH","000852.SH");REPS=5000;SEED=20260914;LAM=1e-6
PSTATE="e74e497ddf075f7b1519ab3afd96dddfeafbeafce7e4bab86a77d9037e23e30d";PCOH="53276c7f25861b8a064288f8662c1a391c0c5af75758376df60e98ab180c4234"
def loadmod(p):s=importlib.util.spec_from_file_location("p",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def sha(p):
 with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def auc(y,p):
 y=np.asarray(y,int);a=int(y.sum());b=len(y)-a;r=rankdata(p);return float((r[y==1].sum()-a*(a+1)/2)/(a*b))
def gain(x,y,b,c):
 Y=x[y].to_numpy(int);B=x[b].to_numpy(float);C=x[c].to_numpy(float)
 def s(p):
  q=np.clip(p,1e-12,1-1e-12);return auc(Y,p),float(np.mean((p-Y)**2)),float(-np.mean(Y*np.log(q)+(1-Y)*np.log(1-q)))
 u=s(B);v=s(C);return {"auroc_gain":v[0]-u[0],"brier_gain":u[1]-v[1],"logloss_gain":u[2]-v[2]}
def fitcal(p,y):
 z=np.log(np.clip(p,1e-6,1-1e-6)/(1-np.clip(p,1e-6,1-1e-6)));X=np.column_stack([np.ones(len(z)),z]);b=np.zeros(2);P=np.diag([0.,LAM])
 for _ in range(100):
  e=X@b;q=np.where(e>=0,1/(1+np.exp(-e)),np.exp(e)/(1+np.exp(e)));w=np.maximum(q*(1-q),1e-12);d=np.linalg.solve((X.T*w)@X/len(y)+P,X.T@(q-y)/len(y)+P@b);b-=d
  if np.max(np.abs(d))<=1e-10:return b
 raise RuntimeError("calibration fit")
def apply(b,p):
 z=np.log(np.clip(p,1e-6,1-1e-6)/(1-np.clip(p,1e-6,1-1e-6)));e=b[0]+b[1]*z;return np.where(e>=0,1/(1+np.exp(-e)),np.exp(e)/(1+np.exp(e)))
def boot(x,y,b,c):
 G=[(g[y].to_numpy(int),g[b].to_numpy(float),g[c].to_numpy(float)) for _,g in x.groupby("trading_day",sort=True)];r=np.random.default_rng(SEED);d=np.empty(REPS)
 for i in range(REPS):
  k=r.integers(0,len(G),len(G));Y=np.concatenate([G[j][0] for j in k]);B=np.concatenate([G[j][1] for j in k]);C=np.concatenate([G[j][2] for j in k]);d[i]=auc(Y,C)-auc(Y,B)
 return float(np.quantile(d,.025))
def run(inp,out):
 base=loadmod("/risk_public_input_adapter.py")
 with tempfile.TemporaryDirectory() as td:
  tmp=Path(td)/"phase1";base.run(inp,tmp);st=tmp/"state_rows.parquet";co=tmp/"cohort_rows.parquet"
  if sha(st)!=PSTATE or sha(co)!=PCOH:raise RuntimeError("parent output drift")
  x=pd.read_parquet(co);out.mkdir(parents=True,exist_ok=False);st.replace(out/"state_rows.parquet");co.replace(out/"cohort_rows.parquet")
 R={};F={}
 for h in HS:
  y=f"normal_within_{h}m";b=f"p_B_{h}m";c=f"p_C_{h}m";D=x[x.year.isin(DEV)&x[y].notna()].copy();A=x[x.year.isin(AUD)&x[y].notna()].copy();raw=gain(D,y,b,c);lo=boot(D,y,b,c);Y={str(v):gain(D[D.year.eq(v)],y,b,c) for v in DEV};S={s:gain(D[D.symbol.eq(s)],y,b,c) for s in SYM};AY={str(v):gain(A[A.year.eq(v)],y,b,c) for v in AUD};AS={s:gain(A[A.symbol.eq(s)],y,b,c) for s in SYM};ar=gain(A,y,b,c)
  parts=[];cal={}
  for v in DEV:
   tr=D[D.year.ne(v)];te=D[D.year.eq(v)].copy();fb=fitcal(tr[b].to_numpy(),tr[y].to_numpy(int));fc=fitcal(tr[c].to_numpy(),tr[y].to_numpy(int));te["cb"]=apply(fb,te[b]);te["cc"]=apply(fc,te[c]);cal[str(v)]={"B":fb.tolist(),"C":fc.tolist()};parts.append(te)
  Z=pd.concat(parts);cg=gain(Z,y,"cb","cc");fb=fitcal(D[b].to_numpy(),D[y].to_numpy(int));fc=fitcal(D[c].to_numpy(),D[y].to_numpy(int));A["cb"]=apply(fb,A[b]);A["cc"]=apply(fc,A[c]);ca=gain(A,y,"cb","cc");CAY={str(v):gain(A[A.year.eq(v)],y,"cb","cc") for v in AUD};CAS={s:gain(A[A.symbol.eq(s)],y,"cb","cc") for s in SYM}
  og=[raw["auroc_gain"]>0,lo>0,sum(Y[str(v)]["auroc_gain"]>=0 for v in DEV)>=2,all(S[s]["auroc_gain"]>=0 for s in SYM),ar["auroc_gain"]>=0,all(AY[str(v)]["auroc_gain"]>=0 for v in AUD),all(AS[s]["auroc_gain"]>=0 for s in SYM)];oo=all(og)
  pg=[oo,cg["brier_gain"]>0,cg["logloss_gain"]>0,sum(gain(Z[Z.year.eq(v)],y,"cb","cc")["brier_gain"]>=0 and gain(Z[Z.year.eq(v)],y,"cb","cc")["logloss_gain"]>=0 for v in DEV)>=2,ca["brier_gain"]>=0,ca["logloss_gain"]>=0,all(CAY[str(v)]["brier_gain"]>=0 and CAY[str(v)]["logloss_gain"]>=0 for v in AUD),all(CAS[s]["brier_gain"]>=0 and CAS[s]["logloss_gain"]>=0 for s in SYM)];po=all(pg);status="ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS" if oo and po else ("ORDERING_ONLY_CALIBRATION_NOT_SUPPORTED" if oo else "NOT_SUPPORTED")
  R[h]={"status":status,"raw_dev":raw,"bootstrap_lower":lo,"raw_dev_year":Y,"raw_dev_symbol":S,"raw_audit":ar,"raw_audit_year":AY,"raw_audit_symbol":AS,"cal_dev":cg,"cal_audit":ca,"cal_audit_year":CAY,"cal_audit_symbol":CAS,"ordering_gates":og,"calibration_gates":pg};F[h]={"development_loyo":cal,"audit":{"B":fb.tolist(),"C":fc.tolist()}}
 E=[h for h in HS if R[h]["status"]=="ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS"];V="ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS" if E else ("ORDERING_ONLY_CALIBRATION_NOT_SUPPORTED" if any(R[h]["status"]=="ORDERING_ONLY_CALIBRATION_NOT_SUPPORTED" for h in HS) else "NOT_SUPPORTED")
 pd.DataFrame([{"horizon_minutes":h,"status":R[h]["status"],"dev_auroc_gain":R[h]["raw_dev"]["auroc_gain"],"dev_bootstrap_lower":R[h]["bootstrap_lower"],"dev_cal_brier_gain":R[h]["cal_dev"]["brier_gain"],"dev_cal_logloss_gain":R[h]["cal_dev"]["logloss_gain"],"audit_auroc_gain":R[h]["raw_audit"]["auroc_gain"],"audit_cal_brier_gain":R[h]["cal_audit"]["brier_gain"],"audit_cal_logloss_gain":R[h]["cal_audit"]["logloss_gain"]} for h in HS]).to_csv(out/"HORIZON_METRICS.csv",index=False)
 (out/"SUPPORT_AUDIT.csv").write_text("horizon_minutes,supported_horizon\n15,True\n30,True\n");(out/"CALIBRATION_FREEZE.json").write_text(json.dumps({"method":"Platt","slope_ridge_lambda":LAM,"fits":F,"year_2026_read":False},indent=2,sort_keys=True)+"\n");(out/"INPUT_DATA_RECEIPT.json").write_text(json.dumps({"parent_state_sha256":PSTATE,"parent_cohort_sha256":PCOH,"year_2026_read":False},indent=2)+"\n");(out/"FRESH_OOS_GATE.json").write_text(json.dumps({"year":2026,"unlocked":bool(E),"eligible_horizons_minutes":E,"year_2026_read":False},indent=2)+"\n");(out/"SUMMARY.json").write_text(json.dumps({"phase1b_overall_verdict":V,"horizons":R,"fresh_oos_unlocked":bool(E),"eligible_fresh_oos_horizons_minutes":E,"year_2026_read":False,"production_authority":False},indent=2,sort_keys=True)+"\n")
def main():
 p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args();run(a.inputs.resolve(),a.out.resolve())
if __name__=="__main__":main()
