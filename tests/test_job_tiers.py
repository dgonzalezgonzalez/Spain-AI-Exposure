from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis/paper_replication"))
from lib.job_tiers import build_job_tier_outputs


class PooledTierTests(unittest.TestCase):
    def make_results(self, directory: Path) -> None:
        for outcome in ("ln_parados", "ln_contratos"):
            for suffix in ("benchmark", "cno1_month", "cno1_month_no2021"):
                spec = f"jev_tiers_{suffix}"
                rows = [dict(specification=spec, outcome=outcome, tier=tier, control_group="tiers_2_3",
                             phase=phase, estimate=-tier * .03, se=.01,
                             observations=600, clusters=30, equality_p=.12)
                        for tier in (1,) for phase in ("adjustment", "later")]
                pd.DataFrame(rows).to_csv(directory / f"twfe_tier_phase_{spec}_{outcome}.csv", index=False)
                pd.DataFrame([dict(p_value=.2, control_group="tiers_2_3", observations=600, clusters=30)]).to_csv(
                    directory / f"twfe_tier_pretrend_{spec}_{outcome}.csv", index=False)
            events = [dict(tier=tier, control_group="tiers_2_3", event_time=k, estimate=0 if k == -1 else -tier * .03,
                           ci_low=0 if k == -1 else -tier * .03-.02,
                           ci_high=0 if k == -1 else -tier * .03+.02)
                      for tier in (1,) for k in range(-21, 41)]
            pd.DataFrame(events).to_csv(directory / f"twfe_tier_event_jev_tiers_cno1_month_{outcome}.csv", index=False)

    def test_pooled_path_keeps_log_point_scale_and_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.make_results(directory)
            with patch("lib.job_tiers._render_event_file") as render:
                outputs = build_job_tier_outputs(directory, directory / "outputs")
            self.assertEqual(render.call_count, 2)
            table = outputs["table"].read_text(encoding="utf-8")
            self.assertNotIn("Panel", table)
            self.assertIn("CNO1 $\\times$ year-month FE & No & Yes & Yes", table)
            self.assertIn("tiers 2 and 3 form the pooled control group", table)
            self.assertNotIn("Tier 2 $", table)
            for tier in (1,):
                for phase in ("adjustment", "later"):
                    self.assertEqual(table.count(f"Tier {tier} $\\times$ {phase} period"), 1)
                frame = pd.read_csv(directory / f"outputs/JobTiers_unemployed_jev_tier{tier}.csv")
                self.assertEqual(frame.loc[frame.event_time.eq(-1), "estimate"].iloc[0], 0)
                self.assertAlmostEqual(frame.loc[frame.event_time.eq(0), "estimate"].iloc[0], -tier * .03)

    def test_rejects_inconsistent_sample_and_duplicate_cells(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.make_results(directory)
            path = directory / "twfe_tier_phase_jev_tiers_benchmark_ln_parados.csv"
            original = pd.read_csv(path)
            invalid = original.copy()
            invalid.loc[0, "observations"] = 100
            invalid.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "inconsistent observations"):
                build_job_tier_outputs(directory, directory / "outputs")
            invalid = original.copy()
            invalid.loc[0, "tier"] = 2
            invalid.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "two unique coefficients"):
                build_job_tier_outputs(directory, directory / "outputs")

    def test_rejects_stale_comparison_group(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.make_results(directory)
            for prefix in ("phase", "pretrend", "event"):
                self.make_results(directory)
                path = directory / f"twfe_tier_{prefix}_jev_tiers_cno1_month_ln_parados.csv"
                frame = pd.read_csv(path)
                frame["control_group"] = "tier_3"
                frame.to_csv(path, index=False)
                with self.assertRaisesRegex(ValueError, "pooled tiers 2 and 3"):
                    build_job_tier_outputs(directory, directory / "outputs")

    def test_rejects_phase_event_sample_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.make_results(directory)
            path = directory / "twfe_tier_pretrend_jev_tiers_benchmark_ln_parados.csv"
            frame = pd.read_csv(path)
            frame["observations"] = 599
            frame.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "Phase and event regressions have inconsistent observations"):
                build_job_tier_outputs(directory, directory / "outputs")


if __name__ == "__main__":
    unittest.main()
