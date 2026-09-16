from __future__ import annotations

import numpy as np
import pandas as pd

import ols_maxdd_failure_atlas_v1 as atlas
from ols_maxdd_risk_state_overlap_v1_features import EXIT_MODES, TOP_N, YEARS, d0, _auc, _slice_summary, _episode_window, _lead, _prob_change


def _episode_rows(panel: pd.DataFrame, traces: dict[str, pd.DataFrame]):
    rows = []
    cell_parts = []
    lead_rows = []
    for mode in EXIT_MODES:
        trace = traces[mode]
        episodes = atlas._episodes(pd.to_numeric(trace["strategy_return"], errors="coerce").to_numpy(float))
        base = [atlas._episode_row(mode, trace, i + 1, *e) for i, e in enumerate(episodes)]
        z = pd.DataFrame(base)
        z["depth_rank"] = z["depth_abs"].rank(method="first", ascending=False).astype(int)
        z["top_tail"] = z["depth_rank"].le(TOP_N)
        for _, row in z.iterrows():
            start_ts = pd.Timestamp(row["start_timestamp"])
            trough_ts = pd.Timestamp(row["trough_timestamp"])
            start_ts = start_ts.tz_localize(d0.TZ) if start_ts.tzinfo is None else start_ts.tz_convert(d0.TZ)
            trough_ts = trough_ts.tz_localize(d0.TZ) if trough_ts.tzinfo is None else trough_ts.tz_convert(d0.TZ)
            _, _, episode, pre12, pre48 = _episode_window(panel, start_ts, trough_ts)
            rec = dict(row)
            rec.update(_slice_summary(episode, "episode"))
            rec.update(_slice_summary(pre12, "pre12"))
            rec.update(_slice_summary(pre48, "pre48"))
            rec["R_episode"] = rec.get("episode_risk_occupancy")
            rec["U_episode"] = rec.get("episode_unsafe_occupancy")
            rec["V_episode"] = rec.get("episode_rv_percentile_median")
            rec["M_episode"] = rec.get("episode_morphology_median")
            rec["J_episode"] = rec.get("episode_joint_median")
            rec["risk_transition_lead_bars_pre48"] = _lead(pre48)
            rec["recovery_probability_30m_late_minus_early_pre48"] = _prob_change(pre48)
            rows.append(rec)
            lead_rows.append({
                "exit_mode": mode,
                "episode_id": int(row["episode_id"]),
                "top_tail": bool(row["top_tail"]),
                "start_year": int(row["start_year"]),
                "risk_transition_lead_bars_pre48": rec["risk_transition_lead_bars_pre48"],
                "pre12_risk_occupancy": rec.get("pre12_risk_occupancy"),
                "pre48_risk_occupancy": rec.get("pre48_risk_occupancy"),
                "episode_risk_occupancy": rec.get("episode_risk_occupancy"),
                "pre48_recovery_probability_coverage": rec.get("pre48_recovery_probability_coverage"),
                "episode_recovery_probability_coverage": rec.get("episode_recovery_probability_coverage"),
                "pre48_recovery_probability_median": rec.get("pre48_recovery_probability_median"),
                "episode_recovery_probability_median": rec.get("episode_recovery_probability_median"),
                "recovery_probability_30m_late_minus_early_pre48": rec["recovery_probability_30m_late_minus_early_pre48"],
            })
            cells = episode[["year", "vol_bucket", "pe48_bucket", "rev48_high", "risk_indicator", "unsafe_indicator"]].copy()
            cells["exit_mode"] = mode
            cells["top_tail"] = bool(row["top_tail"])
            cell_parts.append(cells)
    return pd.DataFrame(rows), pd.concat(cell_parts, ignore_index=True), pd.DataFrame(lead_rows)


def _auc_tables(ep: pd.DataFrame):
    family = []
    for mode in EXIT_MODES:
        q = ep[ep["exit_mode"].eq(mode)].copy()
        y = q["top_tail"].astype(int)
        family.append({
            "exit_mode": mode,
            "top_tail_n": int(y.sum()),
            "non_top_n": int(len(y) - y.sum()),
            "auc_R": _auc(y, q["R_episode"]),
            "auc_U": _auc(y, q["U_episode"]),
            "auc_V": _auc(y, q["V_episode"]),
            "auc_M": _auc(y, q["M_episode"]),
            "auc_J": _auc(y, q["J_episode"]),
        })
    years = []
    for year in YEARS:
        q = ep[ep["start_year"].eq(year)].copy()
        y = q["top_tail"].astype(int)
        top = int(y.sum())
        rest = int(len(y) - top)
        evaluable = top >= 2 and rest >= 20
        years.append({
            "year": year,
            "top_tail_n": top,
            "non_top_n": rest,
            "evaluable": evaluable,
            "auc_R": _auc(y, q["R_episode"]) if evaluable else None,
            "auc_U": _auc(y, q["U_episode"]) if evaluable else None,
            "auc_V": _auc(y, q["V_episode"]) if evaluable else None,
            "auc_M": _auc(y, q["M_episode"]) if evaluable else None,
            "auc_J": _auc(y, q["J_episode"]) if evaluable else None,
        })
    return pd.DataFrame(family), pd.DataFrame(years)


