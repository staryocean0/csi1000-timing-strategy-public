"""Coverage-aware deterministic calibration v3 for issue #388.

Iterative development only. Inputs are frozen in-memory records. No file/network
I/O, outcomes, routing, or production authority.

Changes from v2:
- validity is a one-sided INVALID guard; absence of invalid evidence is VALID
  when the selected rule is evaluable, and missing selected evidence is UNCERTAIN;
- existing validity gate features are also legal single-rule candidates;
- morphology retains the same one-axis/two-boundary family but optimizes class
  coverage before wrong/abstention tie-breaks, so abstention is not free.
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

INVALID_SINGLE_DIRECTIONS = {
    **v2.INVALID_SINGLE_DIRECTIONS,
    **v2.INVALID_GATE_DIRECTIONS,
}
INVALID_GATE_DIRECTIONS = dict(v2.INVALID_GATE_DIRECTIONS)
INVALID_PAIR_CORES = tuple(v2.INVALID_PAIR_CORES)
MORPHOLOGY_AXES = dict(v2.MORPHOLOGY_AXES)


def fit_validity_guard(records):
    invalid = v2._fit_capped(
        records,
        DATA_INVALID,
        True,
        INVALID_SINGLE_DIRECTIONS,
        INVALID_GATE_DIRECTIONS,
        INVALID_PAIR_CORES,
        FALSE_INVALID_CAP,
    )
    return {
        "invalid": invalid,
        "false_invalid_cap": FALSE_INVALID_CAP,
        "semantics": "ONE_SIDED_INVALID_GUARD",
    }


def predict_validity(record, fit):
    value = v2.apply_rule(record["validity"], fit["invalid"]["rule"])
    if value is True:
        return INVALID
    if value is False:
        return VALID
    return UNCERTAIN_VALIDITY


def _axis_score(features, axis):
    raw = v2._finite(features.get(axis))
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
    return (
        f"{rule['axis']}|DEV<={format(rule['developing_boundary_score'], '.17g')}|"
        f"TURN>={format(rule['turning_boundary_score'], '.17g')}"
    )


def fit_morphology_band(records):
    train = [r for r in records if r["reference_state"] in {SUPPORTED, DEVELOPING}]
    states = {r["reference_state"] for r in train}
    if states != {SUPPORTED, DEVELOPING}:
        return {
            "fit_status": "INSUFFICIENT_CLASS_SUPPORT",
            "rule": None,
            "rule_id": "NONE",
            "metrics": {"support": len(train)},
        }
    supported_n = sum(r["reference_state"] == SUPPORTED for r in train)
    developing_n = sum(r["reference_state"] == DEVELOPING for r in train)
    best = None
    for axis in sorted(MORPHOLOGY_AXES):
        scores = [_axis_score(r["morphology"], axis) for r in train]
        thresholds = v2._boundary_points(scores)
        for lo, hi in itertools.combinations(thresholds, 2):
            if not lo < hi:
                continue
            rule = {
                "axis": axis,
                "developing_boundary_score": float(lo),
                "turning_boundary_score": float(hi),
            }
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
            # Denominators are fixed inside a fold. Integer cross-products avoid
            # floating tie instability while exactly ranking min class recall
            # and macro-average class recall.
            min_recall_scaled = min(
                correct_s * developing_n,
                correct_d * supported_n,
            )
            macro_recall_scaled = (
                correct_s * developing_n + correct_d * supported_n
            )
            key = (
                -min_recall_scaled,
                -macro_recall_scaled,
                wrong,
                ambiguous,
                _band_rule_id(rule),
            )
            metrics = {
                "support": len(train),
                "supported_support": supported_n,
                "developing_support": developing_n,
                "correct": correct,
                "wrong": wrong,
                "ambiguous": ambiguous,
                "supported_correct": correct_s,
                "developing_correct": correct_d,
                "supported_recall": correct_s / supported_n,
                "developing_recall": correct_d / developing_n,
                "min_class_recall": min(correct_s / supported_n, correct_d / developing_n),
                "macro_class_recall": (
                    correct_s / supported_n + correct_d / developing_n
                ) / 2.0,
                "correct_rate": correct / len(train),
                "wrong_rate": wrong / len(train),
                "ambiguity_rate": ambiguous / len(train),
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
        "rule_id": _band_rule_id(best[1]),
        "metrics": best[2],
        "objective": "MAX_MIN_CLASS_RECALL_THEN_MACRO_RECALL_THEN_WRONG_THEN_AMBIGUITY",
        "ambiguous_reference_used_for_fit": False,
    }


def predict_morphology(record, fit):
    return _band_predict(record["morphology"], fit["rule"])


def _validate_records(records):
    return v2._validate_records(records)


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
        morphology_fit = fit_morphology_band(train)
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
        "schema_id": "csi1000.scale_state_conditional_loyo@3.0",
        "population_role": "ITERATIVE_DEVELOPMENT_EVIDENCE_NOT_FRESH_OOS",
        "years": list(YEARS),
        "predictions": predictions,
        "fold_models": fold_models,
        "dominance_family": "V1_FROZEN_CONTROL_UNCHANGED",
        "full_192_fit_performed": False,
        "production_authority": False,
    }
