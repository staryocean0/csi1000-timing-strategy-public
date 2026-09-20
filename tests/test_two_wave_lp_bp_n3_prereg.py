import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "docs/research/TWO_WAVE_LP_BP_N3_CAUSAL_INPROGRESS_CARRIER_PREREG_20260920.json"
MD_PATH = ROOT / "docs/research/TWO_WAVE_LP_BP_N3_CAUSAL_INPROGRESS_CARRIER_PREREG_20260920.md"


def load_contract():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def test_identity_source_and_parent_evidence_are_frozen():
    c = load_contract()
    assert c["schema_id"] == "csi1000.two_wave_lp_bp_n3_causal_inprogress_carrier_prereg@1.0"
    assert c["issue"] == 652
    assert c["parents"] == {"routing_thread": 450, "r2b": 461, "n2": 470}
    assert c["status"] == "FROZEN_BEFORE_NEW_N3_OUTCOME_ANALYSIS"
    assert c["source"]["rows"] == 70114
    assert c["source"]["sha256"] == "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"
    assert c["source"]["role"] == "CONSUMED_DEVELOPMENT_NOT_FRESH_OOS"
    assert c["parent_evidence"]["n2_result_sha256"] == "db94e7b36ef4f21e2a3791390ccea348b53c67eb69e3bdb191b54b852ac47181"


def test_single_carrier_family_and_lp_bp_symmetry_are_fixed():
    c = load_contract()
    fam = c["carrier_family"]
    assert fam["count"] == 1
    assert fam["name"] == "CONFIRMED_ANCHOR_IMMEDIATE_CHILD_INPROGRESS_BRIDGE"
    assert fam["future_nodes_allowed"] is False
    assert fam["retrospective_interpolation_allowed"] is False
    assert fam["outcome_tuning_allowed"] is False
    assert fam["per_stream_rule"]["active_slope"] == "bridge_slope_if_valid_child_exists_else_confirmed_slope"
    reps = c["representations"]
    assert reps["shared_raw_active_slopes"] == ["g_active_1", "g_active_2", "g_active_3"]
    assert reps["LP"] == {"fast": "g_active_1", "slow": "g_active_2"}
    assert reps["BP"] == {"fast": "g_active_1-g_active_2", "slow": "g_active_2-g_active_3"}
    assert reps["symmetric_raw_information"] is True

def test_gate_a_precedes_any_dominance_outcome():
    c = load_contract()
    assert c["ordered_gates"] == [
        "A_OUTCOME_BLIND_CARRIER_FIDELITY",
        "B_FROZEN_DOMINANCE_QUALIFICATION",
    ]
    assert c["gate_b_requires_gate_a_pass"] is True
    a = c["gate_a"]
    assert a["outcome_blind"] is True
    assert "dominance_label" in a["forbidden_fields"]
    assert "regret" in a["forbidden_fields"]
    assert a["prefix_cuts"] == [10000, 30000, 50000]
    assert a["components_requiring_sign_improvement"] == 3
    assert a["components_requiring_error_improvement"] == 3
    assert a["fail_label"] == "N3_OUTCOME_BLIND_CARRIER_FIDELITY_NOT_SUPPORTED"


def test_gate_b_reuses_frozen_n1_n2_protocol_without_model_search():
    c = load_contract()
    b = c["gate_b"]
    assert b["run_only_if_gate_a_passes"] is True
    assert (b["T0_bars"], b["T1_bars"], b["dominance_horizon_bars"]) == (21, 86, 86)
    assert b["test_years"] == [2018, 2019, 2020]
    assert b["model"]["class"] == "DecisionTreeClassifier"
    assert b["model"]["max_depth"] == 3
    assert b["model"]["min_samples_leaf"] == 100
    assert b["model"]["hyperparameter_search"] is False
    assert len(b["feature_slots"]) == 9
    assert b["additional_features_allowed"] is False
    q = b["qualification"]
    assert q["pooled_balanced_accuracy_min"] == 0.52
    assert q["years_passing_min"] == 2
    assert q["mean_regret_improvement_vs_n2_fraction_min"] == 0.05
    assert q["regret_n2_minus_n3_ci95_lower_strictly_positive"] is True
    assert b["neither_qualifies_label"] == "N3_NO_CAUSAL_REPRESENTATION_QUALIFIED__STOP_R2B_CARRIER_SEARCH"


def test_stop_rule_forbids_automatic_n4_and_authority_promotion():
    c = load_contract()
    assert "AUTOMATIC_N4_FEATURE_ZOO" in c["hard_prohibitions"]
    assert c["stop_rule"]["automatic_n4_authorized"] is False
    assert c["stop_rule"]["gate_a_fail"] == "CLOSE_652_WITHOUT_GATE_B"
    assert c["stop_rule"]["gate_a_pass_gate_b_neither_qualifies"] == "CLOSE_652_AND_STOP_AUTOMATIC_R2B_CARRIER_EXPANSION"
    assert all(v is False for v in c["authority"].values())


def test_markdown_preserves_outcome_blind_then_dominance_boundary():
    text = MD_PATH.read_text(encoding="utf-8")
    assert "FROZEN BEFORE NEW N3 OUTCOME ANALYSIS" in text
    assert "Gate A — outcome-blind causal carrier fidelity" in text
    assert "Gate B is run only if Gate A passes." in text
    assert "No blend weight, lookback length, threshold or smoothing parameter is searched." in text
    assert "No N4 feature zoo is authorized." in text
    assert "The #624/#635/#647 state-survival thread remains closed" in text