def _adjudicate(family: pd.DataFrame, years: pd.DataFrame) -> tuple[str, dict[str, bool | float | int | None]]:
    f = family.copy()
    y = years[years["evaluable"].astype(bool)].copy()
    rvals = pd.to_numeric(f["auc_R"], errors="coerce")
    jr = pd.to_numeric(f["auc_J"], errors="coerce")
    mr = pd.to_numeric(f["auc_M"], errors="coerce")
    yr = pd.to_numeric(y["auc_R"], errors="coerce")
    yj = pd.to_numeric(y["auc_J"], errors="coerce")
    ym = pd.to_numeric(y["auc_M"], errors="coerce")
    family_inc = jr - pd.concat([rvals, mr], axis=1).max(axis=1)
    year_inc = yj - pd.concat([yr, ym], axis=1).max(axis=1) if len(y) else pd.Series(dtype=float)
    support = (
        len(f) == 5
        and bool((f["top_tail_n"] == TOP_N).all())
        and len(y) >= 4
        and rvals.notna().all()
        and jr.notna().all()
        and mr.notna().all()
        and yr.notna().all()
        and yj.notna().all()
        and ym.notna().all()
    )
    checks = {
        "support_all_five_families_top20": bool(len(f) == 5 and (f["top_tail_n"] == TOP_N).all()),
        "support_evaluable_year_count": int(len(y)),
        "support_evaluable_years_ge_4": bool(len(y) >= 4),
        "strong_median_family_auc_R_ge_0_65": bool(rvals.median() >= 0.65),
        "strong_family_auc_R_ge_0_60_count": int((rvals >= 0.60).sum()),
        "strong_family_count_ge_4": bool((rvals >= 0.60).sum() >= 4),
        "strong_year_auc_R_ge_0_60_count": int((yr >= 0.60).sum()),
        "strong_year_count_ge_4": bool((yr >= 0.60).sum() >= 4),
        "strong_no_evaluable_year_auc_R_below_0_45": bool(len(y) >= 4 and not (yr < 0.45).any()),
        "conditional_median_family_auc_J_ge_0_65": bool(jr.median() >= 0.65),
        "conditional_family_auc_J_ge_0_60_count": int((jr >= 0.60).sum()),
        "conditional_family_count_ge_4": bool((jr >= 0.60).sum() >= 4),
        "conditional_median_family_increment_ge_0_05": bool(family_inc.median() >= 0.05),
        "conditional_year_auc_J_ge_0_60_count": int((yj >= 0.60).sum()),
        "conditional_year_count_ge_4": bool((yj >= 0.60).sum() >= 4),
        "conditional_median_year_increment_ge_0_03": bool(len(y) >= 4 and year_inc.median() >= 0.03),
    }
    strong = support and all(checks[k] for k in (
        "strong_median_family_auc_R_ge_0_65",
        "strong_family_count_ge_4",
        "strong_year_count_ge_4",
        "strong_no_evaluable_year_auc_R_below_0_45",
    ))
    conditional = support and (not strong) and all(checks[k] for k in (
        "conditional_median_family_auc_J_ge_0_65",
        "conditional_family_count_ge_4",
        "conditional_median_family_increment_ge_0_05",
        "conditional_year_count_ge_4",
        "conditional_median_year_increment_ge_0_03",
    ))
    checks["strong_pass"] = bool(strong)
    checks["conditional_pass"] = bool(conditional)
    if not support:
        return "INSUFFICIENT_SUPPORT", checks
    if strong:
        return "STRONG", checks
    if conditional:
        return "CONDITIONAL", checks
    return "WEAK", checks


def _cell_table(cells: pd.DataFrame) -> pd.DataFrame:
    keys = ["exit_mode", "top_tail", "year", "vol_bucket", "pe48_bucket", "rev48_high"]
    g = cells.groupby(keys, dropna=False).agg(
        bars=("risk_indicator", "size"),
        risk_occupancy=("risk_indicator", "mean"),
        unsafe_occupancy=("unsafe_indicator", "mean"),
    ).reset_index()
    total = g.groupby(["exit_mode", "top_tail", "year"], sort=False)["bars"].transform("sum")
    g["share"] = g["bars"] / total
    return g


