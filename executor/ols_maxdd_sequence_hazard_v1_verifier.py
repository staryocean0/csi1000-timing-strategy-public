from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

EXIT_MODES = ("qualification_reset","first_opposite_close","two_opposite_closes","prior_extreme_break","frozen_midline_break")
CANDIDATES = ("seq_loss_burden","seq_mae_burden","seq_r2_collapse_burden","seq_pe_collapse_burden","seq_loss_acceleration","seq_r2_collapse_acceleration","seq_pe_collapse_acceleration","seq_participation_density","seq_direction_flip")
TAIL_FRACTION=0.20; MIN_FAMILY_ROWS=20; MIN_FAMILY_YEAR_ROWS=8; MIN_SENSITIVITY_ROWS=15; MIN_RHO=0.25; MIN_RHO_MODES=3; MIN_POSITIVE_MODES=4; MIN_MEDIAN_AUC=0.60; MIN_YEAR_POSITIVE_FRACTION=0.70; MIN_SENSITIVITY_POSITIVE_MODES=4


def _spearman(x: pd.Series, y: pd.Series, minimum: int):
    z=pd.DataFrame({"x":pd.to_numeric(x,errors="coerce"),"y":pd.to_numeric(y,errors="coerce")}).dropna()
    if len(z)<minimum or z.x.nunique()<2 or z.y.nunique()<2: return None,len(z)
    v=z.x.rank(method="average").corr(z.y.rank(method="average")); return (None if pd.isna(v) else float(v)),len(z)


def _auc(x: pd.Series, label: pd.Series, minimum: int):
    z=pd.DataFrame({"x":pd.to_numeric(x,errors="coerce"),"label":label.astype(bool)}).dropna()
    if len(z)<minimum or z.x.nunique()<2: return None,len(z)
    p=int(z.label.sum()); n=len(z)-p
    if p==0 or n==0: return None,len(z)
    r=z.x.rank(method="average"); return float((r[z.label].sum()-p*(p+1)/2)/(p*n)),len(z)


def _close(a,b,tol=1e-12):
    if a is None or (isinstance(a,float) and math.isnan(a)): return b is None or (isinstance(b,float) and math.isnan(b))
    if b is None or (isinstance(b,float) and math.isnan(b)): return False
    return abs(float(a)-float(b))<=tol


def _tail(frame: pd.DataFrame) -> pd.Series:
    result=pd.Series(False,index=frame.index)
    for mode in EXIT_MODES:
        for k in (2,3):
            idx=frame.index[(frame.exit_mode==mode)&(frame.sequence_length==k)&frame.recovered_episode.astype(bool)]
            if len(idx)==0: continue
            n=max(1,int(math.ceil(len(idx)*TAIL_FRACTION)))
            ranks=frame.loc[idx,"remaining_episode_drawdown_extension"].rank(method="first",ascending=False)
            result.loc[idx]=ranks.le(n).to_numpy(bool)
    return result


