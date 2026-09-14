#!/usr/bin/env python3
"""Synthetic-only runtime smoke for the reusable Overnight BLACKBOX query."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXECUTOR = ROOT / "executor"
REAL_PROTOCOL = ROOT / "docs/research/OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_REUSABLE_BLACKBOX_PREREG_20260914.json"
FEATURES = ["global_risk_z", "china_offshore_z", "driver_coherence", "log_rvol20"]


def git_blob_sha1(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def write_sources(root: Path) -> dict:
    panel_path = root / "data/development/csi1000_open_pit_panel.parquet"
    ext = root / "data/v6a_external_sources_2015_2025"
    panel_path.parent.mkdir(parents=True)
    ext.mkdir(parents=True)
    dates = pd.bdate_range("2020-08-03", "2021-05-31")
    idx = np.arange(len(dates), dtype=float)
    panel = pd.DataFrame({
        "trading_day": dates,
        "gap": np.sin(idx / 9.0) * 0.01,
        "rvol20": 0.01 + (idx % 7) * 0.0001,
        "holiday_reopen": np.zeros(len(dates), dtype=int),
        "us_nasdaq": np.sin(idx / 11.0) * 0.02 + 0.001,
        "us_vix_chg": np.cos(idx / 13.0) * 0.02,
    })
    panel.to_parquet(panel_path, index=False)
    ordinary = pd.DataFrame({
        "trading_day": dates,
        "a50_ordinary_preauction_closure_return": np.cos(idx / 10.0) * 0.01 + 0.0005,
        "target_end_time": np.full(len(dates), 91400, dtype=int),
    })
    holiday = pd.DataFrame({
        "trading_day": dates,
        "a50_holiday_closure_return": np.sin(idx / 12.0) * 0.01,
        "target_end_time": np.full(len(dates), 92400, dtype=int),
    })
    ordinary_path = ext / "sgx_a50_ordinary_preauction_endpoints.parquet"
    holiday_path = ext / "sgx_a50_holiday_endpoints.parquet"
    ordinary.to_parquet(ordinary_path, index=False)
    holiday.to_parquet(holiday_path, index=False)
    hk_dates = pd.date_range("2020-01-01", "2021-06-01", freq="D")
    hk = pd.DataFrame({"date": hk_dates, "usdcny_hk": 7.0 + np.arange(len(hk_dates)) * 0.0001})
    hk_path = ext / "hkma_usdcny_cross.parquet"
    hk.to_parquet(hk_path, index=False)
    assertions_path = ext / "source_assertions.json"
    assertions = {
        "assertions": {
            "same_contract_all_events": True,
            "no_future_volume_or_oi_selection": True,
            "no_mid_window_roll": True,
            "no_forward_fill_or_interpolation": True,
            "blackbox_not_used_for_fit_or_rule_selection": True,
        }
    }
    assertions_path.write_text(json.dumps(assertions, indent=2) + "\n", encoding="utf-8")
    paths = [panel_path, hk_path, holiday_path, ordinary_path, assertions_path]
    return {
        path.relative_to(root).as_posix(): {"git_blob_sha1": git_blob_sha1(path), "bytes": path.stat().st_size}
        for path in paths
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "source"
        files = write_sources(source)
        protocol = json.loads(REAL_PROTOCOL.read_text(encoding="utf-8"))
        protocol["blackbox_source"]["files"] = files
        protocol_path = root / "protocol.json"
        protocol_path.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
        model = {
            "schema_id": "csi1000.overnight_continuous_driver_tail_likelihood_model@1.0",
            "research_identity": "overnight_continuous_driver_tail_likelihood_v1",
            "available": True,
            "protocol_sha256": protocol["parent_development_artifact"]["development_protocol_sha256"],
            "features": FEATURES,
            "class_order": ["DOWN", "MID", "UP"],
            "tail_cutoffs": {"q10": -1.0, "q90": 1.0},
            "feature_means": {name: 0.0 for name in FEATURES},
            "feature_population_sds": {name: 1.0 for name in FEATURES},
            "fit_class_priors": {"DOWN": 0.1, "MID": 0.8, "UP": 0.1},
            "down": {"intercept": -2.0, "weights": {name: 0.0 for name in FEATURES}},
            "up": {"intercept": -2.0, "weights": {name: 0.0 for name in FEATURES}},
            "mid_logit": 0.0,
            "temperature": 1.0,
            "directional_margin_threshold": 0.1,
            "minimum_selected_tail_uplift_vs_fit_class_prior": 1.5,
            "model_frozen_before_holdout_evaluation": True,
            "blackbox_authorized": False,
            "production_authority": False,
        }
        model_path = root / "model.json"
        model_path.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
        code_root = root / "code"
        code_root.mkdir()
        shutil.copyfile(EXECUTOR / "overnight_tail_blackbox_query.py", code_root / "run_query.py")
        shutil.copyfile(EXECUTOR / "verify_overnight_tail_blackbox_query.py", code_root / "verify_query.py")
        results = root / "results"
        run = subprocess.run(
            [sys.executable, str(code_root / "run_query.py"), "--source-root", str(source), "--model", str(model_path), "--protocol", str(protocol_path), "--out", str(results)],
            capture_output=True, text=True, check=False,
        )
        if run.returncode != 0 or run.stdout.strip() != "INSUFFICIENT":
            raise RuntimeError("synthetic_query_failed")
        receipt = json.loads((results / "blackbox_receipt.json").read_text(encoding="utf-8"))
        if receipt.get("decision") != "INSUFFICIENT" or receipt.get("internal_metrics_persisted") is not False:
            raise RuntimeError("synthetic_receipt_invalid")
        if set(path.name for path in results.iterdir()) != {"blackbox_receipt.json"}:
            raise RuntimeError("synthetic_result_surface_expanded")
        verify = subprocess.run(
            [sys.executable, str(code_root / "verify_query.py"), "--source-root", str(source), "--model", str(model_path), "--protocol", str(protocol_path), "--results", str(results)],
            capture_output=True, text=True, check=False,
        )
        if verify.returncode != 0:
            raise RuntimeError("synthetic_validator_failed")
        validated = json.loads(verify.stdout)
        if validated != {"decision": "INSUFFICIENT", "production_authority": False, "status": "passed"}:
            raise RuntimeError("synthetic_validator_output_invalid")
    print("SYNTHETIC_OVERNIGHT_BLACKBOX_SMOKE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
