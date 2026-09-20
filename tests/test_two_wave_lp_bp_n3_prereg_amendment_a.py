import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"docs/research/TWO_WAVE_LP_BP_N3_CAUSAL_INPROGRESS_CARRIER_PREREG_AMENDMENT_A_20260920.json"
M=ROOT/"docs/research/TWO_WAVE_LP_BP_N3_CAUSAL_INPROGRESS_CARRIER_PREREG_AMENDMENT_A_20260920.md"


def contract():
    return json.loads(P.read_text(encoding="utf-8"))


def test_amendment_only_closes_measurement_semantics():
    c=contract()
    assert c["schema_id"]=="csi1000.two_wave_lp_bp_n3_causal_inprogress_carrier_prereg_amendment_a@1.0"
    assert c["issue"]==652
    assert c["status"]=="FROZEN_BEFORE_N3_DATA_EXECUTION"
    assert c["changes_thresholds"] is False
    assert c["changes_carrier_family"] is False
    assert c["changes_model"] is False


def test_gate_a_common_rows_sign_and_error_formulas_are_exact():
    a=contract()["gate_a"]
    assert a["expected_joint_rows"]==68911
    assert a["component_common_rows"]=="RETROSPECTIVE_AND_N2_AND_N3_ALL_FINITE"
    assert a["sign"]["improvement"]=="fidelity_N3 - fidelity_N2"
    e=a["normalized_abs_error"]
    assert e["scale"]=="median(abs(retrospective_slope))"
    assert e["candidate_error"]=="mean(abs(causal-retrospective))/scale"
    assert e["improvement_fraction"]=="(error_N2-error_N3)/error_N2"
    assert e["scale_must_be_positive"] is True
    assert e["n2_error_must_be_positive"] is True


def test_gate_a_coverage_is_outcome_blind_and_turn_rule_is_fixed():
    a=contract()["gate_a"]
    assert a["coverage_anchors"]["outcome_blind"] is True
    assert a["coverage_anchors"]["dominance_oracle_called"] is False
    assert a["coverage_anchors"]["step"]==21
    t=a["turns"]
    assert t["zero_creates_turn"] is False
    assert t["zero_replaces_previous_nonzero"] is False
    assert t["turn_rule"]=="current_nonzero_sign != previous_nonzero_sign"
    assert t["retrospective_zero_turns"]=="FAIL_CLOSED"


def test_year_and_prefix_semantics_are_frozen():
    a=contract()["gate_a"]
    y=a["year_stability"]
    assert y["years"]==[2015,2016,2017,2018,2019,2020]
    assert y["year_score"]=="mean(four_component_improvements)"
    assert y["all_four_components_required"] is True
    p=a["prefix_replay"]
    assert p["cuts"]==[10000,30000,50000]
    assert p["full_visible_rule"]=="known_from_bar < cut"
    assert p["active_slope_abs_tolerance"]==1e-15
    assert p["all_levels_all_cuts_required"] is True


def test_gate_b_bootstrap_is_exact_and_still_conditional():
    b=contract()["gate_b"]
    assert b["only_after_gate_a_pass"] is True
    assert b["diff_bp"]=="regret_N2_bp-regret_N3_bp"
    assert b["block_definition"]["block_days"]==20
    assert b["block_definition"]["block_id"]=="trading_day_ordinal//20"
    boot=b["bootstrap"]
    assert boot["repetitions"]==2000
    assert boot["seed"]==20260920
    assert boot["ci_quantiles"]==[0.025,0.975]
    assert boot["lower_endpoint_strictly_positive"] is True


def test_no_post_result_metric_substitution_or_authority():
    c=contract()
    assert "POST_RESULT_FORMULA_CHANGE" in c["forbidden_alternatives"]
    assert "OUTCOME_BASED_CARRIER_SELECTION" in c["forbidden_alternatives"]
    assert all(v is False for v in c["authority"].values())
    text=M.read_text(encoding="utf-8")
    assert "No N3 market-data execution occurred before this amendment." in text
    assert "No implementation may replace these formulas after seeing N3 results." in text
