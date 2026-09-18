"""Deterministic development-only v2 calibration family for issue #381.

Inputs are already-frozen in-memory joined records. No file/network I/O.
Validity has independent INVALID and VALID evidence rules, preserving uncertainty.
Morphology uses one preregistered normalized evidence axis with two non-crossing
training-only boundaries. Dominance reuses the frozen v1 rule family unchanged.
"""
from __future__ import annotations

import itertools
import math
import wave_scale_state_conditional_calibration_v1 as v1

YEARS = v1.YEARS
FALSE_INVALID_CAP = 0.05
FALSE_VALID_CAP = 0.05

DATA_INVALID = v1.DATA_INVALID
SUPPORTED = v1.SUPPORTED
DEVELOPING = v1.DEVELOPING
NOT_DOMINANT = v1.NOT_DOMINANT
AMBIGUOUS = v1.AMBIGUOUS
VALID = v1.VALID
INVALID = v1.INVALID
UNCERTAIN_VALIDITY = v1.UNCERTAIN_VALIDITY
TURNING = v1.TURNING
DEVELOPING_LEG = v1.DEVELOPING_LEG
MORPH_AMBIG = v1.MORPH_AMBIG

INVALID_SINGLE_DIRECTIONS = {
    "post_jump_reversal_extreme_10": "GE",
    "post_jump_midpoint_hold_fraction_10": "LE",
    "signed_post_jump_displacement_ratio_10": "LE",
    "signed_post_jump_displacement_ratio_20": "LE",
    "jump_persistence_ratio": "LE",
    "wick_only_concentration_max": "GE",
    "wick_only_concentration_median": "GE",
}
INVALID_GATE_DIRECTIONS = {
    "local_jump_isolation_ratio": "GE",
    "close_jump_concentration": "GE",
    "close_range_concentration": "GE",
}
INVALID_PAIR_CORES = (
    "post_jump_reversal_extreme_10",
    "post_jump_midpoint_hold_fraction_10",
    "signed_post_jump_displacement_ratio_10",
    "signed_post_jump_displacement_ratio_20",
    "jump_persistence_ratio",
)
VALID_SINGLE_DIRECTIONS = {
    "post_jump_reversal_extreme_10": "LE",
    "post_jump_midpoint_hold_fraction_10": "GE",
    "signed_post_jump_displacement_ratio_10": "GE",
    "signed_post_jump_displacement_ratio_20": "GE",
    "jump_persistence_ratio": "GE",
    "wick_only_concentration_max": "LE",
    "wick_only_concentration_median": "LE",
    "close_jump_concentration": "LE",
}
VALID_GATE_DIRECTIONS = INVALID_GATE_DIRECTIONS
VALID_PAIR_CORES = (
    "post_jump_reversal_extreme_10",
    "post_jump_midpoint_hold_fraction_10",
    "signed_post_jump_displacement_ratio_10",
    "signed_post_jump_displacement_ratio_20",
    "jump_persistence_ratio",
)

# score = sign * raw value; larger score means stronger TURNING evidence.
MORPHOLOGY_AXES = {
    "reversal_completion_ratio_median": 1.0,
    "delta_search_adjusted_bic_vs_one_leg_median": -1.0,
    "post_turn_fraction_median": 1.0,
    "turn_edge_distance_fraction_median": 1.0,
    "one_leg_background_count": -1.0,
}


