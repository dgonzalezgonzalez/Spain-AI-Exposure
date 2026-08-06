"""Build the phase-based paper tables and final robustness figures for V1."""

from __future__ import annotations

from pathlib import Path
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from scipy.stats import t as student_t
except ImportError:  # The packaged runtime may not include SciPy.
    student_t = None


NAVY = "#08519C"
SKY = "#56B4E9"
GREY = "#777777"


def _write_tex(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _phase_pair(tables_dir: Path, specification: str, outcome: str) -> dict[str, pd.Series]:
    path = tables_dir / f"twfe_phase_{specification}_{outcome}.csv"
    frame = pd.read_csv(path)
    if set(frame["phase"]) != {"adjustment", "later"}:
        raise ValueError(f"Unexpected phase rows in {path}")
    return {row.phase: pd.Series(row._asdict()) for row in frame.itertuples(index=False)}


def _p_value(row: pd.Series) -> float:
    if not np.isfinite(row.se) or row.se <= 0:
        return np.nan
    degrees = max(int(row.clusters) - 1, 1)
    statistic = abs(float(row.estimate / row.se))
    if student_t is not None:
        return float(2 * student_t.sf(statistic, degrees))
    # With the project's cluster counts, the normal approximation is highly
    # accurate and keeps the package runnable in a minimal Python runtime.
    return float(math.erfc(statistic / math.sqrt(2)))


def _coefficient(row: pd.Series) -> str:
    p_value = _p_value(row)
    stars = ""
    if p_value < 0.01:
        stars = r"$^{***}$"
    elif p_value < 0.05:
        stars = r"$^{**}$"
    elif p_value < 0.10:
        stars = r"$^{*}$"
    return f"{float(row.estimate):.3f}{stars}"


def _standard_error(row: pd.Series) -> str:
    return f"({float(row.se):.3f})"


def _impact(row: pd.Series) -> str:
    return f"{100 * float(row.estimate):.1f}"


def _p_equal(pair: dict[str, pd.Series]) -> str:
    return f"{float(pair['adjustment'].equality_p):.3f}"


def _phase_block(label: str, columns: list[dict[str, pd.Series]]) -> list[str]:
    rows = [
        f"{label} $\\times$ adjustment period & "
        + " & ".join(_coefficient(column["adjustment"]) for column in columns)
        + r" \\",
        " & "
        + " & ".join(_standard_error(column["adjustment"]) for column in columns)
        + r" \\",
        "Impact of a 10 pp increase (percent) & "
        + " & ".join(_impact(column["adjustment"]) for column in columns)
        + r" \\",
        r"\addlinespace",
        f"{label} $\\times$ later period & "
        + " & ".join(_coefficient(column["later"]) for column in columns)
        + r" \\",
        " & "
        + " & ".join(_standard_error(column["later"]) for column in columns)
        + r" \\",
        "Impact of a 10 pp increase (percent) & "
        + " & ".join(_impact(column["later"]) for column in columns)
        + r" \\",
        "$p$-value: equal phase effects & "
        + " & ".join(_p_equal(column) for column in columns)
        + r" \\",
    ]
    return rows


def _six_column_table(
    tables_dir: Path,
    filename: str,
    caption: str,
    label: str,
    columns: list[dict[str, pd.Series]],
    treatment_label: str,
    notes: str,
    extra_rows: list[str] | None = None,
) -> None:
    extra_rows = extra_rows or []
    lines = [
        r"\begin{table}[!htbp]",
        r"\centering",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        r"\begin{threeparttable}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3.5pt}",
        r"\begin{tabular}{lcccccc}",
        r"\toprule",
        r"& \multicolumn{3}{c}{\# of registered unemployed} & \multicolumn{3}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
        r"& (1) & (2) & (3) & (4) & (5) & (6) \\",
        r"\midrule",
        *_phase_block(treatment_label, columns),
        r"\midrule",
        *extra_rows,
        "Observations & "
        + " & ".join(f"{int(column['adjustment'].observations):,}" for column in columns)
        + r" \\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\begin{tablenotes}[flushleft]",
        r"\footnotesize",
        rf"\item \emph{{Notes:}} {notes}",
        r"\end{tablenotes}",
        r"\end{threeparttable}",
        r"\end{table}",
    ]
    _write_tex(tables_dir / filename, lines)


def _render_event(
    source: Path,
    destination: Path,
    ylim: tuple[float, float],
    step: float,
) -> None:
    frame = pd.read_csv(source).sort_values("event_time")
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    ax.axhline(0, color=GREY, linewidth=0.7)
    ax.axvline(0, color=GREY, linestyle="--", linewidth=0.8)
    ax.fill_between(
        frame["event_time"].astype(float),
        frame["ci_low"].astype(float),
        frame["ci_high"].astype(float),
        color=SKY,
        alpha=0.25,
        linewidth=0,
    )
    ax.plot(frame["event_time"], frame["estimate"], color=NAVY, linewidth=1.25)
    ax.scatter(frame["event_time"], frame["estimate"], color=NAVY, s=9, zorder=3)
    ax.set_xlim(-21, 40)
    ax.set_ylim(*ylim)
    ax.set_yticks(np.arange(ylim[0], ylim[1] + step / 2, step))
    ax.set_xticks(np.arange(-20, 41, 10))
    ax.set_xlabel("Months relative to November 2022")
    ax.set_ylabel("Estimate")
    fig.tight_layout()
    fig.savefig(destination, bbox_inches="tight", dpi=220)
    plt.close(fig)


def _derive_contdid_phase(
    tables_dir: Path,
    specification: str,
    outcome: str,
) -> dict[str, pd.Series]:
    event_path = tables_dir / f"contdid_event_{specification}_{outcome}.csv"
    covariance_path = tables_dir / f"contdid_covariance_{specification}_{outcome}.csv"
    event = pd.read_csv(event_path).sort_values("event_time").reset_index(drop=True)
    covariance_frame = pd.read_csv(covariance_path).sort_values("event_time")
    covariance = covariance_frame.filter(regex=r"^cov_").to_numpy(dtype=float)
    if covariance.shape != (len(event), len(event)):
        raise ValueError(f"Covariance dimensions do not match {event_path.name}")

    weights = {}
    for phase, start, end in [("adjustment", 0, 24), ("later", 25, 40)]:
        index = np.where(event["event_time"].between(start, end))[0]
        if len(index) != end - start + 1:
            raise ValueError(f"Incomplete {phase} window in {event_path.name}")
        vector = np.zeros(len(event))
        vector[index] = 1 / len(index)
        weights[phase] = vector

    difference_weights = weights["adjustment"] - weights["later"]
    difference = float(difference_weights @ event["estimate"].to_numpy())
    difference_se = math.sqrt(float(difference_weights @ covariance @ difference_weights))
    equality_statistic = abs(difference / difference_se)
    if student_t is not None:
        equality_p = 2 * student_t.sf(equality_statistic, max(len(event) - 1, 1))
    else:
        equality_p = math.erfc(equality_statistic / math.sqrt(2))

    average_path = tables_dir / f"contdid_average_{specification}_{outcome}.csv"
    average = pd.read_csv(average_path)
    if "observations" in average and pd.notna(average.loc[0, "observations"]):
        observations = int(average.loc[0, "observations"])
    else:
        family_path = tables_dir / f"contdid_family_estimates_{specification}_{outcome}.csv"
        family = pd.read_csv(family_path)
        observations = int(family["units"].sum() * 63)

    output = {}
    for phase, start, end in [("adjustment", 0, 24), ("later", 25, 40)]:
        vector = weights[phase]
        estimate = float(vector @ event["estimate"].to_numpy())
        standard_error = math.sqrt(float(vector @ covariance @ vector))
        output[phase] = pd.Series(
            {
                "estimate": estimate,
                "se": standard_error,
                "equality_p": equality_p,
                "observations": observations,
                "clusters": 100000,
                "event_start": start,
                "event_end": end,
            }
        )
    return output


def _pretrend_p_value(
    tables_dir: Path,
    specification: str,
    outcome: str,
    window: str,
    test: str,
) -> float:
    path = tables_dir / f"twfe_pretrend_{specification}_{outcome}.csv"
    frame = pd.read_csv(path)
    row = frame.loc[(frame["window"] == window) & (frame["test"] == test)]
    if len(row) != 1:
        raise ValueError(
            f"Expected one {window}/{test} row in {path}; found {len(row)}"
        )
    return float(row.iloc[0]["p_value"])


def _format_pretrend_p(value: float) -> str:
    return r"$<0.001$" if value < 0.001 else f"{value:.3f}"


def _build_robustness_pretrend_table(tables_dir: Path) -> None:
    panels = [
        (
            "Panel A. Baseline specification",
            ("benchmark_twfe", "preferred_cno1_month", "preferred_cno1_month_cluster_cno3"),
            ("ln_parados", "ln_contratos"),
        ),
        (
            "Panel B. Alternative outcomes: log(Y+1)",
            ("benchmark_log_plus_one", "log_plus_one_cno1_month", "log_plus_one_cno1_month_cluster_cno3"),
            ("ln_parados_p1", "ln_contratos_p1"),
        ),
        (
            "Panel C. Alternative exposure: cosine-weighted",
            ("benchmark_cosine_weighted", "cosine_weighted_cno1_month", "cosine_weighted_cno1_month_cluster_cno3"),
            ("ln_parados", "ln_contratos"),
        ),
        (
            "Panel D. Alternative exposure: RF-relative",
            ("benchmark_rf_relative", "rf_relative_cno1_month", "rf_relative_cno1_month_cluster_cno3"),
            ("ln_parados", "ln_contratos"),
        ),
    ]
    windows = [
        ("Full: -21 to -2", "full_-21_-2"),
        ("Early: -21 to -10", "early_-21_-10"),
        ("Recent: -10 to -2", "recent_-10_-2"),
    ]
    tests = ("joint_equal_zero", "joint_equal_coefficients")
    outcome_labels = ("Registered unemployed", "New contracts")

    lines = [
        r"\begin{landscape}",
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Pre-treatment diagnostics for alternative outcomes and exposure measures}",
        r"\label{tab:v1_robustness_pretrends}",
        r"\begin{threeparttable}",
        r"\scriptsize",
        r"\renewcommand{\arraystretch}{0.88}",
        r"\setlength{\tabcolsep}{3.0pt}",
        r"\begin{tabular}{@{}llcccccc@{}}",
        r"\toprule",
        r"& & \multicolumn{2}{c}{Benchmark: CNO4 clustering} & \multicolumn{2}{c}{CNO1-by-month: CNO4 clustering} & \multicolumn{2}{c}{CNO1-by-month: CNO3 clustering} \\",
        r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}",
        r"Outcome & Window & Nullity & Equality & Nullity & Equality & Nullity & Equality \\",
        r"\midrule",
    ]
    for panel_index, (panel, specifications, outcomes) in enumerate(panels):
        if panel_index:
            lines.append(r"\addlinespace")
        lines.append(rf"\multicolumn{{8}}{{l}}{{\textbf{{{panel}}}}} \\")
        for outcome_label, outcome in zip(outcome_labels, outcomes):
            for window_label, window in windows:
                values = []
                for specification in specifications:
                    values.extend(
                        _format_pretrend_p(
                            _pretrend_p_value(
                                tables_dir, specification, outcome, window, test
                            )
                        )
                        for test in tests
                    )
                lines.append(
                    f"{outcome_label} & {window_label} & "
                    + " & ".join(values)
                    + r" \\"
                )
    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\begin{tablenotes}[flushleft]",
        r"\scriptsize",
        r"\item \emph{Notes:} Entries are $p$-values from Wald tests of the pre-treatment event-study coefficients for the specifications reported in Table~\ref{tab:v1_robustness}. The nullity test evaluates whether all coefficients in the indicated window equal zero. The equality test evaluates whether they equal one another while allowing their common value to differ from zero. The benchmark includes CNO4 and year-month fixed effects. The other specifications include CNO4 and CNO1-by-year-month fixed effects, with standard errors clustered at the indicated occupational level. The full, early, and recent windows cover event times -21 to -2, -21 to -10, and -10 to -2; October 2022 (event time -1) is the omitted reference month.",
        r"\end{tablenotes}",
        r"\end{threeparttable}",
        r"\end{table}",
        r"\end{landscape}",
    ]
    _write_tex(tables_dir / "robustness_pretrend_diagnostics_v1.tex", lines)


