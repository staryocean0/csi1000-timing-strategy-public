"""Explicit-ambiguity deterministic calibration v4 for issue #395.

Iterative development only. Inputs are already-frozen in-memory joined records.
No file/network I/O, outcomes, routing, or production authority.

Changes from v3:
- morphology fixes the primary S/D axis to reversal_completion_ratio_median and
  adds exactly one explicit ambiguity gate drawn from already-frozen instability
  evidence;
- validity expands to all singles and all distinct two-feature AND/OR rules over
  the same ten v2 validity features, still subject to the 5% false-invalid cap;
- dominance reuses the frozen v1 family unchanged.
"""
from __future__ import annotations

import itertools
import math

import wave_scale_state_conditional_calibration_v1 as v1
import wave_scale_state_conditional_calibration_v2 as v2

YEARS = v1.YEARS
FALSE_INVALID_CAP = v2.FALSE_INVALID_CAP

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

PRIMARY_AXIS = "reversal_completion_ratio_median"
VALIDITY_DIRECTIONS = {
    **v2.INVALID_SINGLE_DIRECTIONS,
    **v2.INVALID_GATE_DIRECTIONS,
}
AMBIGUITY_DIRECTIONS = {
    "turn_relative_minute_range": "GE",
    "shape_disagreement": "GE",
    "best_second_adjusted_bic_gap_median": "LE",
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


def _cmp(value, direction, threshold):
    x = _finite(value)
    if x is None:
        return None
    return x >= threshold if direction == "GE" else x <= threshold


def _condition_id(cond):
    return f"{cond['feature']}:{cond['direction']}:{format(cond['threshold'], '.17g')}"


def _rule_id(rule):
    if rule["op"] == "NULL":
        return "NULL"
    return rule["op"] + "|" + "|".join(_condition_id(c) for c in rule["conditions"])


def apply_validity_rule(features, rule):
    if rule["op"] == "NULL":
        return False
    values = [
        _cmp(features.get(c["feature"]), c["direction"], c["threshold"])
        for c in rule["conditions"]
    ]
    if rule["op"] == "SINGLE":
        return values[0]
    if rule["op"] == "AND":
        if False in values:
            return False
        return True if all(v is True for v in values) else None
    if rule["op"] == "OR":
        if True in values:
            return True
        return False if all(v is False for v in values) else None
    raise ValueError("unknown validity operator")


def _conditions(rows, feature):
    direction = VALIDITY_DIRECTIONS[feature]
    return [
        {"feature": feature, "direction": direction, "threshold": float(t)}
        for t in _midpoints([row.get(feature) for row in rows])
    ]


def _validity_candidates(rows):
    yield {"op": "NULL", "conditions": []}
    tables = {f: _conditions(rows, f) for f in sorted(VALIDITY_DIRECTIONS)}
    for feature in sorted(tables):
        for cond in tables[feature]:
            yield {"op": "SINGLE", "conditions": [cond]}
    for left, right in itertools.combinations(sorted(tables), 2):
        for a in tables[left]:
            for b in tables[right]:
                yield {"op": "AND", "conditions": [a, b]}
                yield {"op": "OR", "conditions": [a, b]}


def fit_validity_guard(records):
    rows = [r["validity"] for r in records]
    positive = [i for i, r in enumerate(records) if r["reference_state"] == DATA_INVALID]
    negative = [i for i, r in enumerate(records) if r["reference_state"] != DATA_INVALID]
    if not positive or not negative:
        return {
            "fit_status": "INSUFFICIENT_CLASS_SUPPORT",
            "rule": {"op": "NULL", "conditions": []},
            "rule_id": "NULL",
            "false_invalid_cap": FALSE_INVALID_CAP,
        }
    best = None
    for rule in _validity_candidates(rows):
        values = [apply_validity_rule(row, rule) for row in rows]
        tp = sum(values[i] is True for i in positive)
        fp = sum(values[i] is True for i in negative)
        unknown = sum(v is None for v in values)
        recall = tp / len(positive)
        fp_rate = fp / len(negative)
        if fp_rate > FALSE_INVALID_CAP + 1e-15:
            continue
        key = (
            -recall,
            fp_rate,
            unknown / len(rows),
            len(rule["conditions"]),
            _rule_id(rule),
        )
        metrics = {
            "positive_support": len(positive),
            "negative_support": len(negative),
            "true_positive": tp,
            "false_positive": fp,
            "recall": recall,
            "false_positive_rate": fp_rate,
            "unknown_rate": unknown / len(rows),
        }
        item = (key, rule, metrics)
        if best is None or key < best[0]:
            best = item
    if best is None:
        raise RuntimeError("NULL validity rule must be feasible")
    return {
        "fit_status": "FITTED",
        "rule": best[1],
        "rule_id": _rule_id(best[1]),
        "metrics": best[2],
        "false_invalid_cap": FALSE_INVALID_CAP,
        "semantics": "ONE_SIDED_INVALID_GUARD_BOUNDED_TWO_FEATURE",
    }


def predict_validity(record, fit):
    value = apply_validity_rule(record["validity"], fit["rule"])
    if value is True:
        return INVALID
    if value is False:
        return VALID
    return UNCERTAIN_VALIDITY


def _ambiguity_condition_id(feature, threshold):
    return f"{feature}:{AMBIGUITY_DIRECTIONS[feature]}:{format(threshold, '.17g')}"


def _morph_rule_id(rule):
    if rule is None:
        return "NONE"
    return (
        f"{PRIMARY_AXIS}:TURN>{format(rule['primary_threshold'], '.17g')}|"
        f"AMB:{_ambiguity_condition_id(rule['ambiguity_feature'], rule['ambiguity_threshold'])}"
    )


def _predict_morph_features(morphology, ambiguity, rule):
    if rule is None:
        return MORPH_AMBIG
    gate = _cmp(
        ambiguity.get(rule["ambiguity_feature"]),
        AMBIGUITY_DIRECTIONS[rule["ambiguity_feature"]],
        rule["ambiguity_threshold"],
    )
    if gate is None or gate is True:
        return MORPH_AMBIG
    primary = _finite(morphology.get(PRIMARY_AXIS))
    if primary is None:
        return MORPH_AMBIG
    return TURNING if primary > rule["primary_threshold"] else DEVELOPING_LEG


def fit_morphology(records):
    train = [
        r for r in records
        if r["reference_state"] in {SUPPORTED, DEVELOPING, AMBIGUOUS}
    ]
    states = {r["reference_state"] for r in train}
    if states != {SUPPORTED, DEVELOPING, AMBIGUOUS}:
        return {
            "fit_status": "INSUFFICIENT_CLASS_SUPPORT",
            "rule": None,
            "rule_id": "NONE",
            "metrics": {"support": len(train)},
        }
    ns = sum(r["reference_state"] == SUPPORTED for r in train)
    nd = sum(r["reference_state"] == DEVELOPING for r in train)
    na = sum(r["reference_state"] == AMBIGUOUS for r in train)
    primary_thresholds = _midpoints([
        r["morphology"].get(PRIMARY_AXIS) for r in train
        if r["reference_state"] in {SUPPORTED, DEVELOPING}
    ])
    best = None
    for ambiguity_feature in sorted(AMBIGUITY_DIRECTIONS):
        ambiguity_thresholds = _midpoints([
            r["ambiguity"].get(ambiguity_feature) for r in train
        ])
        for primary_threshold in primary_thresholds:
            for ambiguity_threshold in ambiguity_thresholds:
                rule = {
                    "primary_threshold": float(primary_threshold),
                    "ambiguity_feature": ambiguity_feature,
                    "ambiguity_threshold": float(ambiguity_threshold),
                }
                correct_s = correct_d = correct_a = 0
                cross_sd = false_amb = wrong = 0
                for record in train:
                    pred = _predict_morph_features(
                        record["morphology"], record["ambiguity"], rule
                    )
                    state = record["reference_state"]
                    expected = (
                        TURNING if state == SUPPORTED
                        else DEVELOPING_LEG if state == DEVELOPING
                        else MORPH_AMBIG
                    )
                    if pred == expected:
                        if state == SUPPORTED:
                            correct_s += 1
                        elif state == DEVELOPING:
                            correct_d += 1
                        else:
                            correct_a += 1
                    else:
                        wrong += 1
                        if state == SUPPORTED and pred == DEVELOPING_LEG:
                            cross_sd += 1
                        elif state == DEVELOPING and pred == TURNING:
                            cross_sd += 1
                        if state in {SUPPORTED, DEVELOPING} and pred == MORPH_AMBIG:
                            false_amb += 1
                scaled = (
                    correct_s * nd * na,
                    correct_d * ns * na,
                    correct_a * ns * nd,
                )
                min_recall_scaled = min(scaled)
                macro_recall_scaled = sum(scaled)
                key = (
                    -min_recall_scaled,
                    -macro_recall_scaled,
                    cross_sd,
                    false_amb,
                    wrong,
                    _morph_rule_id(rule),
                )
                metrics = {
                    "support": len(train),
                    "supported_support": ns,
                    "developing_support": nd,
                    "ambiguous_support": na,
                    "supported_correct": correct_s,
                    "developing_correct": correct_d,
                    "ambiguous_correct": correct_a,
                    "supported_recall": correct_s / ns,
                    "developing_recall": correct_d / nd,
                    "ambiguous_recall": correct_a / na,
                    "min_class_recall": min(correct_s / ns, correct_d / nd, correct_a / na),
                    "macro_class_recall": (
                        correct_s / ns + correct_d / nd + correct_a / na
                    ) / 3.0,
                    "direct_supported_developing_cross_errors": cross_sd,
                    "false_ambiguity_on_supported_developing": false_amb,
                    "wrong": wrong,
                }
                item = (key, rule, metrics)
                if best is None or key < best[0]:
                    best = item
    if best is None:
        return {
            "fit_status": "INSUFFICIENT_DISTINCT_SUPPORT",
            "rule": None,
            "rule_id": "NONE",
            "metrics": {"support": len(train)},
        }
    return {
        "fit_status": "FITTED",
        "rule": best[1],
        "rule_id": _morph_rule_id(best[1]),
        "metrics": best[2],
        "primary_axis": PRIMARY_AXIS,
        "objective": "MAX_MIN_3CLASS_RECALL_THEN_MACRO_THEN_SD_CROSS_THEN_FALSE_AMBIG_THEN_WRONG",
    }


def predict_morphology(record, fit):
    return _predict_morph_features(
        record["morphology"], record["ambiguity"], fit["rule"]
    )


def _validate_records(records):
    v2._validate_records(records)
    for record in records:
        if set(record.get("ambiguity", {})) != set(AMBIGUITY_DIRECTIONS):
            raise ValueError("exact ambiguity evidence required")


def _dominance_training(records, validity_predictions, morphology_predictions, branch):
    return v2._dominance_training(
        records, validity_predictions, morphology_predictions, branch
    )


def _final(record, validity, morphology, dominance_fits):
    return v2._final(record, validity, morphology, dominance_fits)


def fit_loyo_development(records):
    _validate_records(records)
    ordered = sorted(records, key=lambda r: (r["year"], r["panel_id"]))
    predictions, fold_models = [], []
    for held_year in YEARS:
        train = [r for r in ordered if r["year"] != held_year]
        test = [r for r in ordered if r["year"] == held_year]
        validity_fit = fit_validity_guard(train)
        morphology_fit = fit_morphology(train)
        train_validity = [predict_validity(r, validity_fit) for r in train]
        train_morph = [predict_morphology(r, morphology_fit) for r in train]
        dominance_fits = {}
        for branch in (TURNING, DEVELOPING_LEG):
            branch_train = _dominance_training(
                train, train_validity, train_morph, branch
            )
            dominance_fits[branch] = v1.fit_dominance_rule(branch_train, branch)
        fold_models.append({
            "held_year": held_year,
            "train_years": [y for y in YEARS if y != held_year],
            "train_support": len(train),
            "test_support": len(test),
            "validity": validity_fit,
            "morphology": morphology_fit,
            "dominance": dominance_fits,
        })
        for record in test:
            val = predict_validity(record, validity_fit)
            morph_component = predict_morphology(record, morphology_fit)
            morph = morph_component if val == VALID else MORPH_AMBIG
            final_state, reason = _final(record, val, morph, dominance_fits)
            predictions.append({
                "panel_id": record["panel_id"],
                "year": held_year,
                "reference_state": record["reference_state"],
                "validity_prediction": val,
                "morphology_component_prediction": morph_component,
                "operational_morphology": morph,
                "final_state": final_state,
                "final_reason": reason,
            })
    if (
        len(predictions) != len(records)
        or len({p["panel_id"] for p in predictions}) != len(records)
    ):
        raise RuntimeError("OOF prediction cardinality")
    return {
        "schema_id": "csi1000.scale_state_conditional_loyo@4.0",
        "population_role": "ITERATIVE_DEVELOPMENT_EVIDENCE_NOT_FRESH_OOS",
        "years": list(YEARS),
        "predictions": predictions,
        "fold_models": fold_models,
        "dominance_family": "V1_FROZEN_CONTROL_UNCHANGED",
        "full_192_fit_performed": False,
        "lag_selected_or_promoted": False,
        "production_authority": False,
    }
