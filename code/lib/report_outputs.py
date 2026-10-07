"""Build the phase-based paper tables and final robustness figures for V1."""

from __future__ import annotations

from pathlib import Path
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from scipy.stats import t as student_t
    from scipy.stats import chi2
except ImportError:  # The packaged runtime may not include SciPy.
    student_t = None
    chi2 = None


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


def _phase_block(
    label: str,
    columns: list[dict[str, pd.Series]],
    include_equality: bool = True,
    include_impact: bool = True,
    separate_phases: bool = True,
) -> list[str]:
    rows = [
        f"{label} $\\times$ adjustment period & "
        + " & ".join(_coefficient(column["adjustment"]) for column in columns)
        + r" \\",
        " & "
        + " & ".join(_standard_error(column["adjustment"]) for column in columns)
        + r" \\",
    ]
    if include_impact:
        rows.append(
            "Impact of a 10 pp increase (percent) & "
            + " & ".join(_impact(column["adjustment"]) for column in columns)
            + r" \\"
        )
    if separate_phases:
        rows.append(r"\addlinespace")
    rows.extend([
        f"{label} $\\times$ later period & "
        + " & ".join(_coefficient(column["later"]) for column in columns)
        + r" \\",
        " & "
        + " & ".join(_standard_error(column["later"]) for column in columns)
        + r" \\",
    ])
    if include_impact:
        rows.append(
            "Impact of a 10 pp increase (percent) & "
            + " & ".join(_impact(column["later"]) for column in columns)
            + r" \\"
        )
    if include_equality:
        rows.append(
            "$p$-value: equal phase effects & "
            + " & ".join(_p_equal(column) for column in columns)
            + r" \\"
        )
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
    post_observation_rows: list[str] | None = None,
    include_phase_equality: bool = True,
    include_impact: bool = True,
    separate_phases: bool = True,
    table_placement: str = "!htbp",
) -> None:
    extra_rows = extra_rows or []
    post_observation_rows = post_observation_rows or []
    if len(columns) % 2:
        raise ValueError("Outcome columns must be split evenly across two outcomes")
    columns_per_outcome = len(columns) // 2
    total_columns = len(columns)
    first_end = columns_per_outcome + 1
    second_start = columns_per_outcome + 2
    second_end = total_columns + 1
    lines = [
        rf"\begin{{table}}[{table_placement}]",
        r"\centering",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        r"\begin{threeparttable}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3.5pt}",
        r"\begin{tabular}{l" + "c" * total_columns + "}",
        r"\toprule",
        rf"& \multicolumn{{{columns_per_outcome}}}{{c}}{{\# of registered unemployed}} & \multicolumn{{{columns_per_outcome}}}{{c}}{{\# of new contracts}} \\",
        rf"\cmidrule(lr){{2-{first_end}}}\cmidrule(lr){{{second_start}-{second_end}}}",
        "& " + " & ".join(f"({index})" for index in range(1, total_columns + 1)) + r" \\",
        r"\midrule",
        *_phase_block(
            treatment_label,
            columns,
            include_equality=include_phase_equality,
            include_impact=include_impact,
            separate_phases=separate_phases,
        ),
        r"\midrule",
        *extra_rows,
        "Observations & "
        + " & ".join(f"{int(column['adjustment'].observations):,}" for column in columns)
        + r" \\",
        *post_observation_rows,
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


def _contdid_joint_null(
    tables_dir: Path, specification: str, outcome: str
) -> str:
    event = pd.read_csv(
        tables_dir / f"contdid_event_{specification}_{outcome}.csv"
    ).sort_values("event_time").reset_index(drop=True)
    covariance_frame = pd.read_csv(
        tables_dir / f"contdid_covariance_{specification}_{outcome}.csv"
    ).sort_values("event_time")
    covariance = covariance_frame.filter(regex=r"^cov_").to_numpy(dtype=float)
    index = np.where(event["event_time"].between(event["event_time"].min(), -2))[0]
    beta = event.loc[index, "estimate"].to_numpy(dtype=float)
    variance = covariance[np.ix_(index, index)]
    rank = int(np.linalg.matrix_rank(variance))
    if rank == 0 or chi2 is None:
        return "--"
    statistic = float(beta @ np.linalg.pinv(variance) @ beta)
    return _format_pretrend_p(float(chi2.sf(statistic, rank)))


def _build_contdid_alternative_table(tables_dir: Path) -> list[dict[str, pd.Series]]:
    specifications = [
        ("cno1_stratified", "ln_parados", "ln_contratos"),
        ("cno1_stratified_no2021", "ln_parados", "ln_contratos"),
        ("control_based_cno1_month", "ln_parados_control_adjusted", "ln_contratos_control_adjusted"),
        ("unconditional", "ln_parados", "ln_contratos"),
    ]
    columns = [
        *[_derive_contdid_phase(tables_dir, spec, outcome_u) for spec, outcome_u, _ in specifications],
        *[_derive_contdid_phase(tables_dir, spec, outcome_c) for spec, _, outcome_c in specifications],
    ]
    lines = [
        r"\begin{table}[H]", r"\centering",
        r"\caption{Continuous-DiD alternatives}", r"\label{tab:v1_contdid_alternatives}",
        r"\begin{threeparttable}", r"\scriptsize", r"\setlength{\tabcolsep}{2.5pt}",
        r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{lcccccccc}", r"\toprule",
        r"& \multicolumn{4}{c}{\# of registered unemployed} & \multicolumn{4}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-5}\cmidrule(lr){6-9}",
        r"& (1) & (2) & (3) & (4) & (5) & (6) & (7) & (8) \\", r"\midrule",
        *_phase_block("AI exposure", columns, include_impact=False, separate_phases=False),
        r"\midrule",
        r"CNO1-stratified & Yes & Yes & No & No & Yes & Yes & No & No \\",
        r"Control-based family-time adjustment & No & No & Yes & No & No & No & Yes & No \\",
        r"Unconditional pooled comparison & No & No & No & Yes & No & No & No & Yes \\",
        r"2021 included & Yes & No & Yes & Yes & Yes & No & Yes & Yes \\",
        "Pre-treatment joint-null $p$-value & " + " & ".join(
            _contdid_joint_null(tables_dir, spec, outcome)
            for outcome_index in (1, 2)
            for spec, outcome_u, outcome_c in specifications
            for outcome in ((outcome_u,) if outcome_index == 1 else (outcome_c,))
        ) + r" \\",
        "Observations & " + " & ".join(
            f"{int(column['adjustment'].observations):,}" for column in columns
        ) + r" \\",
        r"\bottomrule", r"\end{tabular}", r"}",
        r"\noindent\begin{minipage}{\textwidth}", r"\footnotesize",
        r"\emph{Notes:} Entries average monthly ACRTs over event times 0--24 and 25--40. Columns 1 and 5 estimate continuous DiD separately within CNO1 families containing at least 15 positive-exposure and 5 zero-exposure occupations and aggregate family estimates using positive-exposure occupation shares. Columns 2 and 6 repeat this estimator without 2021. Columns 3 and 7 subtract the change among zero-exposure occupations in each supported family before pooling; columns 4 and 8 are unconditional. Standard errors use linear combinations of the dynamic influence-function covariance matrices. The pre-treatment row reports a covariance-based Wald test of joint nullity over all available pre-treatment event times through $-2$. Exposure is measured in 10 percentage-point units. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        r"\end{minipage}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "contdid_alternatives_v1.tex", lines)
    return columns


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


def _build_age_cross_group_table(tables_dir: Path) -> None:
    outcomes = ("ln_parados", "ln_contratos")
    phases = ("adjustment", "later")
    unrestricted = {
        outcome: pd.read_csv(tables_dir / f"age_pooled_phase_{outcome}.csv")
        for outcome in outcomes
    }
    pooled = {
        outcome: pd.read_csv(tables_dir / f"age_under40_pooled_phase_{outcome}.csv")
        for outcome in outcomes
    }

    def unrestricted_p(outcome: str, phase: str, column: str) -> str:
        values = unrestricted[outcome].loc[
            unrestricted[outcome]["phase"].eq(phase), column
        ].drop_duplicates()
        if len(values) != 1:
            raise ValueError(f"Expected one {column} value for {outcome}/{phase}")
        return _format_pretrend_p(float(values.iloc[0]))

    def pooled_p(outcome: str, phase: str) -> str:
        rows = pooled[outcome].loc[pooled[outcome]["phase"].eq(phase)]
        if len(rows) != 1:
            raise ValueError(f"Expected one pooled under-40 row for {outcome}/{phase}")
        return _format_pretrend_p(float(rows.iloc[0]["p_under40_vs_40plus"]))

    columns = [(outcome, phase) for outcome in outcomes for phase in phases]
    test_rows = [
        ("All age-group effects equal", "p_equal_all"),
        ("Ages 30--39 = under 30", "p_3039_vs_under30"),
        ("Ages 30--39 = age 40 or older", "p_3039_vs_40plus"),
        ("Under 30 = age 40 or older", "p_under30_vs_40plus"),
    ]

    lines = [
        r"\begin{table}[!htbp]",
        r"\centering",
        r"\caption{Formal tests of age-group heterogeneity}",
        r"\label{tab:v1_age_cross_group_tests}",
        r"\begin{threeparttable}",
        r"\small",
        r"\setlength{\tabcolsep}{5pt}",
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"& \multicolumn{2}{c}{\# of registered unemployed} & \multicolumn{2}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}",
        r"& Adjustment & Later & Adjustment & Later \\",
        r"\midrule",
    ]
    for label, column in test_rows:
        lines.append(
            label
            + " & "
            + " & ".join(
                unrestricted_p(outcome, phase, column)
                for outcome, phase in columns
            )
            + r" \\"
        )
    lines.append(
        "Pooled under 40 = age 40 or older & "
        + " & ".join(pooled_p(outcome, phase) for outcome, phase in columns)
        + r" \\"
    )

    observations = [
        int(
            unrestricted[outcome].loc[
                unrestricted[outcome]["phase"].eq("adjustment"), "observations"
            ].iloc[0]
        )
        for outcome in outcomes
    ]
    clusters = sorted(
        {
            int(value)
            for outcome in outcomes
            for value in pooled[outcome]["clusters"].dropna().unique()
        }
    )
    cluster_text = ", ".join(f"{value:,}" for value in clusters)
    lines += [
        r"\midrule",
        f"Observations & \\multicolumn{{2}}{{c}}{{{observations[0]:,}}} & \\multicolumn{{2}}{{c}}{{{observations[1]:,}}}"
        + r" \\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\begin{tablenotes}[flushleft]",
        r"\footnotesize",
        rf"\item \emph{{Notes:}} Entries are $p$-values from Wald tests in the pooled age-by-CNO4 panel. The first four rows come from a regression that permits separate exposure gradients for workers under 30, ages 30--39, and age 40 or older in each post-treatment period. The final row comes from a companion regression that constrains the two younger groups to share a phase-specific gradient and tests that common under-40 gradient against the gradient for age 40 or older. Both regressions include age-by-CNO4 and age-by-CNO1-by-year-month fixed effects. Standard errors allow arbitrary correlation across age groups within each of {cluster_text} CNO4 occupations.",
        r"\end{tablenotes}",
        r"\end{threeparttable}",
        r"\end{table}",
    ]
    _write_tex(tables_dir / "age_cross_group_tests_v1.tex", lines)


def _pretrend_value_or_dash(
    tables_dir: Path,
    specification: str,
    outcome: str,
    window: str,
    test: str,
    prefix: str = "twfe_pretrend",
) -> str:
    path = tables_dir / f"{prefix}_{specification}_{outcome}.csv"
    frame = pd.read_csv(path)
    row = frame.loc[(frame["window"] == window) & (frame["test"] == test)]
    if row.empty:
        return "--"
    if len(row) != 1:
        raise ValueError(f"Expected at most one {window}/{test} row in {path}")
    return _format_pretrend_p(float(row.iloc[0]["p_value"]))


def _pretrend_table_lines(
    tables_dir: Path,
    panels: list[tuple[str, tuple[str, ...], tuple[str, str]]],
    caption: str,
    label: str,
    prefix: str = "twfe_pretrend",
    notes: str | None = None,
    notes_width: str | None = None,
) -> list[str]:
    windows = [
        ("Full available", "full_-21_-2"),
        ("Early: -21 to -10", "early_-21_-10"),
        ("Recent: -10 to -2", "recent_-10_-2"),
    ]
    tests = ("joint_equal_zero", "joint_equal_coefficients")
    outcome_labels = ("Registered unemployed", "New contracts")
    if notes is None:
        notes = (
            "Entries are $p$-values from Wald tests of pre-treatment event-study coefficients. "
            "The nullity test evaluates whether all coefficients in the indicated window equal zero; "
            "the equality test evaluates whether they equal one another while allowing their common "
            "value to differ from zero. The benchmark includes CNO4 and year-month fixed effects. "
            "The remaining specifications include CNO4 and CNO1-by-year-month fixed effects and differ "
            "by sample period as indicated. The full available window is event times "
            "$-21$ through $-2$ when 2021 is included and $-10$ through $-2$ when it is excluded. "
            "Accordingly, the early window is unavailable for the no-2021 specification. October 2022 "
            "(event time $-1$) is omitted."
        )
    lines = [
        r"\begin{table}[H]",
        r"\centering",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        r"\begin{threeparttable}",
        r"\scriptsize",
        r"\renewcommand{\arraystretch}{0.90}",
        r"\setlength{\tabcolsep}{1.6pt}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{@{}llcccccc@{}}",
        r"\toprule",
        r"& & \multicolumn{2}{c}{Benchmark} & \multicolumn{4}{c}{CNO1-by-month FE} \\",
        r"\cmidrule(lr){3-4}\cmidrule(lr){5-8}",
        r"& & \multicolumn{2}{c}{With 2021} & \multicolumn{2}{c}{With 2021} & \multicolumn{2}{c}{Without 2021} \\",
        r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}",
        r"Outcome & Window & Nullity & Equality & Nullity & Equality & Nullity & Equality \\",
        r"\midrule",
    ]
    for panel_index, (panel, specifications, outcomes) in enumerate(panels):
        if panel:
            if panel_index:
                lines.append(r"\addlinespace[5pt]")
            lines.append(rf"\multicolumn{{8}}{{l}}{{\textbf{{{panel}}}}} \\")
        for outcome_label, outcome in zip(outcome_labels, outcomes):
            for window_label, window in windows:
                values = []
                for specification in specifications:
                    values.extend(
                        _pretrend_value_or_dash(
                            tables_dir, specification, outcome, window, test, prefix
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
        r"}",
        r"\begin{minipage}{\textwidth}",
        r"\footnotesize",
        rf"\emph{{Notes:}} {notes}",
        r"\end{minipage}",
        r"\end{threeparttable}",
        r"\end{table}",
    ]
    return lines


def _pretrend_table_lines(
    tables_dir: Path,
    panels: list[tuple[str, tuple[str, ...], tuple[str, str]]],
    caption: str,
    label: str,
    prefix: str = "twfe_pretrend",
    notes: str | None = None,
    notes_width: str | None = None,
) -> list[str]:
    """Format diagnostics with the same six regression columns as estimates."""
    windows = [
        ("Full available", "full_-21_-2"),
        ("Early: -21 to -10", "early_-21_-10"),
        ("Recent: -10 to -2", "recent_-10_-2"),
    ]
    tests = (
        ("Joint nullity", "joint_equal_zero"),
        ("Equal coefficients", "joint_equal_coefficients"),
    )
    if notes is None:
        notes = (
            "Entries are $p$-values from Wald tests of pre-treatment event-study coefficients. "
            "Joint nullity tests whether all coefficients in the indicated window equal zero; "
            "the equality test allows a common nonzero level. Columns 1 and 4 are the benchmark "
            "with CNO4 and year-month fixed effects. Columns 2 and 5 add CNO1-by-year-month fixed "
            "effects. Columns 3 and 6 use the latter specification but exclude 2021. The full "
            "available window is event times $-21$ through $-2$ when 2021 is included and $-10$ "
            "through $-2$ otherwise; the early window is consequently unavailable in columns 3 "
            "and 6. October 2022 (event time $-1$) is omitted. Standard errors are clustered by CNO4."
        )

    header = [
        r"\toprule",
        r"& \multicolumn{3}{c}{\# of registered unemployed} & \multicolumn{3}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
        r"& (1) & (2) & (3) & (4) & (5) & (6) \\",
        r"\midrule",
    ]
    use_longtable = len(panels) > 1
    if use_longtable:
        lines = [
            r"\begingroup", r"\scriptsize",
            r"\renewcommand{\arraystretch}{0.88}",
            r"\setlength{\tabcolsep}{2.0pt}",
            r"\begin{longtable}{@{}lcccccc@{}}",
            f"\\caption{{{caption}}}\\label{{{label}}}\\\\",
            *header,
            r"\endfirsthead",
            r"\multicolumn{7}{c}{\tablename\ \thetable{} -- continued} \\",
            *header,
            r"\endhead",
        ]
    else:
        lines = [
            r"\begin{table}[H]", r"\centering",
            f"\\caption{{{caption}}}", f"\\label{{{label}}}",
            r"\begin{threeparttable}", r"\scriptsize",
            r"\renewcommand{\arraystretch}{0.90}",
            r"\setlength{\tabcolsep}{2.0pt}",
            r"\begin{tabular}{@{}lcccccc@{}}",
            *header,
        ]

    for panel_index, (panel, specifications, outcomes) in enumerate(panels):
        if panel:
            if panel_index:
                lines.append(r"\addlinespace[5pt]")
            lines.append(rf"\multicolumn{{7}}{{l}}{{\textbf{{{panel}}}}} \\")
        for window_label, window in windows:
            for test_label, test in tests:
                values = [
                    _pretrend_value_or_dash(
                        tables_dir, specification, outcome, window, test, prefix
                    )
                    for outcome in outcomes
                    for specification in specifications
                ]
                lines.append(
                    f"{window_label}: {test_label} & "
                    + " & ".join(values)
                    + r" \\")

    lines += [
        r"\midrule",
        r"CNO1 $\times$ year-month FE & No & Yes & Yes & No & Yes & Yes \\",
        r"2021 included & Yes & Yes & No & Yes & Yes & No \\",
        r"\bottomrule",
    ]
    if use_longtable:
        lines.append(r"\end{longtable}")
        if notes_width is not None:
            lines.extend([
                r"\begin{center}",
                rf"\begin{{minipage}}{{{notes_width}}}", r"\footnotesize",
                rf"\emph{{Notes:}} {notes}", r"\end{minipage}",
                r"\end{center}", r"\endgroup",
            ])
        else:
            lines.extend([
                r"\noindent\begin{minipage}{\linewidth}", r"\footnotesize",
                rf"\emph{{Notes:}} {notes}", r"\end{minipage}", r"\endgroup",
            ])
    else:
        lines += [
            r"\end{tabular}", r"\begin{tablenotes}[flushleft]", r"\footnotesize",
            rf"\item \emph{{Notes:}} {notes}", r"\end{tablenotes}",
            r"\end{threeparttable}", r"\end{table}",
        ]
    return lines


def _build_baseline_pretrend_table(tables_dir: Path) -> None:
    specifications = (
        "benchmark_twfe",
        "preferred_cno1_month",
        "preferred_cno1_month_no2021",
    )
    lines = _pretrend_table_lines(
        tables_dir,
        [("", specifications, ("ln_parados", "ln_contratos"))],
        "Pre-treatment coefficient tests across baseline specifications",
        "tab:v1_pretrends",
    )
    _write_tex(tables_dir / "pretrend_diagnostics_v1.tex", lines)


def _build_robustness_pretrend_table(tables_dir: Path) -> None:
    panels = [
        (
            "Panel A. Baseline specification",
            ("benchmark_twfe", "preferred_cno1_month", "preferred_cno1_month_no2021"),
            ("ln_parados", "ln_contratos"),
        ),
        (
            "Panel B. Alternative outcomes: log(Y+1)",
            ("benchmark_log_plus_one", "log_plus_one_cno1_month", "log_plus_one_cno1_month_no2021"),
            ("ln_parados_p1", "ln_contratos_p1"),
        ),
        (
            "Panel C. Alternative exposure: cosine-weighted",
            ("benchmark_cosine_weighted", "cosine_weighted_cno1_month", "cosine_weighted_cno1_month_no2021"),
            ("ln_parados", "ln_contratos"),
        ),
    ]
    lines = _pretrend_table_lines(
        tables_dir,
        panels,
        "Pre-treatment diagnostics for alternative outcomes and exposure measures",
        "tab:v1_robustness_pretrends",
        notes_width=r"0.68\linewidth",
    )
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
    specification_rows = [
        {
            "specification": "expanded_donor_cno1_month",
            "threshold": "0.1169",
            "all_lower_donors": "Yes",
            "zero_only_donors": "No",
        },
        {
            "specification": "high020_zeroonly_cno1_month",
            "threshold": "0.2",
            "all_lower_donors": "No",
            "zero_only_donors": "Yes",
        },
    ]
    columns = []
    for outcome in ("ln_parados", "ln_contratos"):
        for spec_row in specification_rows:
            columns.append(
                {
                    **spec_row,
                    "outcome": outcome,
                    **{
                        phase: _sdid_phase_row(
                            tables_dir, spec_row["specification"], outcome, phase
                        )
                        for phase in ("adjustment", "later")
                    },
                }
            )
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
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"& \multicolumn{2}{c}{\# of registered unemployed} & \multicolumn{2}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}",
        r"& (1) & (2) & (3) & (4) \\",
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
        "Exposure threshold for treatment status & "
        + " & ".join(column["threshold"] for column in columns)
        + r" \\",
        "All lower-exposure occupations eligible as donors & "
        + " & ".join(column["all_lower_donors"] for column in columns)
        + r" \\",
        "Donor pool restricted to zero exposure & "
        + " & ".join(column["zero_only_donors"] for column in columns)
        + r" \\",
        r"CNO1 $\times$ month adjustment & Residualized & Projected & Residualized & Projected \\",
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
        rf"\item \emph{{Notes:}} Columns 1 and 3 report the baseline SDID design, where treated occupations have nearest-neighbor exposure above 0.1169 and every occupation at or below that cutoff remains eligible for the donor pool. Columns 2 and 4 report the more dichotomous robustness design, where treated occupations have exposure above 0.2 and donors are restricted to zero-exposure occupations. The adjustment-period estimates use all pre-treatment months and event times 0--24. The later-period estimates use all pre-treatment months and event times 25--40; event times 0--24 are omitted from those fits. Unit and time weights are re-estimated separately for each specification, outcome, and interval. Columns 1 and 3 residualize outcomes on CNO1-by-month indicators using the estimation sample; this adjustment is held fixed across placebo assignments. Columns 2 and 4 use the SDID implementation's projected CNO1-by-month covariate adjustment, fitted to donor outcomes and re-estimated under each placebo assignment. Standard errors in parentheses use placebo inference with {repetitions[0]} repetitions. Impact rows report $100[\exp(\widehat{{\tau}})-1]$. $^{{***}}p<0.01$, $^{{**}}p<0.05$, and $^{{*}}p<0.10$.",
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
    figures_dir = (
        Path(output_dir)
        if output_dir is not None
        else project_root / "uploads" / "figuresNtables"
    )
    figures_dir.mkdir(parents=True, exist_ok=True)

    base_specs = [
        "benchmark_twfe",
        "preferred_cno1_month",
        "preferred_cno1_month_no2021",
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
        "Entries are marginal effects from occupation-month regressions. The adjustment period covers November 2022 through November 2024 (event times 0--24); the later period covers December 2024 through March 2026 (event times 25--40). All available pre-treatment months form the omitted category. The dependent variables are logarithms. Columns 1 and 4 include CNO4 and year-month fixed effects; the remaining columns include CNO4 and CNO1-by-year-month fixed effects. Columns 3 and 6 exclude 2021, when pandemic recovery, employment-retention policies, and unusually high telework intensity may have generated differential occupational trends. Exposure is divided by 0.10, so each coefficient corresponds to a 10 percentage-point increase and can be interpreted approximately as a proportional change in the outcome. Standard errors are clustered by CNO4. The phase-equality row tests whether the adjustment- and later-period coefficients are equal. The pre-treatment joint-null row tests whether all available pre-treatment event-study coefficients equal zero: event times $-21$ through $-2$ in columns that include 2021 and event times $-10$ through $-2$ in columns 3 and 6. October 2022 is omitted. These are marginal effects, not ATTs. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        [
            r"CNO1 $\times$ year-month FE & No & Yes & Yes & No & Yes & Yes \\",
            r"2021 included & Yes & Yes & No & Yes & Yes & No \\",
            "$p$-value: equal phase effects & "
            + " & ".join(_p_equal(column) for column in main_columns)
            + r" \\",
            "Pre-treatment joint-null $p$-value & "
            + " & ".join(
                _format_pretrend_p(
                    _pretrend_p_value(
                        tables_dir,
                        spec,
                        outcome,
                        "full_-21_-2",
                        "joint_equal_zero",
                    )
                )
                for outcome in ("ln_parados", "ln_contratos")
                for spec in base_specs
            )
            + r" \\",
        ],
        include_phase_equality=False,
        include_impact=False,
        separate_phases=False,
    )

    robustness_definitions = [
        ("Panel A. Baseline specification", "benchmark_twfe", "preferred_cno1_month", "preferred_cno1_month_no2021", "ln_parados", "ln_contratos"),
        ("Panel B. Alternative outcomes: log(Y+1)", "benchmark_log_plus_one", "log_plus_one_cno1_month", "log_plus_one_cno1_month_no2021", "ln_parados_p1", "ln_contratos_p1"),
        ("Panel C. Alternative exposure: cosine-weighted", "benchmark_cosine_weighted", "cosine_weighted_cno1_month", "cosine_weighted_cno1_month_no2021", "ln_parados", "ln_contratos"),
    ]
    robust_lines = [
        r"\begin{table}[H]", r"\centering",
        r"\caption{Robustness checks: alternative outcomes and exposure measures}",
        r"\label{tab:v1_robustness}", r"\begin{threeparttable}", r"\scriptsize",
        r"\renewcommand{\arraystretch}{0.78}", r"\setlength{\tabcolsep}{3.0pt}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{lcccccc}", r"\toprule",
        r"& \multicolumn{3}{c}{\# of registered unemployed} & \multicolumn{3}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
        r"& (1) & (2) & (3) & (4) & (5) & (6) \\", r"\midrule",
    ]
    for panel_number, definition in enumerate(robustness_definitions):
        panel, benchmark, preferred, no2021, outcome_u, outcome_c = definition
        if panel_number:
            robust_lines.append(r"\addlinespace[5pt]")
        specs = [benchmark, preferred, no2021]
        columns = [
            *[_phase_pair(tables_dir, spec, outcome_u) for spec in specs],
            *[_phase_pair(tables_dir, spec, outcome_c) for spec in specs],
        ]
        robust_lines.append(rf"\multicolumn{{7}}{{l}}{{\textbf{{{panel}}}}} \\")
        robust_lines.extend(
            _phase_block(
                "AI exposure",
                columns,
                include_equality=False,
                include_impact=False,
                separate_phases=False,
            )
        )
        robust_lines.append(r"\addlinespace[2pt]")
        robust_lines.append(
            "Pre-treatment joint-null $p$-value & "
            + " & ".join(
                _format_pretrend_p(
                    _pretrend_p_value(
                        tables_dir,
                        spec,
                        outcome,
                        "full_-21_-2",
                        "joint_equal_zero",
                    )
                )
                for outcome in (outcome_u, outcome_c)
                for spec in specs
            )
            + r" \\"
        )
        robust_lines.append(
            "$p$-value: equal phase effects & "
            + " & ".join(_p_equal(column) for column in columns)
            + r" \\"
        )
        robust_lines.append(
            "Observations & "
            + " & ".join(f"{int(column['adjustment'].observations):,}" for column in columns)
            + r" \\"
        )
    robust_lines += [
        r"\midrule",
        r"CNO1 $\times$ year-month FE & No & Yes & Yes & No & Yes & Yes \\",
        r"2021 included & Yes & Yes & No & Yes & Yes & No \\",
        r"\bottomrule", r"\end{tabular}", r"}",
        r"\begin{minipage}{\textwidth}", r"\footnotesize",
        r"\emph{Notes:} Each panel reports marginal effects for the adjustment period (event times 0--24) and the later period (event times 25--40), relative to all pre-treatment months. Panel A reproduces the baseline specification. Panel B replaces the logarithmic outcomes with $\log(Y+1)$. Panel C uses the cosine-weighted exposure measure. Columns 1 and 4 include CNO4 and year-month fixed effects; the remaining columns include CNO4 and CNO1-by-year-month fixed effects. Columns 3 and 6 exclude 2021. Exposure measures are divided by 0.10, so each coefficient corresponds to a 10 percentage-point increase in the indicated score. Standard errors are clustered by CNO4. Pre-treatment entries test the joint null that all available event-study coefficients equal zero: event times $-21$ through $-2$ when 2021 is included and $-10$ through $-2$ otherwise. Equality rows test whether adjustment- and later-period effects are equal. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        r"\end{minipage}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "robustness_checks_v1.tex", robust_lines)
    _build_baseline_pretrend_table(tables_dir)
    _build_robustness_pretrend_table(tables_dir)

    binary_specs = [
        "binary_high_all_benchmark",
        "binary_high_all_preferred",
        "binary_high_all_preferred_no2021",
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
        r"$\mathbf{1}\{A_j>A_{75}\}$",
        "Treatment equals one for occupations with nearest-neighbor exposure above $A_{75}$ and zero for occupations at or below it, where $A_{75}=0.1169$ is the 75th percentile of AI exposure. The adjustment and later periods cover event times 0--24 and 25--40, respectively; all pre-treatment months form the omitted category. Columns 1 and 4 include CNO4 and year-month fixed effects; the remaining columns include CNO4 and CNO1-by-year-month fixed effects. Columns 3 and 6 exclude 2021. Standard errors are clustered by CNO4. The phase-equality row tests whether the adjustment- and later-period coefficients are equal. The pre-treatment joint-null row tests whether all available pre-treatment event-study coefficients equal zero: event times $-21$ through $-2$ when 2021 is included and $-10$ through $-2$ otherwise. October 2022 is omitted. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        [
            r"CNO1 $\times$ year-month FE & No & Yes & Yes & No & Yes & Yes \\",
            r"2021 included & Yes & Yes & No & Yes & Yes & No \\",
            "$p$-value: equal phase effects & "
            + " & ".join(_p_equal(column) for column in binary_columns)
            + r" \\",
            "Pre-treatment joint-null $p$-value & "
            + " & ".join(
                _pretrend_value_or_dash(
                    tables_dir, spec, outcome, "full_-21_-2",
                    "joint_equal_zero", "twfe_binary_pretrend"
                )
                for outcome in ("ln_parados", "ln_contratos")
                for spec in binary_specs
            )
            + r" \\",
        ],
        include_phase_equality=False,
        include_impact=False,
        separate_phases=False,
    )

    binary_pretrend_notes = (
        "Entries are $p$-values from Wald tests of pre-treatment event-study coefficients in the binary-treatment design. "
        "Treatment equals one for occupations with nearest-neighbor exposure above 0.1169 and zero otherwise. "
        "The nullity test evaluates whether all coefficients in the indicated window equal zero; the equality test evaluates "
        "whether they equal one another while allowing their common value to differ from zero. The benchmark includes CNO4 "
        "and year-month fixed effects. The remaining specifications include CNO4 and CNO1-by-year-month fixed effects and "
        "differ by sample period as indicated. The full available window is event times $-21$ through "
        "$-2$ when 2021 is included and $-10$ through $-2$ when it is excluded. The early window is therefore unavailable "
        "for the no-2021 specification. October 2022 (event time $-1$) is omitted."
    )
    binary_pretrend_lines = _pretrend_table_lines(
        tables_dir,
        [("", tuple(binary_specs), ("ln_parados", "ln_contratos"))],
        "Pre-treatment diagnostics for the binary-treatment design",
        "tab:v1_binary_pretrends",
        prefix="twfe_binary_pretrend",
        notes=binary_pretrend_notes,
    )
    _write_tex(tables_dir / "binary_pretrend_diagnostics_v1.tex", binary_pretrend_lines)

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
            f"{dimension}_{tag}_cno1_month_no2021",
        ]
        columns = [
            *[_phase_pair(tables_dir, spec, "ln_parados") for spec in specs],
            *[_phase_pair(tables_dir, spec, "ln_contratos") for spec in specs],
        ]
        hetero_lines.append(rf"\multicolumn{{7}}{{l}}{{\textbf{{{label}}}}} \\")
        hetero_lines.extend(
            _phase_block(
                "AI exposure", columns, include_impact=False,
                separate_phases=False,
            )
        )
        hetero_lines.append(
            "Observations & "
            + " & ".join(f"{int(column['adjustment'].observations):,}" for column in columns)
            + r" \\"
        )
        hetero_lines.append(
            "Pre-trend joint-null $p$-value & "
            + " & ".join(
                _format_pretrend_p(
                    _pretrend_p_value(
                        tables_dir, spec, outcome, "full_-21_-2", "joint_equal_zero"
                    )
                )
                for outcome in ("ln_parados", "ln_contratos")
                for spec in specs
            )
            + r" \\"
        )
    hetero_lines += [
        r"\midrule",
        r"CNO1 $\times$ year-month FE & No & Yes & Yes & No & Yes & Yes \\",
        r"2021 included & Yes & Yes & No & Yes & Yes & No \\",
        r"\bottomrule", r"\end{tabular}",
        r"\begin{tablenotes}[flushleft]", r"\scriptsize",
        r"\item \emph{Notes:} Each panel reports subgroup-specific marginal effects for the adjustment period (event times 0--24) and later period (event times 25--40), relative to all pre-treatment months. Age categories are under 30, 30--39, and 40 or older. Columns 1 and 4 include CNO4 and year-month fixed effects; the remaining columns include CNO4 and CNO1-by-year-month fixed effects. Columns 3 and 6 exclude 2021. Exposure is measured in 10 percentage-point units, and standard errors are clustered by CNO4. Equality rows test whether the two phase effects are equal. Pre-treatment rows test the joint null over all available event-study coefficients: event times $-21$ through $-2$ when 2021 is included and $-10$ through $-2$ otherwise. October 2022 is omitted. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "heterogeneity_v1.tex", hetero_lines)
    hetero_pretrend_panels = [
        (
            label,
            (
                f"{dimension}_{tag}_benchmark",
                f"{dimension}_{tag}_cno1_month",
                f"{dimension}_{tag}_cno1_month_no2021",
            ),
            ("ln_parados", "ln_contratos"),
        )
        for label, dimension, tag in groups
    ]
    _write_tex(
        tables_dir / "heterogeneity_pretrend_diagnostics_v1.tex",
        _pretrend_table_lines(
            tables_dir,
            hetero_pretrend_panels,
            "Pre-treatment diagnostics for heterogeneity estimates",
            "tab:v1_heterogeneity_pretrends",
            notes=(
                "Entries are $p$-values from Wald tests of subgroup-specific pre-treatment "
                "event-study coefficients. Joint nullity tests whether all coefficients in the "
                "indicated window equal zero; equality tests whether they equal one another. "
                "Within every panel, columns 1 and 4 include CNO4 and year-month fixed effects, "
                "columns 2 and 5 add CNO1-by-year-month fixed effects, and columns 3 and 6 repeat "
                "the latter specification without 2021. The full available window is event times "
                "$-21$ through $-2$ when 2021 is included and $-10$ through $-2$ otherwise. "
                "October 2022 is omitted. Standard errors are clustered by CNO4."
            ),
        ),
    )
    _build_age_cross_group_table(tables_dir)

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
        *_phase_block("AI exposure", trailing_columns, include_impact=False),
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
        tables_dir / "twfe_event_trailing12_cno1_month_ln_contratos_12m.csv",
        figures_dir / "Trailing12_contracts_event.png",
        (-0.05, 0.05),
        0.025,
    )

    contdid_columns = _build_contdid_alternative_table(tables_dir)
    _build_sdid_phase_table(tables_dir)

    summary_rows = []
    for table_name, columns in [
        ("baseline", main_columns),
        ("binary", binary_columns),
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
