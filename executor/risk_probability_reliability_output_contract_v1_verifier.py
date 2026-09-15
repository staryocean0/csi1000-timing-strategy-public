from __future__ import annotations
import argparse, csv, json
from pathlib import Path

SUPPORTED = "DUAL_OUTPUT_CONTRACT_SUPPORTED"
NOT_SUPPORTED = "DUAL_OUTPUT_CONTRACT_NOT_SUPPORTED"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def expected(v3: dict, rel: dict, contract: dict) -> dict:
    h15 = v3["horizons"]["15"]
    h30 = v3["horizons"]["30"]
    c15 = contract["15m"]
    q = rel["development_tercile_cutpoints"]
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
    ok = all(checks.values()) and q["q33"] < q["q67"]
    return {
        "schema_id": "risk_tool_v2_probability_reliability_output_contract_result@1.0",
        "status": SUPPORTED if ok else NOT_SUPPORTED,
        "checks": checks,
        "15m": {
            "authority_state": h15["acceptance_state"],
            "authority_grade": h15["grade"],
            "current_bottleneck": h15["current_bottleneck"],
            "probability_reliability_output": ok,
            "band_thresholds": c15["band_thresholds"],
            "bands": c15["bands"],
            "cannot_promote_to_complete": True,
        },
        "30m": {
            "authority_state": h30["acceptance_state"],
            "authority_grade": h30["grade"],
            "reliability_overlay_required": False,
            "research_probability_interpretation": contract["30m"]["research_probability_interpretation"],
        },
        "global_prohibitions": contract["global_prohibitions"],
        "current_v3_authority_immutable": True,
        "year_2026_read": False,
        "production_authority": False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--v3",type=Path,required=True);p.add_argument("--reliability",type=Path,required=True);p.add_argument("--contract",type=Path,required=True);p.add_argument("--results",type=Path,required=True)
    a=p.parse_args()
    v3,rel,contract=load(a.v3),load(a.reliability),load(a.contract)
    got=load(a.results/"OUTPUT_CONTRACT_RESULT.json")
    exp=expected(v3,rel,contract)
    if got!=exp: raise SystemExit("output_contract_result_mismatch")
    rows=list(csv.DictReader((a.results/"BAND_POLICY.csv").open(encoding="utf-8")))
    if [r["band"] for r in rows] != list(contract["15m"]["bands"].keys()): raise SystemExit("band_policy_order_mismatch")
    summary=load(a.results/"SUMMARY.json")
    if summary.get("status")!=exp["status"] or summary.get("q33")!=contract["15m"]["band_thresholds"]["low_upper_exclusive"] or summary.get("q67")!=contract["15m"]["band_thresholds"]["high_lower_inclusive"]: raise SystemExit("summary_mismatch")
    if summary.get("production_authority") is not False or summary.get("year_2026_read") is not False: raise SystemExit("authority_boundary_mismatch")
    print(json.dumps({"status":"passed"},sort_keys=True))


if __name__=="__main__":main()
