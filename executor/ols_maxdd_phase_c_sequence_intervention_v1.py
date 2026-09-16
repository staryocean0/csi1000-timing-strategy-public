from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import ols_drawdown_d0_session_adapter as adapter
import ols_maxdd_sequence_hazard_v1 as seq

d0 = adapter.d0
d0._load_5m = adapter._load_5m_by_verified_order

EXIT_MODES = d0.EXIT_MODES
PE_TRIGGER = 0.30
VARIANTS = (
    "direction_flip__half_next_segment",
    "direction_flip__block_next_segment",
    "pe_collapse_ge_0p30__half_next_segment",
    "pe_collapse_ge_0p30__block_next_segment",
    "both__half_next_segment",
    "both__block_next_segment",
    "either__half_next_segment",
    "either__block_next_segment",
    "either__block_until_baseline_recovery",
)


def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    return pd.to_numeric(frame[column], errors="coerce").to_numpy(float)


def _equity(returns: np.ndarray) -> np.ndarray:
    return np.cumprod(1.0 + np.asarray(returns, dtype=float))


def _total_return(returns: np.ndarray) -> float:
    eq = _equity(returns)
    return float(eq[-1] - 1.0) if len(eq) else 0.0


def _maxdd(returns: np.ndarray) -> float:
    eq = _equity(returns)
    if len(eq) == 0:
        return 0.0
    peak = np.maximum.accumulate(np.maximum(eq, 1.0))
    dd = eq / peak - 1.0
    return float(np.min(dd))


def _episode_depths(returns: np.ndarray) -> list[float]:
    eq = _equity(returns)
    out: list[float] = []
    for ep in seq._episodes(eq):
        s = int(ep["start"]); e = int(ep["end"]); h = float(ep["hwm"])
        if s <= e:
            out.append(float(max(0.0, 1.0 - float(np.min(eq[s : e + 1])) / h)))
    return out


def _worst20_mean_depth(returns: np.ndarray) -> float:
    depths = sorted(_episode_depths(returns), reverse=True)
    if not depths:
        return 0.0
    return float(np.mean(depths[: min(20, len(depths))]))


def _variant_parts(name: str) -> tuple[str, str]:
    trigger, action = name.split("__", 1)
    return trigger, action


def _trigger(row: dict[str, object], trigger: str) -> bool:
    flip = float(row["seq_direction_flip"]) >= 0.5
    pe = float(row["seq_pe_collapse_burden"]) >= PE_TRIGGER
    if trigger == "direction_flip": return flip
    if trigger == "pe_collapse_ge_0p30": return pe
    if trigger == "both": return flip and pe
    if trigger == "either": return flip or pe
    raise ValueError(trigger)


def _segment_return(returns: np.ndarray, start: int, end: int) -> float:
    if start > end:
        return 0.0
    return float(np.prod(1.0 + returns[start : end + 1]) - 1.0)


def _build_mode(mode: str, bars: pd.DataFrame, upf, downf) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, list[tuple[int,int]], list[dict[str,object]], list[dict[str,object]]]:
    strategy = d0._strategy(bars, upf, downf, mode)
    trace = d0._trace(bars, strategy, upf, downf)
    returns = _numeric(trace, "strategy_return")
    position = pd.to_numeric(trace["executable_position"], errors="coerce").fillna(0).to_numpy(int)
    eq = _equity(returns)
    segments = seq._segments(position)
    episodes = seq._episodes(eq)
    audits: list[dict[str,object]] = []
    ts_to_i = {pd.Timestamp(v).isoformat(): i for i, v in enumerate(trace["timestamp"])}
    seg_by_start = {s:(s,e) for s,e in segments}
    for ep in episodes:
        row = seq._checkpoint_for_episode(mode, trace, returns, position, segments, ep, 2)
        if row is None or not bool(ep["recovered"]):
            continue
        start = int(ts_to_i[str(row["next_segment_entry_timestamp"])])
        if start not in seg_by_start:
            raise RuntimeError("phase_c_next_segment_identity_failed")
        s,e = seg_by_start[start]
        audit = {
            "exit_mode": mode,
            "episode_id": int(ep["episode_id"]),
            "checkpoint_timestamp": str(row["checkpoint_decision_timestamp"]),
            "next_segment_start_i": int(s),
            "next_segment_end_i": int(e),
            "baseline_episode_end_i": int(ep["end"]),
            "seq_pe_collapse_burden": float(row["seq_pe_collapse_burden"]),
            "seq_direction_flip": float(row["seq_direction_flip"]),
            "direction_flip_trigger": bool(float(row["seq_direction_flip"]) >= 0.5),
            "pe_collapse_ge_0p30_trigger": bool(float(row["seq_pe_collapse_burden"]) >= PE_TRIGGER),
            "both_trigger": bool(float(row["seq_direction_flip"]) >= 0.5 and float(row["seq_pe_collapse_burden"]) >= PE_TRIGGER),
            "either_trigger": bool(float(row["seq_direction_flip"]) >= 0.5 or float(row["seq_pe_collapse_burden"]) >= PE_TRIGGER),
            "next_segment_baseline_return": _segment_return(returns, s, e),
            "checkpoint_year": int(pd.Timestamp(row["checkpoint_decision_timestamp"]).year),
        }
        audits.append(audit)
    return trace, returns, position, segments, episodes, audits


