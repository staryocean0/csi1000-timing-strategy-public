from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import ols_drawdown_d0_session_adapter as adapter
import ols_maxdd_sequence_hazard_v1 as seq

d0=adapter.d0
d0._load_5m=adapter._load_5m_by_verified_order
EXIT_MODES=d0.EXIT_MODES
PE_TRIGGER=0.30
VARIANTS=("direction_flip__half_next_segment","direction_flip__block_next_segment","pe_collapse_ge_0p30__half_next_segment","pe_collapse_ge_0p30__block_next_segment","both__half_next_segment","both__block_next_segment","either__half_next_segment","either__block_next_segment","either__block_until_baseline_recovery")


def _arr(frame,col): return pd.to_numeric(frame[col],errors="coerce").to_numpy(float)
def _eq(r): return np.cumprod(1.0+np.asarray(r,dtype=float))
def _ret(r):
    e=_eq(r); return float(e[-1]-1.0) if len(e) else 0.0
def _dd(r):
    e=_eq(r)
    if not len(e): return 0.0
    p=np.maximum.accumulate(np.maximum(e,1.0)); return float(np.min(e/p-1.0))
def _depths(r):
    e=_eq(r); out=[]
    for ep in seq._episodes(e):
        s=int(ep["start"]); z=int(ep["end"]); h=float(ep["hwm"])
        if s<=z: out.append(max(0.0,1.0-float(np.min(e[s:z+1]))/h))
    return out
def _tail(r):
    d=sorted(_depths(r),reverse=True); return 0.0 if not d else float(np.mean(d[:min(20,len(d))]))
def _sret(r,s,e): return 0.0 if s>e else float(np.prod(1.0+r[s:e+1])-1.0)
def _close(a,b,tol=1e-11):
    if a is None or (isinstance(a,float) and np.isnan(a)): return b is None or (isinstance(b,float) and np.isnan(b))
    if b is None or (isinstance(b,float) and np.isnan(b)): return False
    return abs(float(a)-float(b))<=tol


def _build(mode,bars,upf,downf):
    strategy=d0._strategy(bars,upf,downf,mode); trace=d0._trace(bars,strategy,upf,downf)
    r=_arr(trace,"strategy_return"); pos=pd.to_numeric(trace.executable_position,errors="coerce").fillna(0).to_numpy(int)
    seg=seq._segments(pos); eps=seq._episodes(_eq(r)); ts={pd.Timestamp(v).isoformat():i for i,v in enumerate(trace.timestamp)}; segmap={s:(s,e) for s,e in seg}; rows=[]
    for ep in eps:
        q=seq._checkpoint_for_episode(mode,trace,r,pos,seg,ep,2)
        if q is None or not bool(ep["recovered"]): continue
        s=int(ts[str(q["next_segment_entry_timestamp"])]); e=int(segmap[s][1]); pe=float(q["seq_pe_collapse_burden"]); flip=float(q["seq_direction_flip"])>=0.5
        rows.append({"episode_id":int(ep["episode_id"]),"s":s,"e":e,"ep_end":int(ep["end"]),"pe":pe,"flip":flip,"next_ret":_sret(r,s,e),"checkpoint_timestamp":str(q["checkpoint_decision_timestamp"])})
    return trace,r,pos,rows


def _fire(row,trigger):
    pe=row["pe"]>=PE_TRIGGER; flip=bool(row["flip"])
    return {"direction_flip":flip,"pe_collapse_ge_0p30":pe,"both":flip and pe,"either":flip or pe}[trigger]


def _variant(r,pos,rows,name):
    trigger,action=name.split("__",1); m=np.ones(len(r),float); affected=[]; n=0
    for q in rows:
        if not _fire(q,trigger): continue
        n+=1; s=q["s"]; e=q["e"]
        if action=="half_next_segment": m[s:e+1]=np.minimum(m[s:e+1],0.5); affected.append(q["next_ret"])
        elif action=="block_next_segment": m[s:e+1]=0.0; affected.append(q["next_ret"])
        elif action=="block_until_baseline_recovery": m[s:q["ep_end"]+1]=0.0; affected.append(_sret(r,s,q["ep_end"]))
        else: raise RuntimeError("phase_c_unknown_action")
    return r*m,np.abs(pos).astype(float)*m,affected,n