def verify(results_dir: Path) -> dict:
    required=("episode_checkpoint_table.csv","candidate_summary.csv","year_stability.csv","seq3_sensitivity.csv","RESULTS.json","RESULTS.md")
    for name in required:
        p=results_dir/name
        if not p.is_file() or p.is_symlink(): raise RuntimeError("ols_maxdd_sequence_missing_result_"+name)
    frame=pd.read_csv(results_dir/"episode_checkpoint_table.csv")
    family=pd.read_csv(results_dir/"candidate_summary.csv")
    years=pd.read_csv(results_dir/"year_stability.csv")
    seq3=pd.read_csv(results_dir/"seq3_sensitivity.csv")
    results=json.loads((results_dir/"RESULTS.json").read_text(encoding="utf-8"))
    if frame.empty or set(pd.to_numeric(frame.sequence_length,errors="raise").astype(int).unique())- {2,3}: raise RuntimeError("ols_maxdd_sequence_bad_sequence_lengths")
    if frame.duplicated(["exit_mode","episode_id","sequence_length"]).any(): raise RuntimeError("ols_maxdd_sequence_duplicate_episode_checkpoint")
    if not frame["causal_checkpoint_verified"].astype(bool).all(): raise RuntimeError("ols_maxdd_sequence_noncausal_checkpoint")
    calc_tail=_tail(frame)
    if not np.array_equal(calc_tail.to_numpy(bool),frame["tail_extension_label"].astype(bool).to_numpy()): raise RuntimeError("ols_maxdd_sequence_tail_label_mismatch")
    primary=frame[(frame.sequence_length==2)&frame.recovered_episode.astype(bool)].copy(); sensitivity=frame[(frame.sequence_length==3)&frame.recovered_episode.astype(bool)].copy()
    decisions=[]
    for candidate in CANDIDATES:
        rhos=[]; aucs=[]; year_rhos=[]; s3_rhos=[]
        for mode in EXIT_MODES:
            z=primary[primary.exit_mode==mode]; rho,n=_spearman(z[candidate],z.remaining_episode_drawdown_extension,MIN_FAMILY_ROWS); auc,an=_auc(z[candidate],z.tail_extension_label,MIN_FAMILY_ROWS)
            got=family[(family.candidate==candidate)&(family.exit_mode==mode)]
            if len(got)!=1: raise RuntimeError("ols_maxdd_sequence_family_row_mismatch")
            g=got.iloc[0]
            if int(g.primary_episode_n)!=n or int(g.primary_auc_n)!=an or not _close(g.primary_rho,rho) or not _close(g.primary_auc,auc): raise RuntimeError("ols_maxdd_sequence_family_value_mismatch")
            if rho is not None: rhos.append(rho)
            if auc is not None: aucs.append(auc)
            for year in (2020,2021,2022,2023,2024,2025):
                zy=z[z.checkpoint_year==year]; ry,ny=_spearman(zy[candidate],zy.remaining_episode_drawdown_extension,MIN_FAMILY_YEAR_ROWS)
                goty=years[(years.candidate==candidate)&(years.exit_mode==mode)&(years.year==year)]
                if len(goty)!=1 or int(goty.iloc[0].n)!=ny or not _close(goty.iloc[0].rho,ry): raise RuntimeError("ols_maxdd_sequence_year_value_mismatch")
                if ry is not None: year_rhos.append(ry)
            s=sensitivity[sensitivity.exit_mode==mode]; r3,n3=_spearman(s[candidate],s.remaining_episode_drawdown_extension,MIN_SENSITIVITY_ROWS)
            g3=seq3[(seq3.candidate==candidate)&(seq3.exit_mode==mode)]
            if len(g3)!=1 or int(g3.iloc[0].n)!=n3 or not _close(g3.iloc[0].rho,r3): raise RuntimeError("ols_maxdd_sequence_seq3_value_mismatch")
            if r3 is not None: s3_rhos.append(r3)
        pass_modes=sum(v>=MIN_RHO for v in rhos); positive=sum(v>0 for v in rhos); median_auc=None if not aucs else float(np.median(aucs)); year_pos=None if not year_rhos else float(np.mean(np.asarray(year_rhos)>0)); s3_pos=sum(v>0 for v in s3_rhos)
        eligible=bool(pass_modes>=MIN_RHO_MODES and positive>=MIN_POSITIVE_MODES and median_auc is not None and median_auc>=MIN_MEDIAN_AUC and year_pos is not None and year_pos>=MIN_YEAR_POSITIVE_FRACTION and s3_pos>=MIN_SENSITIVITY_POSITIVE_MODES)
        decisions.append((candidate,eligible,pass_modes,positive,median_auc,year_pos,s3_pos))
    expected=[c for c,e,*_ in decisions if e]
    if results.get("schema_id")!="ols_maxdd_sequence_hazard_v1@1.0" or results.get("status")!="SEQUENCE_HAZARD_IDENTIFICATION_COMPLETED": raise RuntimeError("ols_maxdd_sequence_result_identity")
    if list(results.get("eligible_candidates",[]))!=expected or bool(results.get("phase_c_reopen_authority"))!=bool(expected): raise RuntimeError("ols_maxdd_sequence_gate_mismatch")
    for key in ("optimization_performed","parameter_search_performed","entry_rule_changed","exit_rule_changed","position_sizing_changed","routing_changed","leverage_changed","fresh_oos_claimed","production_authority"):
        if bool(results.get(key)): raise RuntimeError("ols_maxdd_sequence_forbidden_authority_"+key)
    by={d["candidate"]:d for d in results.get("candidate_decisions",[])}
    for candidate,eligible,pass_modes,positive,median_auc,year_pos,s3_pos in decisions:
        d=by.get(candidate)
        if not d or int(d["rho_pass_modes"])!=pass_modes or int(d["positive_sign_modes"])!=positive or int(d["seq3_positive_sign_modes"])!=s3_pos or not _close(d.get("median_family_auc"),median_auc) or not _close(d.get("family_year_positive_fraction"),year_pos): raise RuntimeError("ols_maxdd_sequence_decision_mismatch")
        if d.get("status")!=("PHASE_C_REOPEN_ELIGIBLE" if eligible else "NOT_PHASE_C_REOPEN_ELIGIBLE"): raise RuntimeError("ols_maxdd_sequence_decision_status_mismatch")
    return {"status":"passed","profile":"ols-maxdd-sequence-hazard-v1","eligible_candidates":expected,"phase_c_reopen_authority":bool(expected)}


def main():
    p=argparse.ArgumentParser(); p.add_argument("--inputs",required=True); p.add_argument("--results",required=True); a=p.parse_args(); print(json.dumps(verify(Path(a.results)),sort_keys=True,separators=(",",":")))

if __name__=="__main__": main()
