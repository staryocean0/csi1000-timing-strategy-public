"""Independent verifier for Two-Wave issue #615.

Does not import the issue-615 study module. It reconstructs the frozen #507 score,
causal C1 relation, T0 outcome, support cells, block bootstrap and preregistered
gate verdict from the frozen 5m input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import two_wave_c1_compression_risk_ranking_v1 as risk507
from wave_blindspot_relocation_v1 import _prepare_asof, causal_state
from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_dual_gate_probe_v1 import trend_shadow_trades
from wave_scale_specific_continuity_v1 import continuity_hierarchy

DATA_FILE = "5m_offset_0.parquet"
DATA_BYTES = 3351411
DATA_SHA256 = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"
RISK_MODULE_SHA256 = "7c386d7ce6b5b41a8df297aecf74488d806dcb20c09c852aab566f424602478c"
EXPECTED_RISK_ROWS = 945
BOOT_REPS = 5000
BOOT_SEED = 20260919
ATOL = 1e-10


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(reason: str) -> None:
    print(json.dumps({"status": "failed", "reason": reason}, sort_keys=True))
    raise SystemExit(1)


def group(band: int) -> str:
    return "LOW" if band <= 2 else ("MID" if band == 3 else "HIGH")


def close(a: float, b: float, atol: float = ATOL) -> bool:
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=atol)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    inputs = Path(args.inputs)
    results = Path(args.results)

    data = inputs / DATA_FILE
    exact_path = results / "ISSUE615_RESULT_EXACT.json"
    ledger_path = results / "ISSUE615_JOINED_LEDGER.csv"
    if not data.is_file() or data.stat().st_size != DATA_BYTES or sha256(data) != DATA_SHA256:
        fail("input_identity_mismatch")
    if not exact_path.is_file() or not ledger_path.is_file():
        fail("required_output_missing")
    if sha256(Path(risk507.__file__)) != RISK_MODULE_SHA256:
        fail("risk507_module_identity_mismatch")

    exact = json.loads(exact_path.read_text())
    ledger = pd.read_csv(ledger_path, parse_dates=["timestamp"])
    bars = pd.read_parquet(data).reset_index(drop=True)
    if len(bars) != 70114:
        fail("input_row_count_mismatch")

    raw, _ = risk507.build_signal_ledger(bars)
    scored, _ = risk507.walk_forward(raw)
    if len(scored) != EXPECTED_RISK_ROWS:
        fail("risk507_row_count_mismatch")
    if len(ledger) != len(scored) or ledger.signal_bar.duplicated().any():
        fail("joined_ledger_identity_mismatch")

    got = ledger.set_index("signal_bar").sort_index()
    exp = scored.set_index("signal_bar").sort_index()
    if not np.array_equal(got.index.to_numpy(int), exp.index.to_numpy(int)):
        fail("risk507_signal_set_mismatch")
    if not np.array_equal(got.risk_band.to_numpy(int), exp.risk_band.to_numpy(int)):
        fail("risk507_band_mismatch")
    if not np.allclose(
        got.compression_score.to_numpy(float),
        exp.compression_score.to_numpy(float),
        rtol=0.0,
        atol=1e-14,
    ):
        fail("risk507_score_mismatch")

    hierarchy = continuity_hierarchy(base_inventory(bars), 1, 3)
    prep = _prepare_asof(hierarchy["stages"][0])
    trades = trend_shadow_trades(
        bars.close.to_numpy(float), bars.open.to_numpy(float), 21,
        cost_bps_per_side=2.0,
    )["trades"]
    by_signal = {int(t["signal_bar"]): t for t in trades}

    recomputed = []
    for row in scored.itertuples(index=False):
        k = int(row.signal_bar)
        trade = by_signal.get(k)
        if trade is None:
            fail("missing_t0_trade")
        state = causal_state(prep, k)
        if state["status"] != "RESOLVED":
            fail("causal_c1_unresolved")
        c1_side = 1 if state["leg"] == "UP" else -1
        t0_side = int(trade["side"])
        recomputed.append({
            "signal_bar": k,
            "relation": "ALIGNED" if c1_side == t0_side else "OPPOSED",
            "risk_group": group(int(row.risk_band)),
            "net_bp": float(trade["net_log_return_proxy"]) * 10000.0,
            "year": int(row.year),
            "timestamp": pd.Timestamp(row.timestamp),
        })
    frame = pd.DataFrame(recomputed).set_index("signal_bar").sort_index()
    if not np.array_equal(frame.relation.to_numpy(), got.c1_relation.to_numpy()):
        fail("causal_relation_mismatch")
    if not np.array_equal(frame.risk_group.to_numpy(), got.risk_group.to_numpy()):
        fail("risk_group_mismatch")
    if not np.allclose(frame.net_bp.to_numpy(), got.net_bp.to_numpy(), rtol=0.0, atol=1e-12):
        fail("t0_outcome_mismatch")

    dates = bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order = {d: i for i, d in enumerate(dict.fromkeys(dates))}
    frame = frame.reset_index()
    frame["block20"] = [
        order[pd.Timestamp(ts).strftime("%Y-%m-%d")] // 20 for ts in frame.timestamp
    ]

    def mean(rel: str, rg: str) -> float:
        q = frame[(frame.relation == rel) & (frame.risk_group == rg)]
        return float(q.net_bp.mean())

    aligned_low = mean("ALIGNED", "LOW")
    aligned_high = mean("ALIGNED", "HIGH")
    opposed_low = mean("OPPOSED", "LOW")
    opposed_high = mean("OPPOSED", "HIGH")
    da = aligned_high - aligned_low
    do = opposed_high - opposed_low
    did = do - da

    point = exact.get("point_contrasts", {})
    required_point = {
        "aligned_LOW_mean_bp": aligned_low,
        "aligned_HIGH_mean_bp": aligned_high,
        "delta_aligned_HIGH_minus_LOW": da,
        "opposed_LOW_mean_bp": opposed_low,
        "opposed_HIGH_mean_bp": opposed_high,
        "delta_opposed_HIGH_minus_LOW": do,
        "DID_opposed_minus_aligned": did,
    }
    if any(not close(point.get(k, math.nan), v) for k, v in required_point.items()):
        fail("point_contrast_mismatch")

    for rel in ("ALIGNED", "OPPOSED"):
        for rg in ("LOW", "HIGH"):
            q = frame[(frame.relation == rel) & (frame.risk_group == rg)]
            support = exact["support"]["primary_cells"][f"{rel}_{rg}"]
            if int(support["n"]) != len(q) or int(support["blocks"]) != q.block20.nunique():
                fail("support_cell_mismatch")
            if len(q) < 50 or q.block20.nunique() < 15:
                fail("preregistered_support_gate_failed")
    if float(exact["meta"]["causal_c1_coverage"]) < 0.95:
        fail("coverage_gate_failed")

    yearly = {}
    for year in (2018, 2019, 2020):
        p = frame[frame.year == year]
        def ym(rel: str, rg: str) -> float:
            q = p[(p.relation == rel) & (p.risk_group == rg)]
            return float(q.net_bp.mean())
        ya = ym("ALIGNED", "HIGH") - ym("ALIGNED", "LOW")
        yo = ym("OPPOSED", "HIGH") - ym("OPPOSED", "LOW")
        yearly[str(year)] = (ya, yo, yo - ya)
        reported = exact["yearly_contrasts"][str(year)]
        if not (
            close(reported["delta_aligned"], ya)
            and close(reported["delta_opposed"], yo)
            and close(reported["did"], yo - ya)
        ):
            fail("yearly_contrast_mismatch")

    ids = np.asarray(sorted(frame.block20.unique()), int)
    cells = [
        ("ALIGNED", "LOW"), ("ALIGNED", "HIGH"),
        ("OPPOSED", "LOW"), ("OPPOSED", "HIGH"),
    ]
    sums = np.zeros((len(ids), 4), float)
    counts = np.zeros((len(ids), 4), int)
    for bi, block in enumerate(ids):
        p = frame[frame.block20 == block]
        for ci, (rel, rg) in enumerate(cells):
            q = p[(p.relation == rel) & (p.risk_group == rg)]
            sums[bi, ci] = q.net_bp.sum()
            counts[bi, ci] = len(q)

    rng = np.random.default_rng(BOOT_SEED)
    A, O, D = [], [], []
    for _ in range(BOOT_REPS):
        draw = rng.integers(0, len(ids), size=len(ids))
        ss = sums[draw].sum(axis=0)
        cc = counts[draw].sum(axis=0)
        if np.any(cc == 0):
            continue
        means = ss / cc
        a = means[1] - means[0]
        o = means[3] - means[2]
        A.append(float(a)); O.append(float(o)); D.append(float(o - a))

    for key, values in (("delta_aligned", A), ("delta_opposed", O), ("did", D)):
        arr = np.asarray(values, float)
        ci = np.quantile(arr, [0.025, 0.975])
        reported = exact["bootstrap"][key]
        if int(reported["n_draws"]) != len(arr):
            fail("bootstrap_draw_count_mismatch")
        if not (
            close(reported["median"], np.median(arr))
            and close(reported["ci95"][0], ci[0])
            and close(reported["ci95"][1], ci[1])
        ):
            fail("bootstrap_mismatch")

    aligned_negative_years = sum(v[0] < 0 for v in yearly.values())
    opposed_positive_years = sum(v[1] > 0 for v in yearly.values())
    checks = {
        "aligned_delta_upper_ci_lt0": exact["bootstrap"]["delta_aligned"]["ci95"][1] < 0,
        "opposed_delta_lower_ci_gt0": exact["bootstrap"]["delta_opposed"]["ci95"][0] > 0,
        "did_lower_ci_gt0": exact["bootstrap"]["did"]["ci95"][0] > 0,
        "aligned_delta_negative_years_ge2": aligned_negative_years >= 2,
        "opposed_delta_positive_years_ge2": opposed_positive_years >= 2,
    }
    verdict = (
        "T0_CAUSAL_C1_COMPRESSION_INTERACTION_SUPPORTED"
        if all(checks.values())
        else "T0_CAUSAL_C1_COMPRESSION_INTERACTION_NOT_SUPPORTED"
    )
    if exact["decision"]["checks"] != checks or exact["decision"]["verdict"] != verdict:
        fail("preregistered_adjudication_mismatch")
    if any(bool(exact["authority"].get(k)) for k in exact["authority"]):
        fail("authority_scope_violation")

    print(json.dumps({
        "status": "passed",
        "issue": 615,
        "verified_rows": int(len(frame)),
        "verified_blocks": int(len(ids)),
        "verdict": verdict,
        "new_training": False,
        "production_authority": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
