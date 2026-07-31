from unittest import TestCase

import pandas as pd

from src.sepe_supplement import add_missing_breakdowns, validate_supplement


class SepeSupplementTests(TestCase):
    def _supplement(self) -> pd.DataFrame:
        rows = []
        categories = {"gender": ["Hombre", "Mujer"], "age": ["<18", "18-24", "25-29", "30-39", "40-44", ">44"], "province": [f"P{i}" for i in range(52)]}
        for dimension, labels in categories.items():
            for index, label in enumerate(labels):
                rows.append({
                    "period": "2022-09", "cno4": "2220", "dimension": dimension,
                    "category": label, "gender": label if dimension == "gender" else "Total",
                    "contratos": 10 if index == 0 else 0,
                    "parados": 5 if index == 0 else 0, "personas": pd.NA, "source_url": "provider://test",
                })
        return pd.DataFrame(rows)

    def test_add_missing_breakdowns_is_idempotent_and_preserves_total(self):
        base = pd.DataFrame([{
            "period": "2022-09", "cno4": "2220", "occupation_title": "Profesores",
            "dimension": "total", "category": "Total", "gender": "Total", "source_url": "cache://report",
            "contratos": 10, "parados": 5, "personas": 9,
        }])
        supplement = self._supplement()
        validate_supplement(supplement)

        completed = add_missing_breakdowns(base, supplement)
        repeated = add_missing_breakdowns(completed, supplement)

        self.assertEqual(len(completed), 61)
        self.assertEqual(len(repeated), 61)
        self.assertEqual(completed.iloc[0]["personas"], 9)

    def test_rejects_disagreeing_dimension_totals(self):
        supplement = self._supplement()
        supplement.loc[supplement["dimension"] == "age", "contratos"] = 1
        with self.assertRaises(ValueError):
            validate_supplement(supplement)
