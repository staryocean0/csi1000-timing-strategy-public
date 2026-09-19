"""Issue #615: T0 causal C1-relation × frozen #507 compression-risk interaction.

Preregistered groups:
- LOW = B1+B2
- MID = B3
- HIGH = B4+B5

Primary estimands:
- delta_aligned = mean(HIGH)-mean(LOW) within causal C1 ALIGNED
- delta_opposed = mean(HIGH)-mean(LOW) within causal C1 OPPOSED
- DID = delta_opposed-delta_aligned

No score fitting, band tuning, cell merging, or post-hoc threshold search.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
import pandas as pd

import two_wave_c1_compression_risk_ranking_v1 as risk507
from wave_blindspot_relocation_v1 import _prepare_asof, causal_state
from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_dual_gate_probe_v1 import trend_shadow_trades
from wave_scale_specific_continuity_v1 import continuity_hierarchy

BOOT_REPS = 5000
BOOT_SEED = 20260919
PREFIX_CUTS = (10000, 30000, 50000, 65000)
RELATIONS = ("ALIGNED", "OPPOSED")
GROUPS = ("LOW", "MID", "HIGH")
PRIMARY_GROUPS = ("LOW", "HIGH")

AUTHORITATIVE_RISK_MODULE_SHA256 = (
    "7c386d7ce6b5b41a8df297aecf74488d806dcb20c09c852aab566f424602478c"
)
AUTHORITATIVE_SCORED_LEDGER_SHA256 = (
    "6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33"
)
EXPECTED_507_N = 945
EXPECTED_507_BASE_RATE = 0.2201058201058201
EXPECTED_507_AUC = 0.5565833420311032
EXPECTED_507_B1_RATE = 0.14788732394366197
EXPECTED_507_B5_RATE = 0.24858757062146894

MIN_TRADES_PER_PRIMARY_CELL = 50
MIN_BLOCKS_PER_PRIMARY_CELL = 15
MIN_C1_RESOLVED_COVERAGE = 0.95


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _risk_group(band: int) -> str:
    band = int(band)
    if band <= 2:
        return "LOW"
    if band == 3:
        return "MID"
    return "HIGH"


def rebuild_authoritative_507(bars: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    module_sha = _sha256(risk507.__file__)
    if module_sha != AUTHORITATIVE_RISK_MODULE_SHA256:
        raise RuntimeError(
            f"#507 module hash mismatch: {module_sha} != {AUTHORITATIVE_RISK_MODULE_SHA256}"
        )

    raw, raw_meta = risk507.build_signal_ledger(bars)
    scored, folds = risk507.walk_forward(raw)
    pooled = risk507._metrics(scored)
    checks = {
        "n": int(pooled["n"]) == EXPECTED_507_N,
        "base_rate": math.isclose(
            float(pooled["base_rate"]), EXPECTED_507_BASE_RATE, rel_tol=0, abs_tol=1e-15
        ),
        "auc": math.isclose(
            float(pooled["auc"]), EXPECTED_507_AUC, rel_tol=0, abs_tol=1e-15
        ),
        "B1_rate": math.isclose(
            float(pooled["bands"][0]["turn_rate"]),
            EXPECTED_507_B1_RATE,
            rel_tol=0,
            abs_tol=1e-15,
        ),
        "B5_rate": math.isclose(
            float(pooled["bands"][4]["turn_rate"]),
            EXPECTED_507_B5_RATE,
            rel_tol=0,
            abs_tol=1e-15,
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"#507 reconstruction mismatch: {checks}")
    receipt = {
        "authoritative_version": "v2",
        "module_sha256": module_sha,
        "declared_scored_ledger_sha256": AUTHORITATIVE_SCORED_LEDGER_SHA256,
        "rows": int(len(scored)),
        "folds": folds,
        "pooled": {
            "base_rate": float(pooled["base_rate"]),
            "auc": float(pooled["auc"]),
            "B1_rate": float(pooled["bands"][0]["turn_rate"]),
            "B5_rate": float(pooled["bands"][4]["turn_rate"]),
        },
        "checks": checks,
        "matched": True,
        "raw_meta": raw_meta,
    }
    return scored, receipt


def _stream_snapshot(stage: dict, cut: int) -> list[tuple[int, int, float]]:
    return [
        (
            int(node["occurrence_bar"]),
            int(node["known_from_bar"]),
            float(node["price"]),
        )
        for node in stage["stream"]
        if int(node["known_from_bar"]) < int(cut)
    ]


def prefix_replay(
    bars: pd.DataFrame,
    scored: pd.DataFrame,
    full_hierarchy: dict,
    cuts: tuple[int, ...] = PREFIX_CUTS,
) -> list[dict]:
    full_stage = full_hierarchy["stages"][0]
    full_prep = _prepare_asof(full_stage)
    out = []
    for cut in cuts:
        if cut >= len(bars):
            continue
        prefix = bars.iloc[:cut].reset_index(drop=True)
        ph = continuity_hierarchy(base_inventory(prefix), 1, 3)
        prefix_stage = ph["stages"][0]
        prefix_prep = _prepare_asof(prefix_stage)

        full_stream = _stream_snapshot(full_stage, cut)
        prefix_stream = _stream_snapshot(prefix_stage, cut)
        stream_passed = full_stream == prefix_stream

        candidates = scored[scored.signal_bar < cut]
        checked = 0
        mismatches = 0
        for k in candidates.signal_bar.astype(int):
            a = causal_state(full_prep, int(k))
            b = causal_state(prefix_prep, int(k))
            checked += 1
            if a["status"] != b["status"]:
                mismatches += 1
                continue
            if a["status"] == "RESOLVED" and a["leg"] != b["leg"]:
                mismatches += 1

        out.append(
            {
                "cut": int(cut),
                "stream_nodes_full": int(len(full_stream)),
                "stream_nodes_prefix": int(len(prefix_stream)),
                "stream_passed": bool(stream_passed),
                "signals_checked": int(checked),
                "state_mismatches": int(mismatches),
                "passed": bool(stream_passed and mismatches == 0),
            }
        )
    return out


def build_ledger(
    bars: pd.DataFrame, scored: pd.DataFrame, full_hierarchy: dict | None = None
) -> tuple[pd.DataFrame, dict]:
    hierarchy = (
        continuity_hierarchy(base_inventory(bars), 1, 3)
        if full_hierarchy is None
        else full_hierarchy
    )
    prep = _prepare_asof(hierarchy["stages"][0])

    trades = trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        21,
        cost_bps_per_side=2.0,
    )["trades"]
    by_signal = {int(t["signal_bar"]): t for t in trades}
    if len(by_signal) != len(trades):
        raise RuntimeError("duplicate T0 signal_bar")

    rows = []
    unresolved = 0
    missing_trade = 0
    for _, row in scored.iterrows():
        k = int(row.signal_bar)
        trade = by_signal.get(k)
        if trade is None:
            missing_trade += 1
            continue
        state = causal_state(prep, k)
        if state["status"] != "RESOLVED":
            unresolved += 1
            continue

        c1_side = 1 if state["leg"] == "UP" else -1
        t0_side = int(trade["side"])
        relation = "ALIGNED" if c1_side == t0_side else "OPPOSED"
        rows.append(
            {
                "signal_bar": k,
                "timestamp": row.timestamp,
                "year": int(row.year),
                "risk_band": int(row.risk_band),
                "risk_group": _risk_group(int(row.risk_band)),
                "compression_score": float(row.compression_score),
                "turn_next8": int(row.turn_next8),
                "c1_leg": str(state["leg"]),
                "c1_relation": relation,
                "t0_side": "LONG" if t0_side == 1 else "SHORT",
                "net_log_return": float(trade["net_log_return_proxy"]),
                "net_bp": float(trade["net_log_return_proxy"]) * 10000.0,
                "gross_log_return": float(trade["gross_log_return"]),
                "win": bool(float(trade["net_log_return_proxy"]) > 0),
                "fast_loss": bool(trade["fast_loss"]),
                "duration": int(trade["duration"]),
            }
        )

    out = pd.DataFrame(rows)
    meta = {
        "scored_rows": int(len(scored)),
        "joined_rows": int(len(out)),
        "missing_trade": int(missing_trade),
        "unresolved_c1": int(unresolved),
        "causal_c1_coverage": float(len(out) / len(scored)) if len(scored) else None,
    }
    return out, meta


def _assign_blocks(bars: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    dates = bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order = {d: i for i, d in enumerate(dict.fromkeys(dates))}
    out = df.copy()
    out["block20"] = [
        order[pd.Timestamp(ts).strftime("%Y-%m-%d")] // 20 for ts in out.timestamp
    ]
    return out


def _stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"n": 0, "blocks": 0}
    x = df.net_bp.to_numpy(float)
    return {
        "n": int(len(df)),
        "blocks": int(df.block20.nunique()),
        "mean_net_bp": float(np.mean(x)),
        "median_net_bp": float(np.median(x)),
        "win_rate": float(np.mean(df.win)),
        "fast_loss_rate": float(np.mean(df.fast_loss)),
        "mean_duration": float(np.mean(df.duration)),
    }


def tables(df: pd.DataFrame) -> dict:
    grid = {}
    for relation in RELATIONS:
        grid[relation] = {}
        for group in GROUPS:
            grid[relation][group] = _stats(
                df[(df.c1_relation == relation) & (df.risk_group == group)]
            )

    yearly = {}
    for year in sorted(df.year.unique()):
        p = df[df.year == year]
        yearly[str(int(year))] = {}
        for relation in RELATIONS:
            yearly[str(int(year))][relation] = {}
            for group in GROUPS:
                yearly[str(int(year))][relation][group] = _stats(
                    p[(p.c1_relation == relation) & (p.risk_group == group)]
                )
    return {"grid": grid, "yearly": yearly}


def _mean(df: pd.DataFrame, relation: str, group: str) -> float:
    p = df[(df.c1_relation == relation) & (df.risk_group == group)]
    return float(p.net_bp.mean()) if len(p) else math.nan


def point_contrasts(df: pd.DataFrame) -> dict:
    aligned_low = _mean(df, "ALIGNED", "LOW")
    aligned_high = _mean(df, "ALIGNED", "HIGH")
    opposed_low = _mean(df, "OPPOSED", "LOW")
    opposed_high = _mean(df, "OPPOSED", "HIGH")
    delta_aligned = aligned_high - aligned_low
    delta_opposed = opposed_high - opposed_low
    did = delta_opposed - delta_aligned
    return {
        "aligned_LOW_mean_bp": aligned_low,
        "aligned_HIGH_mean_bp": aligned_high,
        "delta_aligned_HIGH_minus_LOW": delta_aligned,
        "opposed_LOW_mean_bp": opposed_low,
        "opposed_HIGH_mean_bp": opposed_high,
        "delta_opposed_HIGH_minus_LOW": delta_opposed,
        "DID_opposed_minus_aligned": did,
    }


def yearly_contrasts(df: pd.DataFrame) -> dict:
    out = {}
    for year in sorted(df.year.unique()):
        p = df[df.year == year]
        da = _mean(p, "ALIGNED", "HIGH") - _mean(p, "ALIGNED", "LOW")
        do = _mean(p, "OPPOSED", "HIGH") - _mean(p, "OPPOSED", "LOW")
        out[str(int(year))] = {
            "delta_aligned": float(da),
            "delta_opposed": float(do),
            "did": float(do - da),
        }
    return out


def bootstrap(df: pd.DataFrame) -> dict:
    ids = np.asarray(sorted(df.block20.unique()), int)
    cells = [
        ("ALIGNED", "LOW"),
        ("ALIGNED", "HIGH"),
        ("OPPOSED", "LOW"),
        ("OPPOSED", "HIGH"),
    ]
    sums = np.zeros((len(ids), len(cells)), float)
    counts = np.zeros((len(ids), len(cells)), int)

    for bi, block in enumerate(ids):
        p = df[df.block20 == block]
        for ci, (relation, group) in enumerate(cells):
            q = p[(p.c1_relation == relation) & (p.risk_group == group)]
            sums[bi, ci] = q.net_bp.sum()
            counts[bi, ci] = len(q)

    rng = np.random.default_rng(BOOT_SEED)
    aligned, opposed, did = [], [], []
    for _ in range(BOOT_REPS):
        draw = rng.integers(0, len(ids), size=len(ids))
        ss = sums[draw].sum(axis=0)
        cc = counts[draw].sum(axis=0)
        if np.any(cc == 0):
            continue
        means = ss / cc
        da = means[1] - means[0]
        do = means[3] - means[2]
        aligned.append(float(da))
        opposed.append(float(do))
        did.append(float(do - da))

    def summary(values: list[float]) -> dict:
        a = np.asarray(values, float)
        return {
            "n_draws": int(len(a)),
            "median": float(np.median(a)),
            "ci95": [float(v) for v in np.quantile(a, [0.025, 0.975])],
        }

    return {
        "blocks": int(len(ids)),
        "repetitions": BOOT_REPS,
        "seed": BOOT_SEED,
        "delta_aligned": summary(aligned),
        "delta_opposed": summary(opposed),
        "did": summary(did),
    }


def support_gate(meta: dict, tab: dict) -> dict:
    cells = {}
    passed = True
    for relation in RELATIONS:
        for group in PRIMARY_GROUPS:
            cell = tab["grid"][relation][group]
            ok = (
                int(cell["n"]) >= MIN_TRADES_PER_PRIMARY_CELL
                and int(cell["blocks"]) >= MIN_BLOCKS_PER_PRIMARY_CELL
            )
            cells[f"{relation}_{group}"] = {
                "n": int(cell["n"]),
                "blocks": int(cell["blocks"]),
                "passed": bool(ok),
            }
            passed = passed and ok

    coverage_ok = (
        meta["causal_c1_coverage"] is not None
        and float(meta["causal_c1_coverage"]) >= MIN_C1_RESOLVED_COVERAGE
    )
    passed = passed and coverage_ok
    return {
        "min_trades_per_primary_cell": MIN_TRADES_PER_PRIMARY_CELL,
        "min_blocks_per_primary_cell": MIN_BLOCKS_PER_PRIMARY_CELL,
        "min_c1_resolved_coverage": MIN_C1_RESOLVED_COVERAGE,
        "coverage_passed": bool(coverage_ok),
        "primary_cells": cells,
        "passed": bool(passed),
    }


def adjudicate(
    support: dict, point: dict, yearly: dict, boot: dict
) -> dict:
    aligned_negative_years = sum(v["delta_aligned"] < 0 for v in yearly.values())
    opposed_positive_years = sum(v["delta_opposed"] > 0 for v in yearly.values())

    checks = {
        "aligned_delta_upper_ci_lt0": bool(boot["delta_aligned"]["ci95"][1] < 0),
        "opposed_delta_lower_ci_gt0": bool(boot["delta_opposed"]["ci95"][0] > 0),
        "did_lower_ci_gt0": bool(boot["did"]["ci95"][0] > 0),
        "aligned_delta_negative_years_ge2": bool(aligned_negative_years >= 2),
        "opposed_delta_positive_years_ge2": bool(opposed_positive_years >= 2),
    }

    if not support["passed"]:
        verdict = "T0_CAUSAL_C1_COMPRESSION_INTERACTION_INSUFFICIENT_SUPPORT"
    elif all(checks.values()):
        verdict = "T0_CAUSAL_C1_COMPRESSION_INTERACTION_SUPPORTED"
    else:
        verdict = "T0_CAUSAL_C1_COMPRESSION_INTERACTION_NOT_SUPPORTED"

    return {
        "verdict": verdict,
        "checks": checks,
        "aligned_negative_years": int(aligned_negative_years),
        "opposed_positive_years": int(opposed_positive_years),
        "point_estimates": point,
    }


def analyze(bars: pd.DataFrame) -> dict:
    scored, risk_receipt = rebuild_authoritative_507(bars)
    hierarchy = continuity_hierarchy(base_inventory(bars), 1, 3)
    replay = prefix_replay(bars, scored, hierarchy)
    if not all(item["passed"] for item in replay):
        raise RuntimeError(f"prefix replay failed: {replay}")

    ledger, meta = build_ledger(bars, scored, hierarchy)
    ledger = _assign_blocks(bars, ledger)
    tab = tables(ledger)
    point = point_contrasts(ledger)
    yearly = yearly_contrasts(ledger)
    boot = bootstrap(ledger)
    support = support_gate(meta, tab)
    decision = adjudicate(support, point, yearly, boot)

    return {
        "status": "T0_CAUSAL_C1_COMPRESSION_INTERACTION_COMPLETE",
        "risk507_reconstruction": risk_receipt,
        "prefix_replay": replay,
        "prefix_replay_passed": True,
        "meta": meta,
        "support": support,
        "tables": tab,
        "point_contrasts": point,
        "yearly_contrasts": yearly,
        "bootstrap": boot,
        "decision": decision,
        "ledger": ledger,
        "authority": {
            "signal": False,
            "router": False,
            "trade": False,
            "paper_trading": False,
            "live_trading": False,
            "production": False,
        },
    }
