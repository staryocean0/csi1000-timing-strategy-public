from __future__ import annotations

import argparse
import json
from pathlib import Path

from ols_maxdd_risk_state_overlap_v1_features import (
    EXIT_MODES, TOP_N, YEARS, SYMBOL, Q1, Q2, WINDOWS, d0, _risk_rows, _market_panel,
)
from ols_maxdd_risk_state_overlap_v1_analysis import (
    _episode_rows, _auc_tables, _adjudicate, _cell_table, _prob_summary, _control_summary,
)


def run(inputs: Path, out: Path) -> None:
    raw5, data_receipt = d0._load_5m(inputs)
    bars15 = d0._to_15m(raw5)
    upf = d0._features(bars15, "up")
    downf = d0._features(bars15, "down")
    traces = {}
    for mode in EXIT_MODES:
        strategy = d0._strategy(bars15, upf, downf, mode)
        traces[mode] = d0._trace(bars15, strategy, upf, downf)

    states, cohort = _risk_rows(inputs)
    panel = _market_panel(raw5, states, cohort)
    ep, cells, lead = _episode_rows(panel, traces)
    family, years = _auc_tables(ep)
    verdict, checks = _adjudicate(family, years)
    cell_table = _cell_table(cells)
    prob = _prob_summary(ep)
    controls = _control_summary(ep, panel, traces)

    out.mkdir(parents=True, exist_ok=False)
    ep.to_csv(out / "episode_overlap.csv", index=False)
    family.to_csv(out / "family_auc.csv", index=False)
    years.to_csv(out / "year_auc.csv", index=False)
    cell_table.to_csv(out / "vol_directionality_cells.csv", index=False)
    lead.to_csv(out / "pre_failure_lead.csv", index=False)
    prob.to_csv(out / "recovery_probability_summary.csv", index=False)
    controls.to_csv(out / "control_summary.csv", index=False)

    risk_provenance = json.loads((inputs / "RISK_INPUT_PROVENANCE.json").read_text(encoding="utf-8"))
    receipt = {
        "schema_id": "ols_maxdd_risk_state_overlap_semantics_receipt@1.0",
        "symbol": SYMBOL,
        "years": list(YEARS),
        "data_receipt": data_receipt,
        "risk_input_provenance": risk_provenance,
        "risk_state_categories": ["NORMAL", "UNSAFE", "RECOVERING"],
        "risk_state_rows": int(len(states)),
        "risk_primary_cohort_rows": int(len(cohort)),
        "risk_probability_semantics": "recovery_probability_not_high_risk_probability",
        "primary_probability_horizon_minutes": 30,
        "probability_missing_outside_primary_cohort_preserved": True,
        "reliability_used_as_market_state": False,
        "volatility_bucket_quantiles": [Q1, Q2],
        "morphology_windows_5m": list(WINDOWS),
        "ols_failure_label_scale": "15m",
        "risk_morphology_measurement_scale": "native_5m",
        "year_2026_read": False,
    }
    (out / "data_and_semantics_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    result = {
        "schema_id": "ols_maxdd_risk_state_overlap_v1@1.0",
        "status": "DIAGNOSTIC_COMPLETED" if verdict != "INSUFFICIENT_SUPPORT" else "DIAGNOSTIC_INSUFFICIENT_SUPPORT",
        "relationship_verdict": verdict,
        "verdict_checks": checks,
        "symbol": SYMBOL,
        "years": list(YEARS),
        "exit_modes": list(EXIT_MODES),
        "top_n": TOP_N,
        "risk_probability_semantics": "recovery_probability_not_high_risk_probability",
        "reliability_used_as_market_state": False,
        "entry_rule_changed": False,
        "exit_rule_changed": False,
        "position_sizing_changed": False,
        "parameter_search_performed": False,
        "threshold_search_performed": False,
        "state_machine_authority": False,
        "production_authority": False,
        "fresh_oos_claimed": False,
    }
    (out / "RESULTS.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# OLS MaxDD Failure × Volatility / Risk-State Overlap v1",
        "",
        f"Relationship verdict: **{verdict}**",
        "",
        "Diagnostic only. `recovery_probability` means probability of recovery to NORMAL, not high-risk probability.",
        "Reliability LOW/MID/HIGH is not used as market state.",
        "",
        "| exit family | AUC risk-state R | AUC raw-vol V | AUC morphology M | AUC joint J |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in family.itertuples():
        lines.append(f"| {r.exit_mode} | {r.auc_R:.3f} | {r.auc_V:.3f} | {r.auc_M:.3f} | {r.auc_J:.3f} |")
    lines += [
        "",
        "No filter, state machine, entry/exit overlay, sizing, leverage, routing, or production authority is granted.",
    ]
    (out / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    run(args.inputs.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
