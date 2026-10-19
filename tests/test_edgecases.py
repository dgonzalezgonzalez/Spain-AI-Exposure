from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
from lib.edgecase_replay import resolve_matches
from lib.edgecase_validation import within_fit


class CompleteCrosswalkTests(unittest.TestCase):
    def setUp(self):
        self.baseline = pd.DataFrame({
            'cno4': ['1000', '2000'], 'spanish_title': ['A', 'B'],
            'anthropic_occ_code': ['11-1000', '22-1000'],
        }).set_index('cno4')
        self.catalogue = pd.DataFrame({
            'code': ['11-1000', '22-1000', '33-1000'],
            'title': ['First', 'Second', 'Third'], 'observed_exposure': [.1, .2, .3],
        }).set_index('code')
        self.answers = {'1000': {'code': '33-1000', 'approximate': False, 'reason': 'Core work'}}

    def test_inclusive_gate_and_unflagged_preservation(self):
        result = resolve_matches(self.baseline, {'1000': .5, '2000': .499}, self.answers,
                                 self.catalogue, {}).set_index('cno4')
        self.assertEqual(result.loc['1000', 'final_code'], '33-1000')
        self.assertEqual(result.loc['2000', 'final_code'], '22-1000')
        self.assertFalse(result.exposure_edgecases.isna().any())

    def test_abstention_or_incomplete_review_cannot_silently_create_missing_values(self):
        with self.assertRaises(ValueError):
            resolve_matches(self.baseline, {'1000': .8, '2000': .2}, {}, self.catalogue, {})
        self.answers['1000']['code'] = None
        with self.assertRaises(ValueError):
            resolve_matches(self.baseline, {'1000': .8, '2000': .2}, self.answers, self.catalogue, {})

    def test_manual_false_negative_correction_is_explicit_and_uses_catalogue_exposure(self):
        result = resolve_matches(self.baseline, {'1000': .8, '2000': .2}, self.answers,
                                 self.catalogue, {'2000': '33-1000'}).set_index('cno4')
        self.assertTrue(result.loc['2000', 'manual_override'])
        self.assertEqual(result.loc['2000', 'exposure_edgecases'], .3)
        with self.assertRaises(ValueError):
            resolve_matches(self.baseline, {'1000': .8, '2000': .2}, self.answers,
                            self.catalogue, {'2000': 'unknown'})

    def test_independent_absorption_recovers_known_phase_slopes(self):
        rows = []
        for unit in range(8):
            for month in [-3, -2, -1, 0, 1, 25, 26]:
                dose = unit / 7
                value = unit * .2 + month * .01 + dose * (.12 if 0 <= month <= 24 else .34 if month >= 25 else 0)
                rows.append({'cno4': f'1{unit:03}', 'period': str(month), 'event_time': month,
                             'dose': dose, 'outcome': value})
        beta, _, nobs = within_fit(pd.DataFrame(rows), 'outcome', 'dose', True)
        np.testing.assert_allclose(beta, [.12, .34], atol=1e-10)
        self.assertEqual(nobs, len(rows))


if __name__ == '__main__':
    unittest.main()
