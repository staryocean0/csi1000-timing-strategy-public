import ast
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))
import wave_scale_state_conditional_calibration_v1 as c


def validity(invalid=False):
    return {
        "close_jump_concentration": .90 if invalid else .10,
        "close_range_concentration": .95 if invalid else .15,
        "jump_persistence_ratio": .05 if invalid else .95,
        "wick_only_concentration_median": .80 if invalid else .05,
        "wick_only_concentration_max": .90 if invalid else .08,
        "largest_jump_relative_minute_range": 40.0 if invalid else 4.0,
        "largest_jump_location_agreement_within_5m": 1.0 if invalid else 5.0,
    }


def morph(kind):
    if kind == "turn":
        return {"no_reversal_count": 0, "peak_count": 5, "trough_count": 0,
                "turn_relative_minute_range": 4.0}
    if kind == "leg":
        return {"no_reversal_count": 5, "peak_count": 0, "trough_count": 0,
                "turn_relative_minute_range": 4.0}
    return {"no_reversal_count": 2, "peak_count": 2, "trough_count": 1,
            "turn_relative_minute_range": 20.0}


def dom(nondom=False):
    return {
        "tortuosity_median": 8.0 if nondom else 2.0,
        "norm_rmse_median": .20 if nondom else .05,
        "delta_bic_median": 5.0 if nondom else -30.0,
        "sse_improvement_median": .10 if nondom else .65,
    }


def rec(panel, year, state, morphology, invalid=False, nondom=False):
    return {"panel_id": panel, "year": year, "reference_state": state,
            "validity": validity(invalid), "morphology": morph(morphology),
            "dominance": dom(nondom)}


def six_year_records():
    rows = []
    for year in c.YEARS:
        rows.extend([
            rec(f"{year}-s", year, c.SUPPORTED, "turn"),
            rec(f"{year}-d", year, c.DEVELOPING, "leg"),
            rec(f"{year}-nt", year, c.NOT_DOMINANT, "turn", nondom=True),
            rec(f"{year}-nd", year, c.NOT_DOMINANT, "leg", nondom=True),
            rec(f"{year}-i", year, c.DATA_INVALID, "other", invalid=True),
            rec(f"{year}-a", year, c.AMBIGUOUS, "other"),
        ])
    return rows


