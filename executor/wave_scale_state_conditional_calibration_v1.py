"""Pure deterministic calibration engine for issue #376.

No file/network I/O. Inputs are already-frozen in-memory records. The engine
implements leave-one-calendar-year-out fitting for validity, morphology and
morphology-conditional current-scale dominance. It grants no production authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import itertools
import math

YEARS = tuple(range(2015, 2021))
FALSE_REJECT_CAP = 0.05

DATA_INVALID = "DATA_INVALID_EDGE"
SUPPORTED = "CURRENT_SCALE_SUPPORTED"
DEVELOPING = "CURRENT_SCALE_DEVELOPING"
NOT_DOMINANT = "CURRENT_SCALE_NOT_DOMINANT"
AMBIGUOUS = "AMBIGUOUS_MULTI_SCALE"

VALID = "VALID_FOR_SCALE_JUDGMENT"
INVALID = "INVALID_OR_DISCONTINUITY"
UNCERTAIN_VALIDITY = "UNCERTAIN_VALIDITY"
TURNING = "TURNING_OR_COMPLETED"
DEVELOPING_LEG = "DEVELOPING_ONE_LEG"
MORPH_AMBIG = "MORPHOLOGY_AMBIGUOUS"
VALIDITY_DIRECTIONS = {
    "close_jump_concentration": "GE",
    "close_range_concentration": "GE",
    "jump_persistence_ratio": "LE",
    "wick_only_concentration_median": "GE",
    "wick_only_concentration_max": "GE",
    "largest_jump_relative_minute_range": "GE",
    "largest_jump_location_agreement_within_5m": "LE",
}
DOMINANCE_DIRECTIONS = {
    "tortuosity_median": "GE",
    "norm_rmse_median": "GE",
    "delta_bic_median": "GE",
    "sse_improvement_median": "LE",
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
    if direction == "GE":
        return x >= threshold
    if direction == "LE":
        return x <= threshold
    raise ValueError("direction")


def _condition_id(feature, direction, threshold):
    return f"{feature}:{direction}:{format(float(threshold), '.17g')}"


def _rule_id(rule):
    if rule["op"] == "NULL":
        return "NULL"
    parts = [_condition_id(c["feature"], c["direction"], c["threshold"])
             for c in rule["conditions"]]
    return rule["op"] + "|" + "|".join(parts)


def apply_rule(features, rule):
    if rule["op"] == "NULL":
        return False
    values = [_cmp(features.get(c["feature"]), c["direction"], c["threshold"])
              for c in rule["conditions"]]
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
    raise ValueError("rule op")


def _condition_tables(feature_rows, directions):
    n = len(feature_rows)
    all_mask = (1 << n) - 1
    by_feature = {}
    for feature in sorted(directions):
        direction = directions[feature]
        thresholds = _midpoints([row.get(feature) for row in feature_rows])
        entries = []
        for threshold in thresholds:
            true_mask = 0
            unknown_mask = 0
            for i, row in enumerate(feature_rows):
                value = _cmp(row.get(feature), direction, threshold)
                if value is True:
                    true_mask |= 1 << i
                elif value is None:
                    unknown_mask |= 1 << i
            false_mask = all_mask & ~(true_mask | unknown_mask)
            condition = {"feature": feature, "direction": direction,
                         "threshold": float(threshold)}
            entries.append((condition, true_mask, false_mask, unknown_mask))
        by_feature[feature] = entries
    return by_feature, all_mask


def _combine(a, b, op, all_mask):
    _, ta, fa, ua = a
    _, tb, fb, ub = b
    if op == "AND":
        true_mask = ta & tb
        false_mask = fa | fb
    elif op == "OR":
        true_mask = ta | tb
        false_mask = fa & fb
    else:
        raise ValueError("combine op")
    unknown_mask = all_mask & ~(true_mask | false_mask)
    return true_mask, false_mask, unknown_mask


def _rules(feature_rows, directions):
    table, all_mask = _condition_tables(feature_rows, directions)
    yield {"op": "NULL", "conditions": []}, 0, all_mask, 0
    for feature in sorted(table):
        for cond, t, f, u in table[feature]:
            yield {"op": "SINGLE", "conditions": [cond]}, t, f, u
    for f1, f2 in itertools.combinations(sorted(table), 2):
        for a in table[f1]:
            for b in table[f2]:
                for op in ("AND", "OR"):
                    t, f, u = _combine(a, b, op, all_mask)
                    rule = {"op": op, "conditions": [a[0], b[0]]}
                    yield rule, t, f, u


def _mask(indices):
    value = 0
    for i in indices:
        value |= 1 << i
    return value


def _binary_metrics(true_mask, unknown_mask, positive_mask, negative_mask, n):
    pos_n = positive_mask.bit_count()
    neg_n = negative_mask.bit_count()
    tp = (true_mask & positive_mask).bit_count()
    fp = (true_mask & negative_mask).bit_count()
    unknown = unknown_mask.bit_count()
    return {
        "positive_support": pos_n,
        "negative_support": neg_n,
        "true_positive": tp,
        "false_positive": fp,
        "recall": None if pos_n == 0 else tp / pos_n,
        "false_positive_rate": None if neg_n == 0 else fp / neg_n,
        "unknown_rate": 0.0 if n == 0 else unknown / n,
    }


def _rule_complexity(rule):
    return len(rule["conditions"]), len(rule["conditions"])


def _fit_capped_binary(feature_rows, positive_indices, negative_indices,
                       directions, false_positive_cap=FALSE_REJECT_CAP):
    n = len(feature_rows)
    positive_mask = _mask(positive_indices)
    negative_mask = _mask(negative_indices)
    if not positive_indices or not negative_indices:
        rule = {"op": "NULL", "conditions": []}
        metrics = _binary_metrics(0, 0, positive_mask, negative_mask, n)
        return {"fit_status": "INSUFFICIENT_CLASS_SUPPORT", "rule": rule,
                "rule_id": _rule_id(rule), "metrics": metrics}
    best = None
    for rule, true_mask, _, unknown_mask in _rules(feature_rows, directions):
        metrics = _binary_metrics(true_mask, unknown_mask,
                                  positive_mask, negative_mask, n)
        fp_rate = metrics["false_positive_rate"]
        if fp_rate is None or fp_rate > false_positive_cap + 1e-15:
            continue
        recall = metrics["recall"] if metrics["recall"] is not None else 0.0
        complexity = _rule_complexity(rule)
        key = (-recall, fp_rate, metrics["unknown_rate"],
               complexity[0], complexity[1], _rule_id(rule))
        item = (key, rule, metrics)
        if best is None or key < best[0]:
            best = item
    if best is None:
        raise RuntimeError("null rule must make capped binary fit feasible")
    return {"fit_status": "FITTED", "rule": best[1],
            "rule_id": _rule_id(best[1]), "metrics": best[2]}


def fit_validity_rule(records):
    rows = [r["validity"] for r in records]
    positive = [i for i, r in enumerate(records)
                if r["reference_state"] == DATA_INVALID]
    negative = [i for i, r in enumerate(records)
                if r["reference_state"] != DATA_INVALID]
    return _fit_capped_binary(rows, positive, negative, VALIDITY_DIRECTIONS)


def predict_validity(record, fit):
    value = apply_rule(record["validity"], fit["rule"])
    if value is True:
        return INVALID
    if value is False:
        return VALID
    return UNCERTAIN_VALIDITY


def fit_dominance_rule(records, branch):
    positive_state = SUPPORTED if branch == TURNING else DEVELOPING
    rows = [r["dominance"] for r in records]
    positive = [i for i, r in enumerate(records)
                if r["reference_state"] == NOT_DOMINANT]
    negative = [i for i, r in enumerate(records)
                if r["reference_state"] == positive_state]
    return _fit_capped_binary(rows, positive, negative, DOMINANCE_DIRECTIONS)


def predict_dominance(record, fit):
    value = apply_rule(record["dominance"], fit["rule"])
    if value is True:
        return NOT_DOMINANT
    if value is False:
        return SUPPORTED
    return AMBIGUOUS


def _integer_thresholds(values):
    out = sorted({int(v) for v in values if isinstance(v, int) and not isinstance(v, bool)})
    return out


def _morph_predict(features, rule):
    nr = features.get("no_reversal_count")
    peak = features.get("peak_count")
    trough = features.get("trough_count")
    if not all(isinstance(v, int) and not isinstance(v, bool)
               for v in (nr, peak, trough)):
        return MORPH_AMBIG
    developing = nr >= rule["developing_no_reversal_min"]
    turning = max(peak, trough) >= rule["turning_shape_min"]
    if turning and rule["turn_range_max"] is not None:
        tr = _finite(features.get("turn_relative_minute_range"))
        if tr is None:
            return MORPH_AMBIG
        turning = tr <= rule["turn_range_max"]
    if developing and not turning:
        return DEVELOPING_LEG
    if turning and not developing:
        return TURNING
    return MORPH_AMBIG


def _morph_rule_id(rule):
    r = "NONE" if rule["turn_range_max"] is None else format(rule["turn_range_max"], ".17g")
    return (f"NR>={rule['developing_no_reversal_min']}|"
            f"TURN>={rule['turning_shape_min']}|RANGE<={r}")


def fit_morphology_rule(records):
    train = [r for r in records if r["reference_state"] in {SUPPORTED, DEVELOPING}]
    states = {r["reference_state"] for r in train}
    if states != {SUPPORTED, DEVELOPING}:
        return {"fit_status": "INSUFFICIENT_CLASS_SUPPORT", "rule": None,
                "rule_id": "NONE", "metrics": {"support": len(train)}}
    nr_thresholds = _integer_thresholds([r["morphology"].get("no_reversal_count") for r in train])
    shape_thresholds = _integer_thresholds([
        max(r["morphology"].get("peak_count", -1), r["morphology"].get("trough_count", -1))
        for r in train
    ])
    range_thresholds = [None] + _midpoints([
        r["morphology"].get("turn_relative_minute_range") for r in train
    ])
    best = None
    for nr, shape, turn_range in itertools.product(nr_thresholds, shape_thresholds, range_thresholds):
        rule = {"developing_no_reversal_min": nr,
                "turning_shape_min": shape,
                "turn_range_max": turn_range}
        correct = wrong = ambiguous = 0
        for record in train:
            pred = _morph_predict(record["morphology"], rule)
            expected = TURNING if record["reference_state"] == SUPPORTED else DEVELOPING_LEG
            if pred == expected:
                correct += 1
            elif pred == MORPH_AMBIG:
                ambiguous += 1
            else:
                wrong += 1
        complexity = 2 + int(turn_range is not None)
        key = (-correct, wrong, ambiguous, complexity, _morph_rule_id(rule))
        metrics = {"support": len(train), "correct": correct, "wrong": wrong,
                   "ambiguous": ambiguous, "correct_rate": correct / len(train),
                   "wrong_rate": wrong / len(train), "ambiguity_rate": ambiguous / len(train)}
        if best is None or key < best[0]:
            best = (key, rule, metrics)
    if best is None:
        raise RuntimeError("morphology candidate set empty")
    return {"fit_status": "FITTED", "rule": best[1],
            "rule_id": _morph_rule_id(best[1]), "metrics": best[2]}


def predict_morphology(record, fit):
    if fit["rule"] is None:
        return MORPH_AMBIG
    return _morph_predict(record["morphology"], fit["rule"])


def _validate_records(records):
    if not isinstance(records, list) or not records:
        raise ValueError("records")
    ids = []
    years = set()
    for record in records:
        required = {"panel_id", "year", "reference_state", "validity", "morphology", "dominance"}
        if not isinstance(record, dict) or set(record) != required:
            raise ValueError("record schema")
        if not isinstance(record["panel_id"], str):
            raise ValueError("panel id")
        if record["reference_state"] not in {DATA_INVALID, SUPPORTED, DEVELOPING, NOT_DOMINANT, AMBIGUOUS}:
            raise ValueError("reference state")
        if record["year"] not in YEARS:
            raise ValueError("year")
        if not all(isinstance(record[k], dict) for k in ("validity", "morphology", "dominance")):
            raise ValueError("feature section")
        ids.append(record["panel_id"])
        years.add(record["year"])
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate panel")
    if years != set(YEARS):
        raise ValueError("year coverage")


def _dominance_training(records, validity_predictions, morphology_predictions, branch):
    positive_state = SUPPORTED if branch == TURNING else DEVELOPING
    out = []
    for record, validity, morphology in zip(records, validity_predictions, morphology_predictions):
        if validity != VALID or morphology != branch:
            continue
        if record["reference_state"] in {positive_state, NOT_DOMINANT}:
            out.append(record)
    return out


def _operational_final(record, validity, morphology, dominance_fits):
    if validity == INVALID:
        return DATA_INVALID, "VALIDITY_REJECT"
    if validity == UNCERTAIN_VALIDITY:
        return AMBIGUOUS, "VALIDITY_UNCERTAIN"
    if morphology == MORPH_AMBIG:
        return AMBIGUOUS, "MORPHOLOGY_AMBIGUOUS"
    fit = dominance_fits[morphology]
    event = apply_rule(record["dominance"], fit["rule"])
    if event is True:
        return NOT_DOMINANT, "DOMINANCE_REJECT"
    if event is None:
        return AMBIGUOUS, "DOMINANCE_UNCERTAIN"
    return (SUPPORTED if morphology == TURNING else DEVELOPING), "CURRENT_SCALE_ACCEPT"


def fit_loyo(records):
    _validate_records(records)
    ordered = sorted(records, key=lambda r: (r["year"], r["panel_id"]))
    predictions = []
    fold_models = []
    for held_year in YEARS:
        train = [r for r in ordered if r["year"] != held_year]
        test = [r for r in ordered if r["year"] == held_year]
        validity_fit = fit_validity_rule(train)
        morphology_fit = fit_morphology_rule(train)
        train_validity = [predict_validity(r, validity_fit) for r in train]
        train_morphology = [predict_morphology(r, morphology_fit) for r in train]
        dominance_fits = {}
        for branch in (TURNING, DEVELOPING_LEG):
            branch_train = _dominance_training(train, train_validity, train_morphology, branch)
            dominance_fits[branch] = fit_dominance_rule(branch_train, branch)
        fold_models.append({
            "held_year": held_year,
            "train_years": [y for y in YEARS if y != held_year],
            "train_support": len(train), "test_support": len(test),
            "validity": validity_fit,
            "morphology": morphology_fit,
            "dominance": {k: v for k, v in dominance_fits.items()},
        })
        for record in test:
            validity = predict_validity(record, validity_fit)
            morphology_component = predict_morphology(record, morphology_fit)
            operational_morphology = morphology_component if validity == VALID else MORPH_AMBIG
            final_state, final_reason = _operational_final(
                record, validity, operational_morphology, dominance_fits)
            predictions.append({
                "panel_id": record["panel_id"], "year": held_year,
                "reference_state": record["reference_state"],
                "validity_prediction": validity,
                "morphology_component_prediction": morphology_component,
                "operational_morphology": operational_morphology,
                "final_state": final_state, "final_reason": final_reason,
            })
    if len(predictions) != len(records) or len({p["panel_id"] for p in predictions}) != len(records):
        raise RuntimeError("OOF prediction cardinality")
    return {"schema_id": "csi1000.scale_state_conditional_loyo@1.0",
            "years": list(YEARS), "predictions": predictions,
            "fold_models": fold_models,
            "false_reject_cap": FALSE_REJECT_CAP,
            "production_authority": False}
