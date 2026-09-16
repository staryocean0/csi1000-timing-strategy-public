from __future__ import annotations

import argparse
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


def _load_engine():
    path = Path(__file__).resolve().with_name("ols_maxdd_risk_state_overlap_v1.py")
    spec = importlib.util.spec_from_file_location("ols_risk_overlap_engine_verify", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("ols_risk_overlap_verify_engine_unloadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _close(a, b, tol: float = 1e-12) -> bool:
    if a is None or b is None or pd.isna(a) or pd.isna(b):
        return (a is None or pd.isna(a)) and (b is None or pd.isna(b))
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)


def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    lowered = series.astype(str).str.lower()
    if not lowered.isin(["true", "false"]).all():
        raise RuntimeError("ols_risk_overlap_verify_invalid_boolean")
    return lowered.eq("true")


def _compare_table(reported: pd.DataFrame, expected: pd.DataFrame, keys: list[str], metric_cols: list[str]) -> None:
    if set(reported.columns) != set(expected.columns):
        raise RuntimeError("ols_risk_overlap_verify_table_columns")
    a = reported.sort_values(keys).reset_index(drop=True)
    b = expected.sort_values(keys).reset_index(drop=True)
    if len(a) != len(b):
        raise RuntimeError("ols_risk_overlap_verify_table_rows")
    for key in keys:
        if a[key].astype(str).tolist() != b[key].astype(str).tolist():
            raise RuntimeError(f"ols_risk_overlap_verify_table_key_{key}")
    for col in metric_cols:
        if pd.api.types.is_bool_dtype(b[col]):
            if _as_bool(a[col]).tolist() != b[col].astype(bool).tolist():
                raise RuntimeError(f"ols_risk_overlap_verify_table_bool_{col}")
            continue
        for av, bv in zip(a[col], b[col]):
            if not _close(av, bv):
                raise RuntimeError(f"ols_risk_overlap_verify_table_metric_{col}")


def verify(inputs: Path, results: Path) -> dict[str, object]:
    required_files = (
        "RESULTS.json", "RESULTS.md", "episode_overlap.csv", "family_auc.csv", "year_auc.csv",
        "vol_directionality_cells.csv", "pre_failure_lead.csv", "recovery_probability_summary.csv",
        "control_summary.csv", "data_and_semantics_receipt.json",
    )
    for name in required_files:
        path = results / name
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"ols_risk_overlap_verify_missing_{name}")

    payload = json.loads((results / "RESULTS.json").read_text(encoding="utf-8"))
    if payload.get("schema_id") != "ols_maxdd_risk_state_overlap_v1@1.0":
        raise RuntimeError("ols_risk_overlap_verify_schema")
    if payload.get("relationship_verdict") not in {"STRONG", "CONDITIONAL", "WEAK", "INSUFFICIENT_SUPPORT"}:
        raise RuntimeError("ols_risk_overlap_verify_verdict_enum")
    for key in (
        "reliability_used_as_market_state", "entry_rule_changed", "exit_rule_changed",
        "position_sizing_changed", "parameter_search_performed", "threshold_search_performed",
        "state_machine_authority", "production_authority", "fresh_oos_claimed",
    ):
        if payload.get(key) is not False:
            raise RuntimeError(f"ols_risk_overlap_verify_false_flag_{key}")
    if payload.get("risk_probability_semantics") != "recovery_probability_not_high_risk_probability":
        raise RuntimeError("ols_risk_overlap_verify_probability_semantics")

    receipt = json.loads((results / "data_and_semantics_receipt.json").read_text(encoding="utf-8"))
    if receipt.get("risk_probability_semantics") != "recovery_probability_not_high_risk_probability":
        raise RuntimeError("ols_risk_overlap_verify_receipt_probability_semantics")
    if receipt.get("reliability_used_as_market_state") is not False:
        raise RuntimeError("ols_risk_overlap_verify_receipt_reliability")
    if receipt.get("probability_missing_outside_primary_cohort_preserved") is not True:
        raise RuntimeError("ols_risk_overlap_verify_probability_missingness")
    if receipt.get("ols_failure_label_scale") != "15m" or receipt.get("risk_morphology_measurement_scale") != "native_5m":
        raise RuntimeError("ols_risk_overlap_verify_scale_semantics")
    if receipt.get("year_2026_read") is not False:
        raise RuntimeError("ols_risk_overlap_verify_year_2026")
    provenance = receipt.get("risk_input_provenance") or {}
    if provenance.get("year_2026_read") is not False or provenance.get("new_training") is not False:
        raise RuntimeError("ols_risk_overlap_verify_provenance_flags")
    if (provenance.get("risk_source") or {}).get("git_blob_sha1") != "7a9f238442f5a4836c6f38dcafec4bc34526fc5c":
        raise RuntimeError("ols_risk_overlap_verify_risk_source")
    if (provenance.get("model_freeze") or {}).get("member_sha256") != "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551":
        raise RuntimeError("ols_risk_overlap_verify_model_freeze")
    if (provenance.get("calibration_freeze") or {}).get("member_sha256") != "74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909":
        raise RuntimeError("ols_risk_overlap_verify_calibration_freeze")

    ep = pd.read_csv(results / "episode_overlap.csv", keep_default_na=False, na_values=[""])
    family = pd.read_csv(results / "family_auc.csv")
    years = pd.read_csv(results / "year_auc.csv")
    ep["top_tail"] = _as_bool(ep["top_tail"])
    if set(ep["exit_mode"].astype(str)) != set(EXIT_MODES):
        raise RuntimeError("ols_risk_overlap_verify_modes")
    if set(family["exit_mode"].astype(str)) != set(EXIT_MODES):
        raise RuntimeError("ols_risk_overlap_verify_family_modes")
    for mode in EXIT_MODES:
        q = ep[ep["exit_mode"].eq(mode)].copy()
        if int(q["top_tail"].sum()) != TOP_N:
            raise RuntimeError(f"ols_risk_overlap_verify_top20_{mode}")

    raw5, _ = d0._load_5m(inputs)
    bars = d0._to_15m(raw5)
    upf = d0._features(bars, "up")
    downf = d0._features(bars, "down")
    for mode in EXIT_MODES:
        strategy = d0._strategy(bars, upf, downf, mode)
        trace = d0._trace(bars, strategy, upf, downf)
        episodes = atlas._episodes(pd.to_numeric(trace["strategy_return"], errors="coerce").to_numpy(float))
        base = pd.DataFrame([atlas._episode_row(mode, trace, i + 1, *e) for i, e in enumerate(episodes)])
        base["depth_rank"] = base["depth_abs"].rank(method="first", ascending=False).astype(int)
        base["top_tail"] = base["depth_rank"].le(TOP_N)
        got = ep[ep["exit_mode"].eq(mode)].sort_values("episode_id").reset_index(drop=True)
        base = base.sort_values("episode_id").reset_index(drop=True)
        if len(got) != len(base):
            raise RuntimeError(f"ols_risk_overlap_verify_episode_count_{mode}")
        for col in ("episode_id", "start_timestamp", "trough_timestamp", "depth_rank"):
            if got[col].astype(str).tolist() != base[col].astype(str).tolist():
                raise RuntimeError(f"ols_risk_overlap_verify_episode_identity_{mode}_{col}")
        for av, bv in zip(got["depth"], base["depth"]):
            if not _close(av, bv):
                raise RuntimeError(f"ols_risk_overlap_verify_episode_depth_{mode}")
        if got["top_tail"].tolist() != base["top_tail"].astype(bool).tolist():
            raise RuntimeError(f"ols_risk_overlap_verify_top_membership_{mode}")

    engine = _load_engine()
    expected_family, expected_years = engine._auc_tables(ep)
    _compare_table(
        family, expected_family, ["exit_mode"],
        ["top_tail_n", "non_top_n", "auc_R", "auc_U", "auc_V", "auc_M", "auc_J"],
    )
    _compare_table(
        years, expected_years, ["year"],
        ["top_tail_n", "non_top_n", "evaluable", "auc_R", "auc_U", "auc_V", "auc_M", "auc_J"],
    )
    expected_verdict, expected_checks = engine._adjudicate(expected_family, expected_years)
    if payload.get("relationship_verdict") != expected_verdict:
        raise RuntimeError("ols_risk_overlap_verify_verdict")
    if payload.get("verdict_checks") != expected_checks:
        raise RuntimeError("ols_risk_overlap_verify_verdict_checks")
    expected_status = "DIAGNOSTIC_COMPLETED" if expected_verdict != "INSUFFICIENT_SUPPORT" else "DIAGNOSTIC_INSUFFICIENT_SUPPORT"
    if payload.get("status") != expected_status:
        raise RuntimeError("ols_risk_overlap_verify_status")

    return {
        "schema_id": "ols_maxdd_risk_state_overlap_v1_verification@1.0",
        "status": "passed",
        "relationship_verdict": expected_verdict,
        "exit_mode_count": len(EXIT_MODES),
        "diagnostic_only": True,
        "state_machine_authority": False,
        "production_authority": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.inputs.resolve(), args.results.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()
