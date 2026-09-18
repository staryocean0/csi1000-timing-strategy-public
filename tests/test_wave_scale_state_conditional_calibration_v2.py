import ast
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'executor'))
import wave_scale_state_conditional_calibration_v2 as c
import wave_scale_state_conditional_calibration_v1 as v1


def validity(kind='valid'):
    base = {
        'local_jump_isolation_ratio': 3.0,
        'close_jump_concentration': .12,
        'close_range_concentration': .15,
        'post_jump_reversal_extreme_10': .05,
        'post_jump_midpoint_hold_fraction_10': .95,
        'signed_post_jump_displacement_ratio_10': 1.0,
        'signed_post_jump_displacement_ratio_20': 1.0,
        'jump_persistence_ratio': 1.0,
        'wick_only_concentration_max': .05,
        'wick_only_concentration_median': .04,
    }
    if kind == 'invalid':
        base.update(local_jump_isolation_ratio=20.0, close_jump_concentration=.75,
                    post_jump_reversal_extreme_10=1.4,
                    post_jump_midpoint_hold_fraction_10=.0,
                    signed_post_jump_displacement_ratio_10=-.3,
                    signed_post_jump_displacement_ratio_20=-.5,
                    jump_persistence_ratio=.05)
    elif kind == 'sustained_shift':
        base.update(local_jump_isolation_ratio=25.0, close_jump_concentration=.80,
                    post_jump_reversal_extreme_10=.0,
                    post_jump_midpoint_hold_fraction_10=1.0,
                    signed_post_jump_displacement_ratio_10=1.2,
                    signed_post_jump_displacement_ratio_20=1.3,
                    jump_persistence_ratio=1.2)
    return base


def morphology(score_kind):
    if score_kind == 'turn':
        return {'reversal_completion_ratio_median': .85,
                'delta_search_adjusted_bic_vs_one_leg_median': -50.0,
                'post_turn_fraction_median': .45,
                'turn_edge_distance_fraction_median': .30,
                'one_leg_background_count': 0}
    if score_kind == 'leg':
        return {'reversal_completion_ratio_median': .05,
                'delta_search_adjusted_bic_vs_one_leg_median': 5.0,
                'post_turn_fraction_median': .08,
                'turn_edge_distance_fraction_median': .05,
                'one_leg_background_count': 5}
    return {'reversal_completion_ratio_median': .40,
            'delta_search_adjusted_bic_vs_one_leg_median': -20.0,
            'post_turn_fraction_median': .22,
            'turn_edge_distance_fraction_median': .15,
            'one_leg_background_count': 2}


def dominance(nondom=False):
    return {'tortuosity_median': 8.0 if nondom else 2.0,
            'norm_rmse_median': .20 if nondom else .05,
            'delta_bic_median': 5.0 if nondom else -30.0,
            'sse_improvement_median': .10 if nondom else .65}


def rec(panel, year, state, morph, vkind='valid', nondom=False):
    return {'panel_id': panel, 'year': year, 'reference_state': state,
            'validity': validity(vkind), 'morphology': morphology(morph),
            'dominance': dominance(nondom)}


def records():
    out = []
    for year in c.YEARS:
        out.extend([
            rec(f'{year}-s', year, c.SUPPORTED, 'turn'),
            rec(f'{year}-d', year, c.DEVELOPING, 'leg'),
            rec(f'{year}-nt', year, c.NOT_DOMINANT, 'turn', nondom=True),
            rec(f'{year}-nd', year, c.NOT_DOMINANT, 'leg', nondom=True),
            rec(f'{year}-i', year, c.DATA_INVALID, 'mid', 'invalid'),
            rec(f'{year}-a', year, c.AMBIGUOUS, 'mid'),
        ])
    return out