def _apply_variant(returns: np.ndarray, position: np.ndarray, audits: list[dict[str,object]], variant: str) -> tuple[np.ndarray, np.ndarray, list[float], int]:
    trigger, action = _variant_parts(variant)
    multiplier = np.ones(len(returns), dtype=float)
    affected_returns: list[float] = []
    affected_checkpoints = 0
    trigger_key = trigger + "_trigger"
    for row in audits:
        if not bool(row[trigger_key]):
            continue
        affected_checkpoints += 1
        s = int(row["next_segment_start_i"]); e = int(row["next_segment_end_i"])
        if action == "half_next_segment":
            multiplier[s:e+1] = np.minimum(multiplier[s:e+1], 0.5)
            affected_returns.append(float(row["next_segment_baseline_return"]))
        elif action == "block_next_segment":
            multiplier[s:e+1] = 0.0
            affected_returns.append(float(row["next_segment_baseline_return"]))
        elif action == "block_until_baseline_recovery":
            end = int(row["baseline_episode_end_i"])
            multiplier[s:end+1] = 0.0
            affected_returns.append(_segment_return(returns, s, end))
        else:
            raise ValueError(action)
    intervention = np.asarray(returns, dtype=float) * multiplier
    exposure = np.abs(position).astype(float) * multiplier
    return intervention, exposure, affected_returns, affected_checkpoints


def _annual_rows(mode: str, variant: str, timestamps: pd.Series, baseline: np.ndarray, intervention: np.ndarray) -> list[dict[str,object]]:
    years = pd.to_datetime(timestamps).dt.year.to_numpy(int)
    out=[]
    for year in d0.YEARS:
        mask = years == int(year)
        if not np.any(mask): continue
        b = baseline[mask]; v = intervention[mask]
        out.append({"exit_mode":mode,"variant":variant,"year":int(year),"baseline_return_gross":_total_return(b),"intervention_return_gross":_total_return(v),"baseline_maxdd":_maxdd(b),"intervention_maxdd":_maxdd(v)})
    return out