def _finite(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _midpoints(values):
    xs = sorted({_finite(v) for v in values if _finite(v) is not None})
    return [(a + b) / 2.0 for a, b in zip(xs, xs[1:]) if a < b]


def _boundary_points(values):
    xs = sorted({_finite(v) for v in values if _finite(v) is not None})
    return sorted(set(xs + [(a + b) / 2.0 for a, b in zip(xs, xs[1:]) if a < b]))


def _cmp(value, direction, threshold):
    x = _finite(value)
    if x is None:
        return None
    return x >= threshold if direction == "GE" else x <= threshold


def _rule_id(rule):
    if rule["op"] == "NULL":
        return "NULL"
    parts = [f"{c['feature']}:{c['direction']}:{format(c['threshold'], '.17g')}"
             for c in rule["conditions"]]
    return rule["op"] + "|" + "|".join(parts)


def apply_rule(features, rule):
    if rule["op"] == "NULL":
        return False
    values = [_cmp(features.get(c["feature"]), c["direction"], c["threshold"])
              for c in rule["conditions"]]
    if rule["op"] == "SINGLE":
        return values[0]
    if False in values:
        return False
    return True if all(v is True for v in values) else None


def _conditions(rows, feature, direction):
    return [
        {"feature": feature, "direction": direction, "threshold": float(t)}
        for t in _midpoints([row.get(feature) for row in rows])
    ]


def _candidate_rules(rows, singles, gates, pair_cores):
    yield {"op": "NULL", "conditions": []}
    tables = {f: _conditions(rows, f, d) for f, d in {**singles, **gates}.items()}
    for feature in sorted(singles):
        for cond in tables[feature]:
            yield {"op": "SINGLE", "conditions": [cond]}
    for gate in sorted(gates):
        for core in sorted(pair_cores):
            if core not in singles:
                continue
            for a in tables[gate]:
                for b in tables[core]:
                    yield {"op": "AND", "conditions": [a, b]}


def _fit_capped(records, positive_state, positive_when_equal, singles, gates,
                pair_cores, cap):
    rows = [r["validity"] for r in records]
    positive = [i for i, r in enumerate(records)
                if (r["reference_state"] == positive_state) == positive_when_equal]
    negative = [i for i in range(len(records)) if i not in set(positive)]
    if not positive or not negative:
        return {"fit_status": "INSUFFICIENT_CLASS_SUPPORT",
                "rule": {"op": "NULL", "conditions": []}, "rule_id": "NULL"}
    best = None
    for rule in _candidate_rules(rows, singles, gates, pair_cores):
        values = [apply_rule(row, rule) for row in rows]
        tp = sum(values[i] is True for i in positive)
        fp = sum(values[i] is True for i in negative)
        unknown = sum(v is None for v in values)
        recall = tp / len(positive)
        fp_rate = fp / len(negative)
        if fp_rate > cap + 1e-15:
            continue
        key = (-recall, fp_rate, unknown / len(rows), len(rule["conditions"]), _rule_id(rule))
        item = (key, rule, {"positive_support": len(positive), "negative_support": len(negative),
                            "true_positive": tp, "false_positive": fp, "recall": recall,
                            "false_positive_rate": fp_rate, "unknown_rate": unknown / len(rows)})
        if best is None or item[0] < best[0]:
            best = item
    if best is None:
        raise RuntimeError("NULL rule must be feasible")
    return {"fit_status": "FITTED", "rule": best[1],
            "rule_id": _rule_id(best[1]), "metrics": best[2]}


def fit_validity_guard(records):
    invalid = _fit_capped(records, DATA_INVALID, True,
                          INVALID_SINGLE_DIRECTIONS, INVALID_GATE_DIRECTIONS,
                          INVALID_PAIR_CORES, FALSE_INVALID_CAP)
    valid = _fit_capped(records, DATA_INVALID, False,
                        VALID_SINGLE_DIRECTIONS, VALID_GATE_DIRECTIONS,
                        VALID_PAIR_CORES, FALSE_VALID_CAP)
    return {"invalid": invalid, "valid": valid,
            "false_invalid_cap": FALSE_INVALID_CAP,
            "false_valid_cap": FALSE_VALID_CAP}


def predict_validity(record, fit):
    bad = apply_rule(record["validity"], fit["invalid"]["rule"])
    good = apply_rule(record["validity"], fit["valid"]["rule"])
    if bad is True and good is not True:
        return INVALID
    if good is True and bad is not True:
        return VALID
    return UNCERTAIN_VALIDITY


def _axis_score(features, axis):
    raw = _finite(features.get(axis))
    return None if raw is None else MORPHOLOGY_AXES[axis] * raw


def _band_predict(features, rule):
    if rule is None:
        return MORPH_AMBIG
    score = _axis_score(features, rule["axis"])
    if score is None:
        return MORPH_AMBIG
    if score <= rule["developing_boundary_score"]:
        return DEVELOPING_LEG
    if score >= rule["turning_boundary_score"]:
        return TURNING
    return MORPH_AMBIG


def _band_rule_id(rule):
    if rule is None:
        return "NONE"
    return (f"{rule['axis']}|DEV<={format(rule['developing_boundary_score'], '.17g')}|"
            f"TURN>={format(rule['turning_boundary_score'], '.17g')}")


def fit_morphology_band(records):
    train = [r for r in records if r["reference_state"] in {SUPPORTED, DEVELOPING}]
    if {r["reference_state"] for r in train} != {SUPPORTED, DEVELOPING}:
        return {"fit_status": "INSUFFICIENT_CLASS_SUPPORT", "rule": None,
                "rule_id": "NONE", "metrics": {"support": len(train)}}
    best = None
    for axis in sorted(MORPHOLOGY_AXES):
        scores = [_axis_score(r["morphology"], axis) for r in train]
        thresholds = _boundary_points(scores)
        for lo, hi in itertools.combinations(thresholds, 2):
            if not lo < hi:
                continue
            rule = {"axis": axis, "developing_boundary_score": lo,
                    "turning_boundary_score": hi}
            correct_s = correct_d = wrong = ambiguous = 0
            for record in train:
                pred = _band_predict(record["morphology"], rule)
                expected = TURNING if record["reference_state"] == SUPPORTED else DEVELOPING_LEG
                if pred == expected:
                    if expected == TURNING:
                        correct_s += 1
                    else:
                        correct_d += 1
                elif pred == MORPH_AMBIG:
                    ambiguous += 1
                else:
                    wrong += 1
            correct = correct_s + correct_d
            key = (wrong, -min(correct_s, correct_d), -correct, ambiguous, _band_rule_id(rule))
            metrics = {"support": len(train), "correct": correct, "wrong": wrong,
                       "ambiguous": ambiguous, "supported_correct": correct_s,
                       "developing_correct": correct_d, "correct_rate": correct / len(train),
                       "wrong_rate": wrong / len(train), "ambiguity_rate": ambiguous / len(train)}
            item = (key, rule, metrics)
            if best is None or key < best[0]:
                best = item
    if best is None:
        return {"fit_status": "INSUFFICIENT_DISTINCT_SUPPORT", "rule": None,
                "rule_id": "NONE", "metrics": {"support": len(train)}}
    return {"fit_status": "FITTED", "rule": best[1],
            "rule_id": _band_rule_id(best[1]), "metrics": best[2],
            "ambiguous_reference_used_for_fit": False}


def predict_morphology(record, fit):
    return _band_predict(record["morphology"], fit["rule"])


def _validate_records(records):
    if not isinstance(records, list) or not records:
        raise ValueError("records")
    ids, years = [], set()
    allowed = {DATA_INVALID, SUPPORTED, DEVELOPING, NOT_DOMINANT, AMBIGUOUS}
    for record in records:
        required = {"panel_id", "year", "reference_state", "validity", "morphology", "dominance"}
        if not isinstance(record, dict) or set(record) != required:
            raise ValueError("record schema")
        if record["reference_state"] not in allowed or record["year"] not in YEARS:
            raise ValueError("record state/year")
        if not all(isinstance(record[k], dict) for k in ("validity", "morphology", "dominance")):
            raise ValueError("feature section")
        ids.append(record["panel_id"]); years.add(record["year"])
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate panel")
    if years != set(YEARS):
        raise ValueError("year coverage")


def _dominance_training(records, validity_predictions, morphology_predictions, branch):
    positive_state = SUPPORTED if branch == TURNING else DEVELOPING
    return [r for r, val, morph in zip(records, validity_predictions, morphology_predictions)
            if val == VALID and morph == branch and r["reference_state"] in {positive_state, NOT_DOMINANT}]


def _final(record, validity, morphology, dominance_fits):
    if validity == INVALID:
        return DATA_INVALID, "VALIDITY_REJECT"
    if validity == UNCERTAIN_VALIDITY:
        return AMBIGUOUS, "VALIDITY_UNCERTAIN"
    if morphology == MORPH_AMBIG:
        return AMBIGUOUS, "MORPHOLOGY_AMBIGUOUS"
    event = v1.apply_rule(record["dominance"], dominance_fits[morphology]["rule"])
    if event is True:
        return NOT_DOMINANT, "DOMINANCE_REJECT"
    if event is None:
        return AMBIGUOUS, "DOMINANCE_UNCERTAIN"
    return (SUPPORTED if morphology == TURNING else DEVELOPING), "CURRENT_SCALE_ACCEPT"


def fit_loyo_development(records):
    _validate_records(records)
    ordered = sorted(records, key=lambda r: (r["year"], r["panel_id"]))
    predictions, fold_models = [], []
    for held_year in YEARS:
        train = [r for r in ordered if r["year"] != held_year]
        test = [r for r in ordered if r["year"] == held_year]
        validity_fit = fit_validity_guard(train)
        morphology_fit = fit_morphology_band(train)
        train_validity = [predict_validity(r, validity_fit) for r in train]
        train_morph = [predict_morphology(r, morphology_fit) for r in train]
        dominance_fits = {}
        for branch in (TURNING, DEVELOPING_LEG):
            branch_train = _dominance_training(train, train_validity, train_morph, branch)
            dominance_fits[branch] = v1.fit_dominance_rule(branch_train, branch)
        fold_models.append({"held_year": held_year,
                            "train_years": [y for y in YEARS if y != held_year],
                            "train_support": len(train), "test_support": len(test),
                            "validity": validity_fit, "morphology": morphology_fit,
                            "dominance": dominance_fits})
        for record in test:
            val = predict_validity(record, validity_fit)
            morph_component = predict_morphology(record, morphology_fit)
            morph = morph_component if val == VALID else MORPH_AMBIG
            final_state, reason = _final(record, val, morph, dominance_fits)
            predictions.append({"panel_id": record["panel_id"], "year": held_year,
                                "reference_state": record["reference_state"],
                                "validity_prediction": val,
                                "morphology_component_prediction": morph_component,
                                "operational_morphology": morph,
                                "final_state": final_state, "final_reason": reason})
    if len(predictions) != len(records) or len({p["panel_id"] for p in predictions}) != len(records):
        raise RuntimeError("OOF prediction cardinality")
    return {"schema_id": "csi1000.scale_state_conditional_loyo@2.0",
            "population_role": "ITERATIVE_DEVELOPMENT_EVIDENCE_NOT_FRESH_OOS",
            "years": list(YEARS), "predictions": predictions, "fold_models": fold_models,
            "dominance_family": "V1_FROZEN_CONTROL_UNCHANGED",
            "full_192_fit_performed": False, "production_authority": False}