class CalibrationV2Tests(unittest.TestCase):
    def test_validity_has_explicit_three_way_semantics(self):
        fit = c.fit_validity_guard(records())
        self.assertEqual(c.predict_validity(records()[0], fit), c.VALID)
        invalid = next(r for r in records() if r['reference_state'] == c.DATA_INVALID)
        self.assertEqual(c.predict_validity(invalid, fit), c.INVALID)
        row = copy.deepcopy(records()[0])
        for key in row['validity']:
            row['validity'][key] = None
        self.assertEqual(c.predict_validity(row, fit), c.UNCERTAIN_VALIDITY)

    def test_sustained_large_shift_is_not_invalid_by_jump_size_alone(self):
        rows = records()
        fit = c.fit_validity_guard(rows)
        row = copy.deepcopy(rows[0])
        row['validity'] = validity('sustained_shift')
        self.assertNotEqual(c.predict_validity(row, fit), c.INVALID)
        invalid_features = set(c.INVALID_SINGLE_DIRECTIONS)
        self.assertNotIn('local_jump_isolation_ratio', invalid_features)
        self.assertNotIn('close_jump_concentration', invalid_features)

    def test_morphology_band_has_two_non_crossing_boundaries_and_finite_ambiguity(self):
        fit = c.fit_morphology_band(records())
        rule = fit['rule']
        self.assertLess(rule['developing_boundary_score'], rule['turning_boundary_score'])
        self.assertEqual(c.predict_morphology(records()[0], fit), c.TURNING)
        self.assertEqual(c.predict_morphology(records()[1], fit), c.DEVELOPING_LEG)
        mid = copy.deepcopy(records()[0])
        axis = rule['axis']; sign = c.MORPHOLOGY_AXES[axis]
        score = (rule['developing_boundary_score'] + rule['turning_boundary_score']) / 2
        mid['morphology'][axis] = score / sign
        self.assertEqual(c.predict_morphology(mid, fit), c.MORPH_AMBIG)

    def test_raw_amplitude_is_not_a_calibration_axis(self):
        names = set(c.MORPHOLOGY_AXES) | set(c.INVALID_SINGLE_DIRECTIONS) | set(c.VALID_SINGLE_DIRECTIONS)
        self.assertFalse(any('amplitude' in name for name in names))

    def test_dominance_family_is_v1_control(self):
        rows = records()
        out = c.fit_loyo_development(rows)
        self.assertEqual(out['dominance_family'], 'V1_FROZEN_CONTROL_UNCHANGED')
        for fold in out['fold_models']:
            for branch in (c.TURNING, c.DEVELOPING_LEG):
                self.assertIn('rule_id', fold['dominance'][branch])

    def test_heldout_values_do_not_change_heldout_fold_model(self):
        rows = records()
        base = c.fit_loyo_development(rows)
        changed = copy.deepcopy(rows)
        for r in changed:
            if r['year'] == 2018:
                r['validity']['post_jump_reversal_extreme_10'] = 999.0
                r['morphology']['reversal_completion_ratio_median'] = 999.0
                r['dominance']['tortuosity_median'] = 999.0
        again = c.fit_loyo_development(changed)
        a = next(f for f in base['fold_models'] if f['held_year'] == 2018)
        b = next(f for f in again['fold_models'] if f['held_year'] == 2018)
        self.assertEqual(a, b)

    def test_loyo_is_development_only_and_never_full_fits(self):
        out = c.fit_loyo_development(records())
        self.assertEqual(len(out['predictions']), len(records()))
        self.assertEqual(out['population_role'], 'ITERATIVE_DEVELOPMENT_EVIDENCE_NOT_FRESH_OOS')
        self.assertFalse(out['full_192_fit_performed'])
        self.assertFalse(out['production_authority'])

    def test_module_has_no_file_network_random_or_pandas_access(self):
        text = (ROOT / 'executor/wave_scale_state_conditional_calibration_v2.py').read_text()
        tree = ast.parse(text)
        forbidden = {'pathlib', 'os', 'socket', 'requests', 'urllib', 'random', 'pandas', 'numpy'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(a.name.split('.')[0] not in forbidden for a in node.names))
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split('.')[0], forbidden)


if __name__ == '__main__':
    unittest.main()