class CalibrationTests(unittest.TestCase):
    def test_amplitude_is_not_a_calibration_feature(self):
        self.assertNotIn("amplitude", " ".join(c.VALIDITY_DIRECTIONS).lower())
        self.assertNotIn("amplitude", " ".join(c.DOMINANCE_DIRECTIONS).lower())

    def test_validity_rule_detects_without_false_rejection(self):
        rows = six_year_records()
        fit = c.fit_validity_rule(rows)
        self.assertEqual(fit["fit_status"], "FITTED")
        self.assertGreater(fit["metrics"]["recall"], 0)
        self.assertLessEqual(fit["metrics"]["false_positive_rate"], c.FALSE_REJECT_CAP)
        self.assertNotEqual(fit["rule_id"], "NULL")

    def test_validity_cap_overrides_more_aggressive_rule(self):
        rows = []
        for i in range(20):
            r = rec(f"n{i}", 2015, c.SUPPORTED, "turn")
            r["validity"]["close_jump_concentration"] = .10 + i * .01
            rows.append(r)
        for i, value in enumerate((.16, .17, .95, .96)):
            r = rec(f"i{i}", 2016, c.DATA_INVALID, "other", invalid=True)
            r["validity"]["close_jump_concentration"] = value
            rows.append(r)
        # Add remaining years without changing the relevant separation.
        for year in (2017, 2018, 2019, 2020):
            rows.append(rec(f"{year}s", year, c.SUPPORTED, "turn"))
            rows.append(rec(f"{year}i", year, c.DATA_INVALID, "other", invalid=True))
        fit = c.fit_validity_rule(rows)
        self.assertLessEqual(fit["metrics"]["false_positive_rate"], .05 + 1e-15)

    def test_missing_validity_evidence_is_uncertain(self):
        row = six_year_records()[0]
        fit = {"rule": {"op": "SINGLE", "conditions": [
            {"feature": "close_jump_concentration", "direction": "GE", "threshold": .5}
        ]}}
        row = copy.deepcopy(row); row["validity"]["close_jump_concentration"] = None
        self.assertEqual(c.predict_validity(row, fit), c.UNCERTAIN_VALIDITY)

    def test_morphology_objective_does_not_choose_all_abstain(self):
        rows = six_year_records()
        fit = c.fit_morphology_rule(rows)
        self.assertEqual(fit["fit_status"], "FITTED")
        self.assertGreater(fit["metrics"]["correct"], 0)
        self.assertLess(fit["metrics"]["ambiguity_rate"], 1.0)
        self.assertEqual(c.predict_morphology(rows[0], fit), c.TURNING)
        self.assertEqual(c.predict_morphology(rows[1], fit), c.DEVELOPING_LEG)

    def test_dominance_rule_respects_false_reject_cap(self):
        rows = six_year_records()
        fit = c.fit_dominance_rule(
            [r for r in rows if r["reference_state"] in {c.SUPPORTED, c.NOT_DOMINANT}
             and r["morphology"]["no_reversal_count"] == 0], c.TURNING)
        self.assertEqual(fit["fit_status"], "FITTED")
        self.assertGreater(fit["metrics"]["recall"], 0)
        self.assertLessEqual(fit["metrics"]["false_positive_rate"], c.FALSE_REJECT_CAP)

    def test_oof_predicts_each_panel_once(self):
        rows = six_year_records()
        out = c.fit_loyo(rows)
        self.assertEqual(len(out["predictions"]), len(rows))
        self.assertEqual(len({r["panel_id"] for r in out["predictions"]}), len(rows))
        self.assertEqual([f["held_year"] for f in out["fold_models"]], list(c.YEARS))
        self.assertFalse(out["production_authority"])

    def test_heldout_values_do_not_change_their_fold_fit(self):
        rows = six_year_records()
        base = c.fit_loyo(rows)
        altered = copy.deepcopy(rows)
        for r in altered:
            if r["year"] == 2018:
                r["validity"]["close_jump_concentration"] = 999.0
                r["dominance"]["tortuosity_median"] = 999.0
        changed = c.fit_loyo(altered)
        a = next(f for f in base["fold_models"] if f["held_year"] == 2018)
        b = next(f for f in changed["fold_models"] if f["held_year"] == 2018)
        self.assertEqual(a, b)

    def test_candidate_rules_use_at_most_two_features(self):
        fit = c.fit_validity_rule(six_year_records())
        self.assertLessEqual(len(fit["rule"]["conditions"]), 2)
        for fold in c.fit_loyo(six_year_records())["fold_models"]:
            for branch in (c.TURNING, c.DEVELOPING_LEG):
                self.assertLessEqual(len(fold["dominance"][branch]["rule"]["conditions"]), 2)

    def test_missing_year_is_rejected(self):
        rows = [r for r in six_year_records() if r["year"] != 2020]
        with self.assertRaisesRegex(ValueError, "year coverage"):
            c.fit_loyo(rows)

    def test_synthetic_pipeline_recovers_clear_states(self):
        out = c.fit_loyo(six_year_records())
        by = {p["panel_id"]: p for p in out["predictions"]}
        for year in c.YEARS:
            self.assertEqual(by[f"{year}-s"]["final_state"], c.SUPPORTED)
            self.assertEqual(by[f"{year}-d"]["final_state"], c.DEVELOPING)
            self.assertEqual(by[f"{year}-nt"]["final_state"], c.NOT_DOMINANT)
            self.assertEqual(by[f"{year}-nd"]["final_state"], c.NOT_DOMINANT)
            self.assertEqual(by[f"{year}-i"]["final_state"], c.DATA_INVALID)

    def test_module_has_no_file_network_or_random_access(self):
        text = (ROOT / "executor/wave_scale_state_conditional_calibration_v1.py").read_text()
        tree = ast.parse(text)
        forbidden_import_roots = {"pathlib", "os", "socket", "requests", "urllib", "random", "pandas"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(alias.name.split('.')[0] not in forbidden_import_roots for alias in node.names))
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split('.')[0], forbidden_import_roots)


if __name__ == "__main__":
    unittest.main()
