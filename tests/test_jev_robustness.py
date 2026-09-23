from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis" / "paper_replication"))

from lib.jev_robustness import (
    build_exposure_correlation_matrix,
    build_jev_robustness_outputs,
    prepare_jev_panel,
)


class JevRobustnessTests(unittest.TestCase):
    def test_builds_jev_table_and_six_event_study_figures(self) -> None:
        root = ROOT / "analysis" / "paper_replication" / "runtime" / "test_artifacts" / "jev_outputs_unit_test"
        estimates_dir = root / "intermediate"
        output_dir = root / "figuresNtables"
        estimates_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        measures = ["", "nearest", "weighted", "direct"]
        for measure in measures:
            specs = (
                ("benchmark_twfe", "preferred_cno1_month", "preferred_cno1_month_no2021")
                if not measure
                else (
                    f"jev_{measure}_benchmark",
                    f"jev_{measure}_cno1_month",
                    f"jev_{measure}_cno1_month_no2021",
                )
            )
            for outcome in ("ln_parados", "ln_contratos"):
                for specification in specs:
                    pd.DataFrame(
                        [
                            {
                                "phase": phase,
                                "estimate": 0.02 if phase == "adjustment" else 0.01,
                                "se": 0.01,
                                "clusters": 400,
                                "equality_p": 0.42,
                                "observations": 502,
                            }
                            for phase in ("adjustment", "later")
                        ]
                    ).to_csv(estimates_dir / f"twfe_phase_{specification}_{outcome}.csv", index=False)
                    pretrend_window = "full_-10_-2" if specification.endswith("no2021") else "full_-21_-2"
                    pd.DataFrame(
                        [
                            {
                                "window": pretrend_window,
                                "test": "joint_equal_zero",
                                "p_value": 0.234,
                            }
                        ]
                    ).to_csv(
                        estimates_dir / f"twfe_pretrend_{specification}_{outcome}.csv",
                        index=False,
                    )
        event_times = list(range(-21, 41))
        event_frame = pd.DataFrame(
            {
                "event_time": event_times,
                "estimate": [0.0] * len(event_times),
                "ci_low": [-0.01] * len(event_times),
                "ci_high": [0.01] * len(event_times),
            }
        )
        for measure in ("nearest", "weighted", "direct"):
            for outcome in ("ln_parados", "ln_contratos"):
                event_frame.to_csv(
                    estimates_dir / f"twfe_event_jev_{measure}_cno1_month_{outcome}.csv",
                    index=False,
                )

        outputs = build_jev_robustness_outputs(estimates_dir, output_dir)
        table = Path(outputs["table"]).read_text(encoding="utf-8")
        self.assertIn("Panel A. Baseline specification", table)
        self.assertIn("Panel D. Jev: directly imputed observed exposure", table)
        self.assertNotIn("RF-relative", table)
        self.assertIn(r"AI exposure $\times$ adjustment period", table)
        self.assertIn(r"AI exposure $\times$ later period", table)
        self.assertIn(r"0.020$^{**}$", table)
        self.assertIn("2021 included & Yes & Yes & No & Yes & Yes & No", table)
        self.assertNotIn("Impact of a 10 pp increase", table)
        self.assertNotIn("CNO3", table)
        self.assertEqual(len([key for key in outputs if key not in {"table", "table_csv"}]), 6)
        self.assertTrue(all(Path(path).is_file() for key, path in outputs.items() if key not in {"table", "table_csv"}))

    def test_prepares_scaled_exposures_and_full_pairwise_matrix(self) -> None:
        root = ROOT / "analysis" / "paper_replication" / "runtime" / "test_artifacts" / "jev_robustness_unit_test"
        root.mkdir(parents=True, exist_ok=True)
        with self.subTest("temporary fixture"):
            prepared_dir = root / "data" / "prepared"
            processed_dir = root / "data" / "processed"
            raw_dir = root / "data" / "raw"
            output_dir = root / "figuresNtables"
            for directory in (prepared_dir, processed_dir, raw_dir):
                directory.mkdir(parents=True, exist_ok=True)

            panel_path = prepared_dir / "est_total_cno4.csv"
            pd.DataFrame(
                {
                    "cno4": ["0011", "0011", "0012", "0012", "0020", "0020"],
                    "period": ["2021-01", "2021-02"] * 3,
                    "exposure_nearest": [0.1, 0.1, 0.3, 0.3, 0.8, 0.8],
                    "exposure_weighted": [0.2, 0.2, 0.4, 0.4, 0.7, 0.7],
                }
            ).to_csv(panel_path, index=False)
            jev_path = processed_dir / "occupation_estimates.csv"
            pd.DataFrame(
                {
                    "cno4": ["0011", "0012", "0020"],
                    "observed_exposure_jev_nearest": [0.1, 0.5, 0.9],
                    "observed_exposure_jev_weighted": [0.2, 0.4, 0.8],
                    "observed_exposure_jev_direct": [0.3, 0.2, 0.6],
                }
            ).to_csv(jev_path, index=False)
            jev_panel_path = prepared_dir / "est_total_cno4_jev.csv"
            summary = prepare_jev_panel(panel_path, jev_path, jev_panel_path)
            self.assertEqual(summary, {"panel_rows": 6, "occupations": 3, "months": 2})
            jev_panel = pd.read_csv(jev_panel_path, dtype={"cno4": str})
            self.assertAlmostEqual(jev_panel.loc[0, "exposure_jev_nearest_10pp"], 1.0)
            self.assertAlmostEqual(jev_panel.loc[2, "exposure_jev_weighted_10pp"], 4.0)

            pd.DataFrame(
                {
                    "CNO4": ["0011", "0012", "0020"],
                    "anthropic_occ_code": ["11-1011", "11-1021", "11-2011"],
                }
            ).to_csv(processed_dir / "spanish_occupation_matches_cosine_nearest.csv", index=False)
            bls_path = raw_dir / "bls_ai_exposure_categories_2025_35.xlsx"
            with pd.ExcelWriter(bls_path) as writer:
                pd.DataFrame(
                    {
                        "2025 National Employment Matrix code": ["11-1011", "11-1021", "11-2011"],
                        "Relative AI exposure": ["Low", "High", "Very high"],
                    }
                ).to_excel(writer, sheet_name="AI Exposure Categories", startrow=1, index=False)
            frs_path = raw_dir / "felten_raj_seamans_language_modeling_aioe.xlsx"
            with pd.ExcelWriter(frs_path) as writer:
                pd.DataFrame(
                    {
                        "SOC Code": ["11-1011", "11-1021", "11-2011"],
                        "Language Modeling AIOE": [0.1, 0.3, 0.2],
                    }
                ).to_excel(writer, sheet_name="LM AIOE", index=False)

            result = build_exposure_correlation_matrix(
                project_root=root,
                prepared_panel=jev_panel_path,
                jev_estimates=jev_path,
                output_dir=output_dir,
                bls_workbook=bls_path,
                frs_workbook=frs_path,
            )
            self.assertEqual(result["bls_occupations"], 3)
            self.assertEqual(result["frs_lm_aioe_occupations"], 3)
            self.assertTrue(Path(result["figure"]).is_file())
            correlations = pd.read_csv(output_dir / "exposure_measure_spearman_correlations_v1.csv")
            self.assertEqual(len(correlations), 7)


if __name__ == "__main__":
    unittest.main()
