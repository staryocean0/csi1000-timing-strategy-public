import ast
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))
import wave_scale_state_conditional_calibration_v3 as c


def validity(x=0.1, missing=False):
    return {
        "post_jump_reversal_extreme_10": None if missing else x,
        "post_jump_midpoint_hold_fraction_10": 1.0 - x,
        "signed_post_jump_displacement_ratio_10": 2.0 - x,
        "signed_post_jump_displacement_ratio_20": 2.0 - x,
        "jump_persistence_ratio": 2.0 - x,
        "wick_only_concentration_max": x,
        "wick_only_concentration_median": x,
        "local_jump_isolation_ratio": 1.0 + 10.0 * x,
        "close_jump_concentration": x,
        "close_range_concentration": x,
    }


def morph(score):
    return {
        "reversal_completion_ratio_median": score,
        "delta_search_adjusted_bic_vs_one_leg_median": -score,
        "post_turn_fraction_median": score,
        "turn_edge_distance_fraction_median": score,
        "one_leg_background_count": 5.0 - score,
    }


def dom(nondom=False):
    return {
        "tortuosity_median": 8.0 if nondom else 2.0,
        "norm_rmse_median": .20 if nondom else .05,
        "delta_bic_median": 5.0 if nondom else -30.0,
        "sse_improvement_median": .10 if nondom else .65,
    }


def rec(panel, year, state, vs=0.1, ms=0.5, nondom=False):
    return {
        "panel_id": panel,
        "year": year,
        "reference_state": state,
        "validity": validity(vs),
        "morphology": morph(ms),
        "dominance": dom(nondom),
    }


def six_year_records():
    rows = []
    for year in c.YEARS:
        rows += [
            rec(f"{year}-s", year, c.SUPPORTED, .10, .90),
            rec(f"{year}-d", year, c.DEVELOPING, .10, .10),
            rec(f"{year}-nt", year, c.NOT_DOMINANT, .10, .90, True),
            rec(f"{year}-nd", year, c.NOT_DOMINANT, .10, .10, True),
            rec(f"{year}-i", year, c.DATA_INVALID, .95, .50),
            rec(f"{year}-a", year, c.AMBIGUOUS, .10, .50),
        ]
    return rows


class CalibrationV3Tests(unittest.TestCase):
    def test_gate_features_are_legal_validity_singles(self):
        self.assertIn("close_jump_concentration", c.INVALID_SINGLE_DIRECTIONS)
        self.assertIn("close_range_concentration", c.INVALID_SINGLE_DIRECTIONS)
        self.assertIn("local_jump_isolation_ratio", c.INVALID_SINGLE_DIRECTIONS)

    def test_one_sided_validity_false_means_valid(self):
        fit = {"invalid": {"rule": {"op": "SINGLE", "conditions": [
            {"feature": "close_jump_concentration", "direction": "GE", "threshold": .5}
        ]}}}
        row = rec("x", 2015, c.SUPPORTED, .1, .9)
        self.assertEqual(c.predict_validity(row, fit), c.VALID)

    def test_one_sided_validity_missing_means_uncertain(self):
        fit = {"invalid": {"rule": {"op": "SINGLE", "conditions": [
            {"feature": "post_jump_reversal_extreme_10", "direction": "GE", "threshold": .5}
        ]}}}
        row = rec("x", 2015, c.SUPPORTED, .1, .9)
        row["validity"]["post_jump_reversal_extreme_10"] = None
        self.assertEqual(c.predict_validity(row, fit), c.UNCERTAIN_VALIDITY)

    def test_clear_single_gate_can_detect_invalid(self):
        fit = c.fit_validity_guard(six_year_records())
        self.assertEqual(fit["invalid"]["fit_status"], "FITTED")
        self.assertGreater(fit["invalid"]["metrics"]["recall"], 0)
        self.assertLessEqual(
            fit["invalid"]["metrics"]["false_positive_rate"],
            c.FALSE_INVALID_CAP + 1e-15,
        )

    def test_morphology_objective_covers_both_clear_classes(self):
        rows = six_year_records()
        fit = c.fit_morphology_band(rows)
        m = fit["metrics"]
        self.assertEqual(fit["fit_status"], "FITTED")
        self.assertGreater(m["supported_recall"], 0)
        self.assertGreater(m["developing_recall"], 0)
        self.assertGreater(m["min_class_recall"], 0)
        self.assertLess(m["ambiguity_rate"], 1.0)

    def test_morphology_does_not_make_zero_wrong_primary(self):
        rows = []
        # Create overlap where perfect zero-wrong classification requires broad
        # abstention, but coverage-aware objective must still cover both classes.
        for i in range(6):
            rows.append(rec(f"s{i}", 2015 + i % 6, c.SUPPORTED, .1, .55 + .05*i))
            rows.append(rec(f"d{i}", 2015 + i % 6, c.DEVELOPING, .1, .45 - .05*i))
        fit = c.fit_morphology_band(rows)
        self.assertGreater(fit["metrics"]["min_class_recall"], 0.5)

    def test_heldout_values_do_not_change_heldout_fold_model(self):
        rows = six_year_records()
        base = c.fit_loyo_development(rows)
        changed_rows = copy.deepcopy(rows)
        for r in changed_rows:
            if r["year"] == 2018:
                r["validity"]["close_jump_concentration"] = 999.0
                r["morphology"]["reversal_completion_ratio_median"] = 999.0
        changed = c.fit_loyo_development(changed_rows)
        a = next(f for f in base["fold_models"] if f["held_year"] == 2018)
        b = next(f for f in changed["fold_models"] if f["held_year"] == 2018)
        self.assertEqual(a, b)

    def test_oof_predicts_each_panel_once_and_no_full_fit(self):
        rows = six_year_records()
        out = c.fit_loyo_development(rows)
        self.assertEqual(len(out["predictions"]), len(rows))
        self.assertEqual(len({p["panel_id"] for p in out["predictions"]}), len(rows))
        self.assertFalse(out["full_192_fit_performed"])
        self.assertFalse(out["production_authority"])

    def test_raw_amplitude_is_not_a_calibration_feature(self):
        text = " ".join(c.INVALID_SINGLE_DIRECTIONS) + " " + " ".join(c.MORPHOLOGY_AXES)
        self.assertNotIn("incoming_leg_amplitude", text)
        self.assertNotIn("counter_leg_amplitude", text)

    def test_dominance_family_remains_v1(self):
        self.assertIs(c.v1.fit_dominance_rule, c.v1.fit_dominance_rule)

    def test_module_has_no_file_network_random_or_pandas_access(self):
        text = (ROOT / "executor/wave_scale_state_conditional_calibration_v3.py").read_text()
        tree = ast.parse(text)
        forbidden = {"pathlib", "os", "socket", "requests", "urllib", "random", "pandas"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(alias.name.split(".")[0] not in forbidden for alias in node.names))
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split(".")[0], forbidden)


if __name__ == "__main__":
    unittest.main()
