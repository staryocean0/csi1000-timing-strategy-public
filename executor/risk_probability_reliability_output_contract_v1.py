from __future__ import annotations
import argparse, csv, hashlib, json
from pathlib import Path

SCHEMA = "risk_tool_v2_probability_reliability_output_contract_result@1.0"
SUPPORTED = "DUAL_OUTPUT_CONTRACT_SUPPORTED"
NOT_SUPPORTED = "DUAL_OUTPUT_CONTRACT_NOT_SUPPORTED"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def adjudicate(v3: dict, rel: dict, contract: dict) -> dict:
    h15 = v3.get("horizons", {}).get("15", {})
    h30 = v3.get("horizons", {}).get("30", {})
    q = rel.get("development_tercile_cutpoints", {})
    c15 = contract["15m"]
    checks = {
        "15m_grade": h15.get("grade") == c15["authority_grade_must_equal"],
        "15m_state": h15.get("acceptance_state") == "IN_PROGRESS",
        "15m_bottleneck": h15.get("current_bottleneck") == c15["authority_bottleneck_must_equal"],
        "30m_grade": h30.get("grade") == contract["30m"]["authority_grade_must_equal"],
        "30m_state": h30.get("acceptance_state") == contract["30m"]["authority_state_must_equal"],
        "reliability_supported": rel.get("score_supported") is True,
        "q33_exact": q.get("q33") == c15["band_thresholds"]["low_upper_exclusive"],
        "q67_exact": q.get("q67") == c15["band_thresholds"]["high_lower_inclusive"],
        "probability_unmodified": rel.get("probability_modified") is False,
        "ordering_unmodified": rel.get("ordering_modified") is False,
        "v3_no_production": v3.get("production_authority") is False,
        "rel_no_production": rel.get("production_authority") is False,
        "v3_2026_sealed": v3.get("year_2026_read") is False,
        "rel_2026_sealed": rel.get("year_2026_read") is False,
    }
    ok = all(checks.values()) and q.get("q33", 1) < q.get("q67", 0)
    return {
        "schema_id": SCHEMA,
        "status": SUPPORTED if ok else NOT_SUPPORTED,
        "checks": checks,
        "15m": {
            "authority_state": h15.get("acceptance_state"),
            "authority_grade": h15.get("grade"),
            "current_bottleneck": h15.get("current_bottleneck"),
            "probability_reliability_output": ok,
            "band_thresholds": c15["band_thresholds"],
            "bands": c15["bands"],
            "cannot_promote_to_complete": True,
        },
        "30m": {
            "authority_state": h30.get("acceptance_state"),
            "authority_grade": h30.get("grade"),
            "reliability_overlay_required": False,
            "research_probability_interpretation": contract["30m"]["research_probability_interpretation"],
        },
        "global_prohibitions": contract["global_prohibitions"],
        "current_v3_authority_immutable": True,
        "year_2026_read": False,
        "production_authority": False,
    }


def run(v3_path: Path, rel_path: Path, contract_path: Path, out: Path):
    result = adjudicate(load(v3_path), load(rel_path), load(contract_path))
    out.mkdir(parents=True, exist_ok=False)
    (out / "OUTPUT_CONTRACT_RESULT.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = []
    for band, policy in result["15m"]["bands"].items():
        rows.append({"band": band, **policy})
    fields = ["band", "ordering_signal", "reliability_score", "absolute_probability_research_interpretation", "probability_value_surface", "hard_probability_thresholding"]
    with (out / "BAND_POLICY.csv").open("w", newline="", encoding="utf-8") as handle:
        w = csv.DictWriter(handle, fieldnames=fields); w.writeheader(); w.writerows(rows)
    summary = {
        "schema_id": "risk_tool_v2_probability_reliability_output_contract_summary@1.0",
        "profile": "risk-v2-probability-reliability-output-contract-v1",
        "status": result["status"],
        "15m_grade": result["15m"]["authority_grade"],
        "15m_bottleneck": result["15m"]["current_bottleneck"],
        "30m_state": result["30m"]["authority_state"],
        "q33": result["15m"]["band_thresholds"]["low_upper_exclusive"],
        "q67": result["15m"]["band_thresholds"]["high_lower_inclusive"],
        "current_v3_authority_immutable": True,
        "year_2026_read": False,
        "production_authority": False,
    }
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--v3", type=Path, required=True)
    p.add_argument("--reliability", type=Path, required=True)
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    run(a.v3.resolve(), a.reliability.resolve(), a.contract.resolve(), a.out.resolve())


if __name__ == "__main__": main()
