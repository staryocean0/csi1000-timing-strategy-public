from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import ols_drawdown_d0_session_adapter as adapter
import ols_maxdd_failure_atlas_v1 as atlas

d0 = adapter.d0
d0._load_5m = adapter._load_5m_by_verified_order

EXIT_MODES = d0.EXIT_MODES
TOP_N = 20
YEARS = d0.YEARS
SYMBOL = d0.SYMBOL
WINDOWS = (12, 24, 48)
Q1 = 1.0 / 3.0
Q2 = 2.0 / 3.0
RISK_SOURCE_BLOB = "7a9f238442f5a4836c6f38dcafec4bc34526fc5c"
MODEL_SHA256 = "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551"
CAL_SHA256 = "74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909"


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _load_risk_base(inputs: Path):
    path = inputs / "phase1_run_study.py"
    raw = path.read_bytes()
    if _git_blob(raw) != RISK_SOURCE_BLOB:
        raise RuntimeError("ols_risk_overlap_risk_source_identity")
    spec = importlib.util.spec_from_file_location("ols_risk_overlap_phase1", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("ols_risk_overlap_risk_source_unloadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SYMBOLS = (SYMBOL,)
    module.YEARS = YEARS
    module.DEV_YEARS = YEARS
    module.AUDIT_YEARS = ()
    module.HORIZONS = (15, 30)
    return module


def _platt(beta, p):
    q = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    x = np.log(q / (1 - q))
    eta = np.clip(float(beta[0]) + float(beta[1]) * x, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-eta))


def _risk_rows(inputs: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    if _sha256(inputs / "MODEL_FREEZE.json") != MODEL_SHA256:
        raise RuntimeError("ols_risk_overlap_model_freeze_identity")
    if _sha256(inputs / "CALIBRATION_FREEZE.json") != CAL_SHA256:
        raise RuntimeError("ols_risk_overlap_calibration_freeze_identity")
    base = _load_risk_base(inputs)
    frames = {(SYMBOL, y): pd.read_parquet(inputs / f"{y}.parquet") for y in YEARS}
    states = base.build_state_rows(frames)
    cohort = base.build_primary_cohort(states)
    freeze = json.loads((inputs / "MODEL_FREEZE.json").read_text(encoding="utf-8"))
    cal = json.loads((inputs / "CALIBRATION_FREEZE.json").read_text(encoding="utf-8"))
    model = freeze.get("models", {}).get("30", {}).get("C")
    beta = cal.get("fits", {}).get("30", {}).get("repeat_audit", {}).get("C")
    if not isinstance(model, dict) or not isinstance(beta, list) or len(beta) != 2:
        raise RuntimeError("ols_risk_overlap_30m_probability_freeze_missing")
    cohort = cohort.copy()
    cohort["recovery_probability_30m"] = _platt(beta, base.predict(model, cohort))
    return states, cohort


def _rolling_reversal(x: np.ndarray) -> float:
    z = np.asarray(x, float)
    z = z[np.isfinite(z) & (z != 0.0)]
    if len(z) < 2:
        return np.nan
    return float(np.mean(z[1:] * z[:-1] < 0.0))


def _pct_by_year(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame.groupby("year", sort=False)[column].rank(method="average", pct=True)


def _market_panel(raw5: pd.DataFrame, states: pd.DataFrame, cohort: pd.DataFrame) -> pd.DataFrame:
    z = raw5.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    z["year"] = pd.to_datetime(z["trading_day"]).dt.year.astype(int)
    z["bar_end"] = z["timestamp"].dt.tz_convert(d0.TZ).dt.tz_localize(None)
    z["ret_5m"] = z.groupby("trading_day", sort=False)["close"].transform(lambda s: np.log(s).diff())
    z["abs_ret_5m"] = z["ret_5m"].abs()
    z["intrabar_log_range"] = np.log(z["high"] / z["low"])
    prev = z.groupby("trading_day", sort=False)["close"].shift(1)
    base = np.maximum(z["high"] - z["low"], np.maximum((z["high"] - prev).abs(), (z["low"] - prev).abs()))
    first = prev.isna()
    base.loc[first] = (z.loc[first, "high"] - z.loc[first, "low"]).to_numpy(float)
    denom = prev.where(~first, z["close"])
    z["true_range_norm"] = base / denom
    z["atr12_norm"] = z["true_range_norm"].rolling(12, min_periods=12).mean()

    valid = z["ret_5m"].dropna()
    z["rv12_rms"] = np.sqrt(valid.pow(2).rolling(12, min_periods=12).mean()).reindex(z.index)
    for w in WINDOWS:
        gross = valid.abs().rolling(w, min_periods=w).sum()
        net = valid.rolling(w, min_periods=w).sum()
        z[f"net{w}"] = net.reindex(z.index)
        z[f"path{w}"] = gross.reindex(z.index)
        z[f"pe{w}"] = (net.abs() / gross.replace(0.0, np.nan)).reindex(z.index)
        z[f"rev{w}"] = valid.rolling(w, min_periods=w).apply(_rolling_reversal, raw=True).reindex(z.index)

    risk = states[states["symbol"].eq(SYMBOL)][
        ["bar_end", "risk_state", "rv12", "bg_vol48", "vol_ratio", "shock_intensity", "shock"]
    ].copy()
    risk["bar_end"] = pd.to_datetime(risk["bar_end"], errors="raise")
    if risk["bar_end"].duplicated().any():
        raise RuntimeError("ols_risk_overlap_duplicate_risk_bar")
    z = z.merge(risk, on="bar_end", how="left", validate="one_to_one")
    if z["risk_state"].isna().any():
        raise RuntimeError("ols_risk_overlap_risk_state_join_gap")
    z["risk_indicator"] = z["risk_state"].isin(["UNSAFE", "RECOVERING"]).astype(int)
    z["unsafe_indicator"] = z["risk_state"].eq("UNSAFE").astype(int)

    probs = cohort[cohort["symbol"].eq(SYMBOL)][["bar_end", "recovery_probability_30m"]].copy()
    probs["bar_end"] = pd.to_datetime(probs["bar_end"], errors="raise")
    if probs["bar_end"].duplicated().any():
        raise RuntimeError("ols_risk_overlap_duplicate_probability_bar")
    z = z.merge(probs, on="bar_end", how="left", validate="one_to_one")

    for col in ("rv12_rms", "pe12", "pe24", "pe48", "rev12", "rev24", "rev48"):
        z[f"{col}_percentile"] = _pct_by_year(z, col)
    p = z["rv12_rms_percentile"]
    z["vol_bucket"] = np.select(
        [p.notna() & (p < Q1), p.notna() & (p < Q2), p.notna()],
        ["LOW_VOL", "NORMAL_VOL", "HIGH_VOL"], default="UNAVAILABLE"
    )
    p48 = z["pe48_percentile"]
    z["pe48_bucket"] = np.select(
        [p48.notna() & (p48 < Q1), p48.notna() & (p48 < Q2), p48.notna()],
        ["LOW_PE", "MID_PE", "HIGH_PE"], default="UNAVAILABLE"
    )
    z["rev48_high"] = z["rev48_percentile"].ge(Q2)
    z["morphology_score"] = z["pe12_percentile"] * (1.0 - z["pe48_percentile"]) * z["rev48_percentile"]
    z["joint_score"] = z["risk_indicator"] * z["morphology_score"]

    z["session_index"] = z.groupby(["trading_day", "session"], sort=False).cumcount()
    z["bucket"] = z["session_index"] // 3
    z["ols_timestamp"] = z.groupby(["trading_day", "session", "bucket"], sort=False)["timestamp"].transform("max")
    return z


def _auc(y, score) -> float | None:
    q = pd.DataFrame({"y": pd.to_numeric(y, errors="coerce"), "s": pd.to_numeric(score, errors="coerce")}).dropna()
    if q.empty:
        return None
    yy = q["y"].astype(int).to_numpy()
    n1 = int(yy.sum())
    n0 = int(len(yy) - n1)
    if n1 == 0 or n0 == 0:
        return None
    ranks = q["s"].rank(method="average").to_numpy(float)
    return float((ranks[yy == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def _slice_summary(q: pd.DataFrame, prefix: str) -> dict[str, object]:
    out: dict[str, object] = {f"{prefix}_bars": int(len(q))}
    if q.empty:
        return out
    out.update({
        f"{prefix}_risk_occupancy": float(q["risk_indicator"].mean()),
        f"{prefix}_unsafe_occupancy": float(q["unsafe_indicator"].mean()),
        f"{prefix}_rv_percentile_median": float(q["rv12_rms_percentile"].median()),
        f"{prefix}_rv12_rms_median": float(q["rv12_rms"].median()),
        f"{prefix}_abs_ret_median": float(q["abs_ret_5m"].median()),
        f"{prefix}_atr12_norm_median": float(q["atr12_norm"].median()),
        f"{prefix}_intrabar_range_median": float(q["intrabar_log_range"].median()),
        f"{prefix}_pe12_percentile_median": float(q["pe12_percentile"].median()),
        f"{prefix}_pe48_percentile_median": float(q["pe48_percentile"].median()),
        f"{prefix}_rev48_percentile_median": float(q["rev48_percentile"].median()),
        f"{prefix}_morphology_median": float(q["morphology_score"].median()),
        f"{prefix}_joint_median": float(q["joint_score"].median()),
        f"{prefix}_high_vol_share": float(q["vol_bucket"].eq("HIGH_VOL").mean()),
        f"{prefix}_high_vol_trend_share": float((q["vol_bucket"].eq("HIGH_VOL") & q["pe48_bucket"].eq("HIGH_PE")).mean()),
        f"{prefix}_high_vol_chop_share": float((q["vol_bucket"].eq("HIGH_VOL") & q["pe48_bucket"].eq("LOW_PE")).mean()),
    })
    prob = pd.to_numeric(q["recovery_probability_30m"], errors="coerce").dropna()
    out[f"{prefix}_recovery_probability_coverage"] = float(len(prob) / len(q))
    out[f"{prefix}_recovery_probability_median"] = None if prob.empty else float(prob.median())
    out[f"{prefix}_recovery_probability_q25"] = None if prob.empty else float(prob.quantile(0.25))
    out[f"{prefix}_recovery_probability_q75"] = None if prob.empty else float(prob.quantile(0.75))
    return out


def _episode_window(panel: pd.DataFrame, start_ts: pd.Timestamp, trough_ts: pd.Timestamp):
    ts = panel["timestamp"]
    starts = np.flatnonzero(ts.eq(start_ts).to_numpy())
    ends = np.flatnonzero(ts.eq(trough_ts).to_numpy())
    if len(starts) != 1 or len(ends) != 1:
        raise RuntimeError("ols_risk_overlap_15m_timestamp_not_in_5m")
    start_end = int(starts[0])
    trough_end = int(ends[0])
    first = start_end - 2
    if first < 0 or trough_end < first:
        raise RuntimeError("ols_risk_overlap_bad_episode_window")
    episode = panel.iloc[first:trough_end + 1]
    pre12 = panel.iloc[max(0, first - 12):first]
    pre48 = panel.iloc[max(0, first - 48):first]
    return first, trough_end, episode, pre12, pre48


def _lead(pre48: pd.DataFrame) -> int | None:
    if len(pre48) < 2:
        return None
    state = pre48["risk_indicator"].to_numpy(int)
    transitions = np.flatnonzero((state[1:] == 1) & (state[:-1] == 0)) + 1
    if len(transitions) == 0:
        return None
    return int(len(pre48) - 1 - transitions[-1])


def _prob_change(pre48: pd.DataFrame) -> float | None:
    p = pd.to_numeric(pre48["recovery_probability_30m"], errors="coerce")
    q = p.dropna()
    if len(q) < 4:
        return None
    split = len(q) // 2
    return float(q.iloc[split:].mean() - q.iloc[:split].mean())