def _prob_summary(ep: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for mode in EXIT_MODES:
        for top in (False, True):
            q = ep[ep["exit_mode"].eq(mode) & ep["top_tail"].eq(top)]
            for window in ("pre48", "episode"):
                rows.append({
                    "exit_mode": mode,
                    "top_tail": top,
                    "window": window,
                    "episodes": int(len(q)),
                    "mean_bar_coverage": float(pd.to_numeric(q[f"{window}_recovery_probability_coverage"], errors="coerce").mean()),
                    "median_probability_across_episode_medians": float(pd.to_numeric(q[f"{window}_recovery_probability_median"], errors="coerce").median()),
                })
    return pd.DataFrame(rows)


def _control_summary(ep: pd.DataFrame, panel: pd.DataFrame, traces: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for mode in EXIT_MODES:
        q = ep[ep["exit_mode"].eq(mode)]
        for label, top in (("TOP_TAIL_DD", True), ("NON_TOP_DD", False)):
            s = q[q["top_tail"].eq(top)]
            rows.append({
                "exit_mode": mode,
                "control": label,
                "units": int(len(s)),
                "risk_occupancy": float(pd.to_numeric(s["R_episode"], errors="coerce").mean()),
                "unsafe_occupancy": float(pd.to_numeric(s["U_episode"], errors="coerce").mean()),
                "rv_percentile_median": float(pd.to_numeric(s["V_episode"], errors="coerce").median()),
                "morphology_median": float(pd.to_numeric(s["M_episode"], errors="coerce").median()),
            })
        trace = traces[mode].copy()
        trace["pos"] = pd.to_numeric(trace["executable_position"], errors="coerce").fillna(0).astype(int)
        trace["ret"] = pd.to_numeric(trace["strategy_return"], errors="coerce").fillna(0.0)
        top_15 = np.zeros(len(trace), dtype=bool)
        for erow in q[q["top_tail"]].itertuples():
            st = pd.Timestamp(erow.start_timestamp)
            tr = pd.Timestamp(erow.trough_timestamp)
            st = st.tz_localize(d0.TZ) if st.tzinfo is None else st.tz_convert(d0.TZ)
            tr = tr.tz_localize(d0.TZ) if tr.tzinfo is None else tr.tz_convert(d0.TZ)
            top_15 |= trace["timestamp"].between(st, tr).to_numpy()
        mapping = pd.DataFrame({"ols_timestamp": trace["timestamp"], "pos": trace["pos"], "top": top_15})
        p = panel.merge(mapping, on="ols_timestamp", how="left", validate="many_to_one")
        top_mask = p["top"].fillna(False).astype(bool)
        flat = p[p["pos"].eq(0) & ~top_mask]
        rows.append({
            "exit_mode": mode,
            "control": "FLAT_MARKET",
            "units": int(len(flat)),
            "risk_occupancy": float(flat["risk_indicator"].mean()),
            "unsafe_occupancy": float(flat["unsafe_indicator"].mean()),
            "rv_percentile_median": float(flat["rv12_rms_percentile"].median()),
            "morphology_median": float(flat["morphology_score"].median()),
        })
        seg_id = np.zeros(len(trace), dtype=int)
        sid = 0
        for i in range(len(trace)):
            if trace.at[i, "pos"] == 0:
                continue
            if i == 0 or trace.at[i - 1, "pos"] == 0 or trace.at[i - 1, "pos"] != trace.at[i, "pos"]:
                sid += 1
            seg_id[i] = sid
        pieces = []
        for s in sorted(set(seg_id) - {0}):
            idx = np.flatnonzero(seg_id == s)
            if top_15[idx].any():
                continue
            cumulative = float(np.prod(1.0 + trace.iloc[idx]["ret"].to_numpy(float)) - 1.0)
            if cumulative <= 0:
                continue
            stamps = set(trace.iloc[idx]["timestamp"].tolist())
            pieces.append(panel[panel["ols_timestamp"].isin(stamps)])
        positive = pd.concat(pieces, ignore_index=True) if pieces else panel.iloc[0:0]
        rows.append({
            "exit_mode": mode,
            "control": "PROFITABLE_POSITION_SEGMENT",
            "units": int(len(pieces)),
            "risk_occupancy": None if positive.empty else float(positive["risk_indicator"].mean()),
            "unsafe_occupancy": None if positive.empty else float(positive["unsafe_indicator"].mean()),
            "rv_percentile_median": None if positive.empty else float(positive["rv12_rms_percentile"].median()),
            "morphology_median": None if positive.empty else float(positive["morphology_score"].median()),
        })
    return pd.DataFrame(rows)