def verify(inputs:Path,results:Path):
    required=("RESULTS.json","variant_summary.csv","annual_summary.csv","trigger_audit.csv","RESULTS.md")
    for n in required:
        p=results/n
        if not p.is_file() or p.is_symlink(): raise RuntimeError("phase_c_missing_"+n)
    result=json.loads((results/"RESULTS.json").read_text(encoding="utf-8")); summary=pd.read_csv(results/"variant_summary.csv"); audit=pd.read_csv(results/"trigger_audit.csv")
    raw,_=d0._load_5m(inputs); bars=d0._to_15m(raw); upf=d0._features(bars,"up"); downf=d0._features(bars,"down")
    expected_rows=[]; expected_audits=[]
    for mode in EXIT_MODES:
        trace,r,pos,rows=_build(mode,bars,upf,downf)
        for q in rows:
            expected_audits.append((mode,q["episode_id"],q["checkpoint_timestamp"],q["s"],q["e"],q["ep_end"],q["pe"],float(q["flip"])))
        br=_ret(r); bd=_dd(r); bt=_tail(r); be=float(np.abs(pos).sum())
        for name in VARIANTS:
            v,exp,aff,n=_variant(r,pos,rows,name); vr=_ret(v); vd=_dd(v); vt=_tail(v); ve=float(exp.sum()); rr=None if br<=0 else vr/br; di=0.0 if abs(bd)<1e-15 else (abs(bd)-abs(vd))/abs(bd); ti=0.0 if bt<1e-15 else (bt-vt)/bt
            expected_rows.append((mode,name,br,vr,rr,bd,vd,di,bt,vt,ti,be,ve,0.0 if be==0 else (be-ve)/be,n,None if not aff else float(np.mean(np.asarray(aff)>0)),None if not aff else float(np.median(aff))))
    if len(summary)!=len(expected_rows): raise RuntimeError("phase_c_summary_row_count")
    cols=("baseline_return_gross","intervention_return_gross","return_retention","baseline_maxdd","intervention_maxdd","maxdd_relative_depth_improvement","baseline_worst20_mean_depth","intervention_worst20_mean_depth","worst20_relative_depth_improvement","baseline_exposure_equivalent_bars","intervention_exposure_equivalent_bars","exposure_reduction_fraction","affected_checkpoints","affected_return_positive_fraction","median_affected_baseline_return")
    for er in expected_rows:
        mode,name,*vals=er; got=summary[(summary.exit_mode==mode)&(summary.variant==name)]
        if len(got)!=1: raise RuntimeError("phase_c_summary_identity")
        g=got.iloc[0]
        for c,v in zip(cols,vals):
            if c=="affected_checkpoints":
                if int(g[c])!=int(v): raise RuntimeError("phase_c_summary_value_"+c)
            elif not _close(g[c],v): raise RuntimeError("phase_c_summary_value_"+c)
    if len(audit)!=len(expected_audits): raise RuntimeError("phase_c_audit_count")
    for mode,ep,ts,s,e,ee,pe,flip in expected_audits:
        g=audit[(audit.exit_mode==mode)&(audit.episode_id==ep)]
        if len(g)!=1: raise RuntimeError("phase_c_audit_identity")
        x=g.iloc[0]
        if str(x.checkpoint_timestamp)!=ts or int(x.next_segment_start_i)!=s or int(x.next_segment_end_i)!=e or int(x.baseline_episode_end_i)!=ee or not _close(x.seq_pe_collapse_burden,pe) or bool(x.seq_direction_flip>=0.5)!=bool(flip): raise RuntimeError("phase_c_audit_value")
    decisions=[]
    for name in VARIANTS:
        z=summary[summary.variant==name]; dp=int((z.maxdd_relative_depth_improvement>=0.20).sum()); tp=int((z.worst20_relative_depth_improvement>=0.10).sum()); rp=int((z.return_retention>=0.80).sum()); wg=bool((z.maxdd_relative_depth_improvement>=-0.05).all()); f=z[z.exit_mode=="frozen_midline_break"].iloc[0]; fg=bool(float(f.maxdd_relative_depth_improvement)>=0.20 and float(f.return_retention)>=0.70); ok=bool(dp>=3 and tp>=3 and rp>=4 and wg and fg)
        decisions.append({"variant":name,"maxdd_gate_modes_passed":dp,"tail_gate_modes_passed":tp,"return_retention_modes_passed":rp,"worsening_guard_passed":wg,"frozen_midline_guard_passed":fg,"median_maxdd_improvement":float(z.maxdd_relative_depth_improvement.median()),"median_tail_improvement":float(z.worst20_relative_depth_improvement.median()),"median_return_retention":float(z.return_retention.median()),"status":"PHASE_D_RETURN_RECOVERY_ELIGIBLE" if ok else "NOT_PHASE_D_ELIGIBLE"})
    eligible=[d for d in decisions if d["status"]=="PHASE_D_RETURN_RECOVERY_ELIGIBLE"]; eligible=sorted(eligible,key=lambda d:(d["median_maxdd_improvement"],d["median_tail_improvement"],d["median_return_retention"]),reverse=True); expected=[d["variant"] for d in eligible]
    if result.get("schema_id")!="ols_maxdd_phase_c_sequence_intervention_v1@1.0" or result.get("status")!="PHASE_C_INTERVENTION_COMPARISON_COMPLETED": raise RuntimeError("phase_c_result_identity")
    if list(result.get("eligible_variants",[]))!=expected or bool(result.get("phase_d_authority"))!=bool(expected) or list(result.get("research_order",[]))!=expected: raise RuntimeError("phase_c_gate_mismatch")
    forbidden=("optimization_performed","parameter_search_performed","transaction_costs_included","fresh_oos_claimed","baseline_entry_rule_changed","baseline_exit_rule_changed","routing_changed","leverage_changed","production_authority")
    if any(bool(result.get(k)) for k in forbidden): raise RuntimeError("phase_c_forbidden_authority")
    return {"status":"passed","profile":"ols-maxdd-phase-c-sequence-intervention-v1","eligible_variants":expected,"phase_d_authority":bool(expected)}


def main():
    p=argparse.ArgumentParser(); p.add_argument("--inputs",required=True); p.add_argument("--results",required=True); a=p.parse_args(); print(json.dumps(verify(Path(a.inputs),Path(a.results)),sort_keys=True,separators=(",",":")))

if __name__=="__main__": main()