def _sdid_phase_row(
    tables_dir: Path,
    specification: str,
    outcome: str,
    phase: str,
) -> pd.Series:
    path = tables_dir / f"sdid_phase_{specification}_{outcome}_{phase}.csv"
    frame = pd.read_csv(path)
    if len(frame) != 1:
        raise ValueError(f"Expected one phase-specific synthetic-DID row in {path}")
    return frame.iloc[0]


def _sdid_coefficient(row: pd.Series) -> str:
    p_value = float(row.p_value)
    stars = ""
    if p_value < 0.01:
        stars = r"$^{***}$"
    elif p_value < 0.05:
        stars = r"$^{**}$"
    elif p_value < 0.10:
        stars = r"$^{*}$"
    return f"{float(row.estimate):.3f}{stars}"


def _build_sdid_phase_table(tables_dir: Path) -> None:
    specifications = ("expanded_donor_cno1_month",)
    columns = [
        *[
            {
                phase: _sdid_phase_row(
                    tables_dir, specification, "ln_parados", phase
                )
                for phase in ("adjustment", "later")
            }
            for specification in specifications
        ],
        *[
            {
                phase: _sdid_phase_row(
                    tables_dir, specification, "ln_contratos", phase
                )
                for phase in ("adjustment", "later")
            }
            for specification in specifications
        ],
    ]
    repetitions = sorted(
        {
            int(column[phase].placebo_repetitions)
            for column in columns
            for phase in ("adjustment", "later")
        }
    )
    if len(repetitions) != 1:
        raise ValueError(f"Inconsistent synthetic-DID repetitions: {repetitions}")

    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Synthetic difference-in-differences estimates}",
        r"\label{tab:v1_sdid}",
        r"\begin{threeparttable}",
        r"\small",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{lcc}",
        r"\toprule",
        r"& \multicolumn{1}{c}{\# of registered unemployed} & \multicolumn{1}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-2}\cmidrule(lr){3-3}",
        r"& (1) & (2) \\",
        r"\midrule",
        "High exposure: adjustment period & "
        + " & ".join(_sdid_coefficient(column["adjustment"]) for column in columns)
        + r" \\",
        " & "
        + " & ".join(f"({float(column['adjustment'].se):.3f})" for column in columns)
        + r" \\",
        "Impact (percent) & "
        + " & ".join(f"{float(column['adjustment'].effect_percent):.1f}" for column in columns)
        + r" \\",
        r"\addlinespace",
        "High exposure: later period & "
        + " & ".join(_sdid_coefficient(column["later"]) for column in columns)
        + r" \\",
        " & "
        + " & ".join(f"({float(column['later'].se):.3f})" for column in columns)
        + r" \\",
        "Impact (percent) & "
        + " & ".join(f"{float(column['later'].effect_percent):.1f}" for column in columns)
        + r" \\",
        r"\midrule",
        r"All lower-exposure occupations eligible as donors & Yes & Yes \\",
        r"CNO1 $\times$ month residualization & Yes & Yes \\",
        "Treated occupations: adjustment period & "
        + " & ".join(f"{int(column['adjustment'].treated_units):,}" for column in columns)
        + r" \\",
        "Donor occupations: adjustment period & "
        + " & ".join(f"{int(column['adjustment'].donor_units):,}" for column in columns)
        + r" \\",
        "Observations: adjustment period & "
        + " & ".join(f"{int(column['adjustment'].observations):,}" for column in columns)
        + r" \\",
        "Treated occupations: later period & "
        + " & ".join(f"{int(column['later'].treated_units):,}" for column in columns)
        + r" \\",
        "Donor occupations: later period & "
        + " & ".join(f"{int(column['later'].donor_units):,}" for column in columns)
        + r" \\",
        "Observations: later period & "
        + " & ".join(f"{int(column['later'].observations):,}" for column in columns)
        + r" \\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\begin{tablenotes}[flushleft]",
        r"\footnotesize",
        rf"\item \emph{{Notes:}} Treated occupations have nearest-neighbor exposure above 0.1169; every occupation at or below the cutoff is retained as a potential donor. The adjustment-period estimates use all pre-treatment months and event times 0--24. The later-period estimates use all pre-treatment months and event times 25--40; event times 0--24 are omitted from those fits. Unit and time weights are re-estimated separately for each interval. Both columns residualize outcomes on CNO1-by-month indicators before constructing the synthetic comparison. Because this residualization depends only on outcomes and family-month cells, it is held fixed across placebo assignments. Standard errors in parentheses use placebo inference with {repetitions[0]} repetitions. Impact rows report $100[\exp(\widehat{{\tau}})-1]$. $^{{***}}p<0.01$, $^{{**}}p<0.05$, and $^{{*}}p<0.10$.",
        r"\end{tablenotes}",
        r"\end{threeparttable}",
        r"\end{table}",
    ]
    _write_tex(tables_dir / "sdid_estimates_v1.tex", lines)


