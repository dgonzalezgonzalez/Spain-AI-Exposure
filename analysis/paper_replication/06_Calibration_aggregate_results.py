"""Stage 06: aggregate unemployment calibration from micro AI exposure.

Exact calibration logic:

For occupation j in month t, let U_obs_jt be observed registered unemployment,
A_j the observed AI exposure in [0, 1], and beta_p the TWFE coefficient for the
post-treatment phase p(t). The paper estimates:

    log(U_obs_jt) = log(U_no_ai_jt) + beta_p * (A_j / 0.10)

so the no-AI counterfactual is:

    U_no_ai_jt = U_obs_jt / exp(beta_p * (A_j / 0.10))

and the implied AI-related unemployment gap is:

    gap_jt = U_obs_jt - U_no_ai_jt

This stage applies that formula occupation by occupation using the observed
exposure_nearest for each CNO4, then aggregates the implied gap to the national
monthly level.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PHASE_WINDOWS = {
    "adjustment": (0, 24),
    "later": (25, 40),
}

CALIBRATION_SPECS = (
    ("Benchmark TWFE", "twfe_phase_benchmark_twfe_ln_parados.csv"),
    ("Preferred within-CNO1 TWFE", "twfe_phase_preferred_cno1_month_ln_parados.csv"),
)


def discover_project_root() -> Path:
    here = Path(__file__).resolve().parent
    direct_candidate = here
    runtime_candidate = here / "runtime"

    for candidate in (direct_candidate, runtime_candidate):
        if (candidate / "data" / "prepared").is_dir() and (candidate / "intermediate").is_dir():
            return candidate

    candidate = Path.cwd().resolve()
    while candidate != candidate.parent:
        if (candidate / "data" / "prepared").is_dir() and (candidate / "intermediate").is_dir():
            return candidate
        candidate = candidate.parent
    raise FileNotFoundError("Could not locate the replication runtime folder with data/prepared and intermediate.")


PROJECT_ROOT = discover_project_root()
PREPARED_DIR = PROJECT_ROOT / "data" / "prepared"
INTERMEDIATE_DIR = PROJECT_ROOT / "intermediate"
FINAL_DIR = PROJECT_ROOT / "figuresNtables"

for directory in (INTERMEDIATE_DIR, FINAL_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def require(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return path


def phase_from_event_time(event_time: pd.Series) -> pd.Series:
    return np.where(event_time <= PHASE_WINDOWS["adjustment"][1], "adjustment", "later")


def load_panel() -> pd.DataFrame:
    panel = pd.read_csv(
        require(PREPARED_DIR / "est_total_cno4.csv"),
        dtype={"cno4": str, "cno2": str, "cno1d": str},
    )
    panel.columns = [column.lower() for column in panel.columns]

    numeric_columns = ["event_time_nov2022", "ym_stata", "parados", "exposure_nearest"]
    for column in numeric_columns:
        panel[column] = pd.to_numeric(panel[column], errors="coerce")

    panel["cno4"] = panel["cno4"].astype(str).str.strip().str.zfill(4)
    panel = panel.dropna(subset=["event_time_nov2022", "parados", "exposure_nearest"]).copy()
    panel = panel.loc[panel["event_time_nov2022"].between(0, 40)].copy()
    panel["phase"] = phase_from_event_time(panel["event_time_nov2022"])
    return panel


def load_coefficients() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for label, filename in CALIBRATION_SPECS:
        frame = pd.read_csv(require(INTERMEDIATE_DIR / filename))
        frame = frame.loc[frame["phase"].isin(PHASE_WINDOWS)].copy()
        if frame.empty:
            raise ValueError(f"No usable phase coefficients found in {filename}.")
        frame["calibration_spec"] = label
        frames.append(frame[["calibration_spec", "phase", "estimate", "se", "effect_percent"]])

    coefficients = pd.concat(frames, ignore_index=True)
    coefficients = coefficients.sort_values(["calibration_spec", "phase"]).reset_index(drop=True)
    coefficients.to_csv(INTERMEDIATE_DIR / "calibration_phase_coefficients_v1.csv", index=False)
    return coefficients


def apply_micro_calibration(panel: pd.DataFrame, coefficients: pd.DataFrame) -> pd.DataFrame:
    calibrated_frames: list[pd.DataFrame] = []

    for specification, beta_frame in coefficients.groupby("calibration_spec", sort=False):
        phase_betas = beta_frame.set_index("phase")["estimate"].to_dict()
        if set(phase_betas) != set(PHASE_WINDOWS):
            raise ValueError(f"{specification} is missing one of the required post-treatment phase coefficients.")

        calibrated = panel.copy()
        calibrated["calibration_spec"] = specification
        calibrated["beta_phase"] = calibrated["phase"].map(phase_betas)
        calibrated["exposure_real"] = calibrated["exposure_nearest"]
        calibrated["exposure_10pp_units"] = calibrated["exposure_real"] / 0.10
        calibrated["log_shift_ai"] = calibrated["beta_phase"] * calibrated["exposure_10pp_units"]
        calibrated["counterfactual_parados_no_ai"] = calibrated["parados"] / np.exp(calibrated["log_shift_ai"])
        calibrated["ai_extra_parados"] = calibrated["parados"] - calibrated["counterfactual_parados_no_ai"]
        calibrated_frames.append(calibrated)

    calibrated_panel = pd.concat(calibrated_frames, ignore_index=True)
    return calibrated_panel


def aggregate_monthly(calibrated_panel: pd.DataFrame) -> pd.DataFrame:
    monthly = (
        calibrated_panel.groupby(
            ["calibration_spec", "phase", "ym_stata", "period", "event_time_nov2022"], as_index=False
        )
        .agg(
            observed_parados=("parados", "sum"),
            counterfactual_parados_no_ai=("counterfactual_parados_no_ai", "sum"),
            ai_extra_parados=("ai_extra_parados", "sum"),
            mean_exposure_real=("exposure_real", "mean"),
            occupations=("cno4", "nunique"),
        )
        .sort_values(["calibration_spec", "ym_stata"])
        .reset_index(drop=True)
    )
    monthly["ai_extra_share_pct"] = 100 * monthly["ai_extra_parados"] / monthly["observed_parados"]
    monthly.to_csv(INTERMEDIATE_DIR / "calibration_aggregate_monthly_v1.csv", index=False)
    return monthly


def summarize_window(monthly: pd.DataFrame, specification: str, window: str, phase: str | None) -> dict[str, object]:
    subset = monthly.loc[monthly["calibration_spec"] == specification].copy()
    if phase is not None:
        subset = subset.loc[subset["phase"] == phase].copy()

    return {
        "calibration_spec": specification,
        "window": window,
        "months": int(subset["period"].nunique()),
        "first_period": subset["period"].min(),
        "last_period": subset["period"].max(),
        "avg_monthly_observed_parados": subset["observed_parados"].mean(),
        "avg_monthly_counterfactual_parados_no_ai": subset["counterfactual_parados_no_ai"].mean(),
        "avg_monthly_ai_extra_parados": subset["ai_extra_parados"].mean(),
        "total_ai_extra_person_months": subset["ai_extra_parados"].sum(),
        "ai_extra_share_pct": 100 * subset["ai_extra_parados"].sum() / subset["observed_parados"].sum(),
    }


def build_summary(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for specification in monthly["calibration_spec"].drop_duplicates():
        rows.append(summarize_window(monthly, specification, "adjustment_0_24", "adjustment"))
        rows.append(summarize_window(monthly, specification, "later_25_40", "later"))
        rows.append(summarize_window(monthly, specification, "post_0_40", None))

    summary = pd.DataFrame(rows)
    order = {
        "adjustment_0_24": 0,
        "later_25_40": 1,
        "post_0_40": 2,
    }
    summary["window_order"] = summary["window"].map(order)
    summary = summary.sort_values(["calibration_spec", "window_order"]).drop(columns="window_order").reset_index(drop=True)
    summary.to_csv(INTERMEDIATE_DIR / "calibration_aggregate_summary_v1.csv", index=False)
    return summary


def fmt_count(value: float) -> str:
    return f"{value:,.0f}"


def fmt_pct(value: float) -> str:
    return f"{value:.2f}"


def build_latex_table(summary: pd.DataFrame) -> str:
    window_labels = {
        "adjustment_0_24": "Adjustment (0--24)",
        "later_25_40": "Later (25--40)",
        "post_0_40": "Full post (0--40)",
    }
    lines = [
        r"\begin{table}[!htbp]",
        r"\centering",
        r"\caption{Aggregate unemployment calibration using occupation-level AI exposure}",
        r"\label{tab:v1_calibration_aggregate}",
        r"\begin{threeparttable}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Specification & Window & Avg. observed & Avg. no-AI counterfactual & Avg. AI-related extra & Extra share (\%) \\",
        r"\midrule",
    ]

    for row in summary.itertuples(index=False):
        lines.append(
            f"{row.calibration_spec} & "
            f"{window_labels[row.window]} & "
            f"{fmt_count(row.avg_monthly_observed_parados)} & "
            f"{fmt_count(row.avg_monthly_counterfactual_parados_no_ai)} & "
            f"{fmt_count(row.avg_monthly_ai_extra_parados)} & "
            f"{fmt_pct(row.ai_extra_share_pct)} \\\\"
        )

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\begin{tablenotes}[flushleft]",
            r"\footnotesize",
            r"\item \emph{Notes:} The table applies the unemployment TWFE coefficients to each CNO4 occupation's observed AI exposure rather than to a uniform 10 percentage-point shock. For occupation $j$ in month $t$, the no-AI counterfactual is $U_{jt}^{0}=U_{jt}^{obs}/\exp(\beta_{p(t)} A_j/0.10)$, where $A_j$ is the observed exposure and $\beta_{p(t)}$ is the phase-specific post-treatment coefficient. The reported gap is the difference between observed unemployment and that counterfactual, aggregated across occupations within each month and then averaged over the indicated window.",
            r"\end{tablenotes}",
            r"\end{threeparttable}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    panel = load_panel()
    coefficients = load_coefficients()
    calibrated_panel = apply_micro_calibration(panel, coefficients)
    monthly = aggregate_monthly(calibrated_panel)
    summary = build_summary(monthly)

    latex_table = build_latex_table(summary)
    (FINAL_DIR / "calibration_aggregate_results_v1.tex").write_text(latex_table, encoding="utf-8")

    print("Aggregate micro calibration completed.")
    print()
    print("Formula used:")
    print("U_no_ai_jt = U_obs_jt / exp(beta_phase * exposure_real_j / 0.10)")
    print("gap_jt = U_obs_jt - U_no_ai_jt")
    print()

    primary = summary.loc[
        (summary["calibration_spec"] == "Benchmark TWFE") & (summary["window"] == "adjustment_0_24")
    ].iloc[0]
    full_post = summary.loc[
        (summary["calibration_spec"] == "Benchmark TWFE") & (summary["window"] == "post_0_40")
    ].iloc[0]
    preferred = summary.loc[
        (summary["calibration_spec"] == "Preferred within-CNO1 TWFE") & (summary["window"] == "post_0_40")
    ].iloc[0]

    print("Benchmark TWFE, adjustment period (event times 0-24):")
    print(f"  Average monthly observed unemployed: {fmt_count(primary['avg_monthly_observed_parados'])}")
    print(f"  Average monthly no-AI counterfactual: {fmt_count(primary['avg_monthly_counterfactual_parados_no_ai'])}")
    print(f"  Average monthly AI-related extra unemployed: {fmt_count(primary['avg_monthly_ai_extra_parados'])}")
    print(f"  Total AI-related extra unemployment (person-months): {fmt_count(primary['total_ai_extra_person_months'])}")
    print(f"  AI-related share of observed unemployment: {fmt_pct(primary['ai_extra_share_pct'])}%")
    print()
    print("Benchmark TWFE, full post period (event times 0-40):")
    print(f"  Average monthly AI-related extra unemployed: {fmt_count(full_post['avg_monthly_ai_extra_parados'])}")
    print(f"  Total AI-related extra unemployment (person-months): {fmt_count(full_post['total_ai_extra_person_months'])}")
    print(f"  AI-related share of observed unemployment: {fmt_pct(full_post['ai_extra_share_pct'])}%")
    print()
    print("Preferred within-CNO1 TWFE, full post period (event times 0-40):")
    print(f"  Average monthly AI-related extra unemployed: {fmt_count(preferred['avg_monthly_ai_extra_parados'])}")
    print(f"  Total AI-related extra unemployment (person-months): {fmt_count(preferred['total_ai_extra_person_months'])}")
    print(f"  AI-related share of observed unemployment: {fmt_pct(preferred['ai_extra_share_pct'])}%")


if __name__ == "__main__":
    main()