def run(inputs: Path, out: Path) -> None:
    raw5, data_receipt = d0._load_5m(inputs)
    bars = d0._to_15m(raw5); upf=d0._features(bars,"up"); downf=d0._features(bars,"down")
    summary=[]; annual=[]; audits_all=[]
    for mode in EXIT_MODES:
        trace, baseline, position, segments, episodes, audits = _build_mode(mode,bars,upf,downf)
        for row in audits: audits_all.append(row)
        b_ret=_total_return(baseline); b_dd=_maxdd(baseline); b_tail=_worst20_mean_depth(baseline); b_exp=float(np.abs(position).sum())
        for variant in VARIANTS:
            intervention, exposure, affected_returns, affected_checkpoints = _apply_variant(baseline,position,audits,variant)
            v_ret=_total_return(intervention); v_dd=_maxdd(intervention); v_tail=_worst20_mean_depth(intervention); v_exp=float(exposure.sum())
            retention = None if b_ret <= 0 else float(v_ret / b_ret)
            dd_improve = 0.0 if abs(b_dd) < 1e-15 else float((abs(b_dd)-abs(v_dd))/abs(b_dd))
            tail_improve = 0.0 if b_tail < 1e-15 else float((b_tail-v_tail)/b_tail)
            positive_fraction = None if not affected_returns else float(np.mean(np.asarray(affected_returns)>0))
            median_affected = None if not affected_returns else float(np.median(affected_returns))
            summary.append({"exit_mode":mode,"variant":variant,"baseline_return_gross":b_ret,"intervention_return_gross":v_ret,"return_retention":retention,"baseline_maxdd":b_dd,"intervention_maxdd":v_dd,"maxdd_relative_depth_improvement":dd_improve,"baseline_worst20_mean_depth":b_tail,"intervention_worst20_mean_depth":v_tail,"worst20_relative_depth_improvement":tail_improve,"baseline_exposure_equivalent_bars":b_exp,"intervention_exposure_equivalent_bars":v_exp,"exposure_reduction_fraction":0.0 if b_exp==0 else float((b_exp-v_exp)/b_exp),"affected_checkpoints":int(affected_checkpoints),"affected_return_positive_fraction":positive_fraction,"median_affected_baseline_return":median_affected})
            annual.extend(_annual_rows(mode,variant,trace["timestamp"],baseline,intervention))
    summary_df=pd.DataFrame(summary); annual_df=pd.DataFrame(annual); audit_df=pd.DataFrame(audits_all)
    decisions=[]
    for variant in VARIANTS:
        z=summary_df[summary_df.variant==variant]
        dd_pass=int((z.maxdd_relative_depth_improvement>=0.20).sum())
        tail_pass=int((z.worst20_relative_depth_improvement>=0.10).sum())
        ret_pass=int((z.return_retention>=0.80).sum())
        worsening_guard=bool((z.maxdd_relative_depth_improvement>=-0.05).all())
        f=z[z.exit_mode=="frozen_midline_break"].iloc[0]
        frozen_guard=bool(float(f.maxdd_relative_depth_improvement)>=0.20 and float(f.return_retention)>=0.70)
        eligible=bool(dd_pass>=3 and tail_pass>=3 and ret_pass>=4 and worsening_guard and frozen_guard)
        decisions.append({"variant":variant,"maxdd_gate_modes_passed":dd_pass,"tail_gate_modes_passed":tail_pass,"return_retention_modes_passed":ret_pass,"worsening_guard_passed":worsening_guard,"frozen_midline_guard_passed":frozen_guard,"median_maxdd_improvement":float(z.maxdd_relative_depth_improvement.median()),"median_tail_improvement":float(z.worst20_relative_depth_improvement.median()),"median_return_retention":float(z.return_retention.median()),"status":"PHASE_D_RETURN_RECOVERY_ELIGIBLE" if eligible else "NOT_PHASE_D_ELIGIBLE"})
    eligible=[d for d in decisions if d["status"]=="PHASE_D_RETURN_RECOVERY_ELIGIBLE"]
    ordered=sorted(eligible,key=lambda d:(d["median_maxdd_improvement"],d["median_tail_improvement"],d["median_return_retention"]),reverse=True)
    out.mkdir(parents=True,exist_ok=True)
    summary_df.to_csv(out/"variant_summary.csv",index=False); annual_df.to_csv(out/"annual_summary.csv",index=False); audit_df.to_csv(out/"trigger_audit.csv",index=False)
    results={"schema_id":"ols_maxdd_phase_c_sequence_intervention_v1@1.0","status":"PHASE_C_INTERVENTION_COMPARISON_COMPLETED","symbol":d0.SYMBOL,"years":list(d0.YEARS),"exit_modes":list(EXIT_MODES),"variants":list(VARIANTS),"pe_collapse_trigger":PE_TRIGGER,"variant_decisions":decisions,"eligible_variants":[d["variant"] for d in ordered],"phase_d_authority":bool(ordered),"research_order":[d["variant"] for d in ordered],"data_receipt":data_receipt,"optimization_performed":False,"parameter_search_performed":False,"transaction_costs_included":False,"fresh_oos_claimed":False,"baseline_entry_rule_changed":False,"baseline_exit_rule_changed":False,"routing_changed":False,"leverage_changed":False,"production_authority":False}
    (out/"RESULTS.json").write_text(json.dumps(results,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (out/"RESULTS.md").write_text("# OLS MaxDD Phase C sequence intervention v1\n\nStatus: **%s**\n\nEligible variants: `%s`\n\nPhase-D authority: **%s**\n\nGross research comparison only; no production authority.\n"%(results["status"],results["eligible_variants"],results["phase_d_authority"]),encoding="utf-8")


def main():
    p=argparse.ArgumentParser(); p.add_argument("--inputs",required=True); p.add_argument("--out",required=True); a=p.parse_args(); run(Path(a.inputs),Path(a.out))

if __name__=="__main__": main()