def build_phase_outputs(
    project_root: str | Path,
    estimates_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> pd.DataFrame:
    project_root = Path(project_root)
    tables_dir = Path(estimates_dir) if estimates_dir is not None else project_root / "intermediate"
    figures_dir = Path(output_dir) if output_dir is not None else project_root / "figuresNtables"
    figures_dir.mkdir(parents=True, exist_ok=True)

    base_specs = [
        "benchmark_twfe",
        "preferred_cno1_month",
        "preferred_cno1_month_cluster_cno3",
    ]
    main_columns = [
        *[_phase_pair(tables_dir, spec, "ln_parados") for spec in base_specs],
        *[_phase_pair(tables_dir, spec, "ln_contratos") for spec in base_specs],
    ]
    _six_column_table(
        tables_dir,
        "table2_main_effects_v1.tex",
        "Impact of AI exposure on labor market outcomes",
        "tab:v1_main_effects",
        main_columns,
        "AI exposure",
        "Entries are marginal effects from occupation-month regressions. The adjustment period covers November 2022 through November 2024 (event times 0--24); the later period covers December 2024 through March 2026 (event times 25--40). All pre-treatment months form the omitted category. The dependent variables are logarithms. Columns 1 and 4 include CNO4 and year-month fixed effects; columns 2, 3, 5, and 6 include CNO4 and CNO1-by-year-month fixed effects. Exposure is divided by 0.10, so coefficients correspond to a 10 percentage-point increase. Standard errors are clustered as indicated. The impact rows report 100 times the coefficient and carry no significance symbols. The equality row reports the p-value for the null that the two phase effects are equal. These are marginal effects, not ATTs. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        [
            r"CNO1 $\times$ year-month FE & No & Yes & Yes & No & Yes & Yes \\",
            r"Clustered standard errors & CNO4 & CNO4 & CNO3 & CNO4 & CNO4 & CNO3 \\",
        ],
    )

    robustness_definitions = [
        ("Panel A. Baseline specification", "benchmark_twfe", "preferred_cno1_month", "preferred_cno1_month_cluster_cno3", "ln_parados", "ln_contratos"),
        ("Panel B. Alternative outcomes: log(Y+1)", "benchmark_log_plus_one", "log_plus_one_cno1_month", "log_plus_one_cno1_month_cluster_cno3", "ln_parados_p1", "ln_contratos_p1"),
        ("Panel C. Alternative exposure: cosine-weighted", "benchmark_cosine_weighted", "cosine_weighted_cno1_month", "cosine_weighted_cno1_month_cluster_cno3", "ln_parados", "ln_contratos"),
        ("Panel D. Alternative exposure: RF-relative", "benchmark_rf_relative", "rf_relative_cno1_month", "rf_relative_cno1_month_cluster_cno3", "ln_parados", "ln_contratos"),
    ]
    robust_lines = [
        r"\begin{landscape}", r"\begin{table}[H]", r"\centering",
        r"\caption{Robustness checks: alternative outcomes and exposure measures}",
        r"\label{tab:v1_robustness}", r"\begin{threeparttable}", r"\scriptsize",
        r"\renewcommand{\arraystretch}{0.76}", r"\setlength{\tabcolsep}{3.5pt}",
        r"\begin{tabular}{lcccccc}", r"\toprule",
        r"& \multicolumn{3}{c}{\# of registered unemployed} & \multicolumn{3}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
        r"& (1) & (2) & (3) & (4) & (5) & (6) \\", r"\midrule",
    ]
    for panel_number, definition in enumerate(robustness_definitions):
        panel, benchmark, preferred, preferred_cno3, outcome_u, outcome_c = definition
        if panel_number:
            robust_lines.append(r"\addlinespace")
        columns = [
            *[_phase_pair(tables_dir, spec, outcome_u) for spec in [benchmark, preferred, preferred_cno3]],
            *[_phase_pair(tables_dir, spec, outcome_c) for spec in [benchmark, preferred, preferred_cno3]],
        ]
        robust_lines.append(rf"\multicolumn{{7}}{{l}}{{\textbf{{{panel}}}}} \\")
        robust_lines.extend(_phase_block("AI exposure", columns))
        robust_lines.append(
            "Observations & "
            + " & ".join(f"{int(column['adjustment'].observations):,}" for column in columns)
            + r" \\"
        )
    robust_lines += [
        r"\midrule",
        r"CNO1 $\times$ year-month FE & No & Yes & Yes & No & Yes & Yes \\",
        r"Clustered standard errors & CNO4 & CNO4 & CNO3 & CNO4 & CNO4 & CNO3 \\",
        r"\bottomrule", r"\end{tabular}", r"\begin{tablenotes}[flushleft]", r"\tiny",
        r"\item \emph{Notes:} Each panel reports marginal effects for the adjustment period (event times 0--24) and the later period (event times 25--40), relative to all pre-treatment months. Panel A reproduces the baseline specification. Panel B replaces the logarithmic outcomes with $\log(Y+1)$. Panels C and D use the cosine-weighted and RF-relative exposure measures; the latter subtracts its 10th percentile and sets lower values to zero. Columns 1 and 4 include CNO4 and year-month fixed effects; the remaining columns include CNO4 and CNO1-by-year-month fixed effects. Exposure measures are divided by 0.10. Standard errors are clustered as indicated. Impact rows report 100 times the coefficients; equality rows test whether adjustment- and later-period effects are equal. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}", r"\end{landscape}",
    ]
    _write_tex(tables_dir / "robustness_checks_v1.tex", robust_lines)
    _build_robustness_pretrend_table(tables_dir)

    binary_specs = [
        "binary_high_all_benchmark",
        "binary_high_all_preferred",
        "binary_high_all_preferred_cluster_cno3",
    ]
    binary_columns = [
        *[_phase_pair(tables_dir, spec, "ln_parados") for spec in binary_specs],
        *[_phase_pair(tables_dir, spec, "ln_contratos") for spec in binary_specs],
    ]
    _six_column_table(
        tables_dir,
        "binary_treatment_v1.tex",
        "Binary-treatment robustness checks",
        "tab:v1_binary_treatment",
        binary_columns,
        "Binary treatment",
        "Treatment equals one for occupations with nearest-neighbor exposure above 0.1169, the 75th-percentile cutoff used in the binary design, and zero for occupations at or below the cutoff. The adjustment and later periods cover event times 0--24 and 25--40, respectively; all pre-treatment months form the omitted category. Columns 1 and 4 include CNO4 and year-month fixed effects; the remaining columns include CNO4 and CNO1-by-year-month fixed effects. Standard errors are clustered as indicated. Impact rows report 100 times the coefficients. Equality rows test whether the two phase effects are equal. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        [
            r"CNO1 $\times$ year-month FE & No & Yes & Yes & No & Yes & Yes \\",
            r"Clustered standard errors & CNO4 & CNO4 & CNO3 & CNO4 & CNO4 & CNO3 \\",
        ],
    )

    province_specs = [
        "province_benchmark",
        "province_cno1_month",
        "province_cno1_month_cluster_cno3",
    ]
    province_columns = [
        *[_phase_pair(tables_dir, spec, "ln_parados") for spec in province_specs],
        *[_phase_pair(tables_dir, spec, "ln_contratos") for spec in province_specs],
    ]
    _six_column_table(
        tables_dir,
        "province_robustness_v1.tex",
        "Province-panel robustness",
        "tab:v1_province",
        province_columns,
        "AI exposure",
        "Entries are marginal effects from the province-by-CNO4 panel. The adjustment and later periods cover event times 0--24 and 25--40, respectively; all pre-treatment months form the omitted category. Every specification includes province-by-CNO4 and province-by-year-month fixed effects. Columns 2, 3, 5, and 6 additionally include CNO1-by-year-month fixed effects. Standard errors are clustered as indicated. Missing May 2024 province cells are reconstructed from June levels and published June-over-May changes when the rounded rate uniquely identifies an integer value; unresolved cells remain missing. Exposure is divided by 0.10. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        [
            r"CNO1 $\times$ year-month FE & No & Yes & Yes & No & Yes & Yes \\",
            r"Clustered standard errors & CNO4 & CNO4 & CNO3 & CNO4 & CNO4 & CNO3 \\",
        ],
    )

    groups = [
        ("Panel A. Age: under 30", "age", "lt18_to_29"),
        ("Panel B. Age: 30--39", "age", "30-39"),
        ("Panel C. Age: 40 or older", "age", "40_to_gt44"),
        ("Panel D. Gender: men", "gender", "hombre"),
        ("Panel E. Gender: women", "gender", "mujer"),
    ]
    hetero_lines = [
        r"\begin{table}[p]", r"\centering",
        r"\caption{Heterogeneity in the effects of AI exposure}",
        r"\label{tab:v1_heterogeneity}", r"\begin{threeparttable}",
        r"\scriptsize", r"\renewcommand{\arraystretch}{0.84}",
        r"\setlength{\tabcolsep}{3.0pt}", r"\begin{tabular}{@{}lcccccc@{}}",
        r"\toprule",
        r"& \multicolumn{3}{c}{\# of registered unemployed} & \multicolumn{3}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
        r"& (1) & (2) & (3) & (4) & (5) & (6) \\", r"\midrule",
    ]
    for group_number, (label, dimension, tag) in enumerate(groups):
        if group_number:
            hetero_lines.append(r"\addlinespace[1pt]")
        specs = [
            f"{dimension}_{tag}_benchmark",
            f"{dimension}_{tag}_cno1_month",
            f"{dimension}_{tag}_cno1_month_cluster_cno3",
        ]
        columns = [
            *[_phase_pair(tables_dir, spec, "ln_parados") for spec in specs],
            *[_phase_pair(tables_dir, spec, "ln_contratos") for spec in specs],
        ]
        hetero_lines.append(rf"\multicolumn{{7}}{{l}}{{\textbf{{{label}}}}} \\")
        hetero_lines.extend(_phase_block("AI exposure", columns))
        hetero_lines.append(
            "Observations & "
            + " & ".join(f"{int(column['adjustment'].observations):,}" for column in columns)
            + r" \\"
        )
    hetero_lines += [
        r"\midrule",
        r"CNO1 $\times$ year-month FE & No & Yes & Yes & No & Yes & Yes \\",
        r"Clustered standard errors & CNO4 & CNO4 & CNO3 & CNO4 & CNO4 & CNO3 \\",
        r"\bottomrule", r"\end{tabular}",
        r"\begin{tablenotes}[flushleft]", r"\scriptsize",
        r"\item \emph{Notes:} Each panel reports subgroup-specific marginal effects for the adjustment period (event times 0--24) and later period (event times 25--40), relative to all pre-treatment months. Age categories are under 30, 30--39, and 40 or older. Columns 1 and 4 include occupation and year-month fixed effects; the remaining columns replace common month effects with CNO1-by-year-month effects. Standard errors are clustered as indicated. Exposure is measured in 10 percentage-point units. Equality rows test whether the two phase effects are equal. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "heterogeneity_v1.tex", hetero_lines)

    trailing_specs = [
        "trailing12_benchmark",
        "trailing12_cno1_month",
        "trailing12_cno1_month_cluster_cno3",
    ]
    trailing_columns = [
        _phase_pair(tables_dir, spec, "ln_contratos_12m") for spec in trailing_specs
    ]
    trailing_lines = [
        r"\begin{table}[H]", r"\centering",
        r"\caption{Robustness check: trailing 12-month contract registrations}",
        r"\label{tab:v1_trailing_contracts}", r"\begin{threeparttable}", r"\small",
        r"\begin{tabular}{lccc}", r"\toprule", r"& (1) & (2) & (3) \\", r"\midrule",
        *_phase_block("AI exposure", trailing_columns),
        r"\midrule",
        r"CNO1 $\times$ year-month FE & No & Yes & Yes \\",
        r"Clustered standard errors & CNO4 & CNO4 & CNO3 \\",
        "Observations & " + " & ".join(f"{int(column['adjustment'].observations):,}" for column in trailing_columns) + r" \\",
        r"\bottomrule", r"\end{tabular}", r"\begin{tablenotes}[flushleft]", r"\footnotesize",
        r"\item \emph{Notes:} The dependent variable is the logarithm of contract registrations accumulated over the current and preceding 11 months. This trailing sum is a cumulative hiring flow, not a stock of active contracts. The first available observation is December 2021, leaving 11 pre-treatment months. The adjustment and later periods cover event times 0--24 and 25--40; all available pre-treatment months form the omitted category. Because adjacent outcomes share 11 monthly observations, the transformation mechanically smooths and delays the dynamic response. Exposure is measured in 10 percentage-point units. Standard errors are clustered as indicated. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "trailing12_contracts_v1.tex", trailing_lines)

    _render_event(
        tables_dir / "twfe_binary_event_binary_high_all_preferred_ln_parados.csv",
        figures_dir / "Binary_event_unemployed.png",
        (-0.10, 0.15),
        0.05,
    )
    _render_event(
        tables_dir / "twfe_event_province_cno1_month_ln_parados.csv",
        figures_dir / "Province_event_unemployed.png",
        (-0.05, 0.05),
        0.025,
    )
    _render_event(
        tables_dir / "twfe_event_province_cno1_month_ln_contratos.csv",
        figures_dir / "Province_event_contracts.png",
        (-0.20, 0.20),
        0.05,
    )
    _render_event(
        tables_dir / "twfe_event_trailing12_cno1_month_ln_contratos_12m.csv",
        figures_dir / "Trailing12_contracts_event.png",
        (-0.05, 0.05),
        0.025,
    )

    contdid_specs = [
        ("cno1_stratified", "ln_parados", "ln_contratos"),
        ("control_based_cno1_month", "ln_parados_control_adjusted", "ln_contratos_control_adjusted"),
        ("unconditional", "ln_parados", "ln_contratos"),
    ]
    contdid_columns = [
        *[_derive_contdid_phase(tables_dir, spec, outcome_u) for spec, outcome_u, _ in contdid_specs],
        *[_derive_contdid_phase(tables_dir, spec, outcome_c) for spec, _, outcome_c in contdid_specs],
    ]
    _six_column_table(
        tables_dir,
        "contdid_alternatives_v1.tex",
        "Continuous-DiD alternatives",
        "tab:v1_contdid_alternatives",
        contdid_columns,
        "AI exposure",
        "Entries average the monthly ACRT estimates over event times 0--24 and 25--40. Columns 1 and 4 estimate continuous DiD separately within supported CNO1 families and aggregate family-specific effects using positive-exposure occupation shares. Columns 2 and 5 subtract the zero-exposure outcome change within supported CNO1 families before estimation. Columns 3 and 6 are unconditional. Standard errors use linear combinations of the dynamic influence-function covariance matrices; disjoint-family matrices are combined using squared aggregation weights in the stratified estimator. Exposure is measured in 10 percentage-point units. These estimators do not reproduce the preferred CNO1-by-month TWFE specification. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        [
            r"CNO1-stratified & Yes & No & No & Yes & No & No \\",
            r"Control-based family-time adjustment & No & Yes & No & No & Yes & No \\",
            r"Unconditional pooled comparison & No & No & Yes & No & No & Yes \\",
        ],
    )
    _build_sdid_phase_table(tables_dir)

    summary_rows = []
    for table_name, columns in [
        ("baseline", main_columns),
        ("binary", binary_columns),
        ("province", province_columns),
        ("contdid", contdid_columns),
    ]:
        for column, pair in enumerate(columns, start=1):
            for phase, row in pair.items():
                summary_rows.append(
                    {
                        "table": table_name,
                        "column": column,
                        "phase": phase,
                        "estimate": row.estimate,
                        "se": row.se,
                        "equality_p": row.equality_p,
                        "observations": row.observations,
                    }
                )
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(tables_dir / "phase_estimates_summary_v1.csv", index=False)
    return summary
