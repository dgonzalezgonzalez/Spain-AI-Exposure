from __future__ import annotations

from pathlib import Path
import math

import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import pandas as pd

from .report_outputs import (
    GREY,
    NAVY,
    SKY,
    _format_pretrend_p,
    _p_equal,
    _phase_pair,
    _pretrend_p_value,
    _six_column_table,
    _write_tex,
)


GROUP_COLORS = {1: GREY, 2: "#9ECAE1", 3: SKY, 4: NAVY}


def _row(frame: pd.DataFrame, **conditions: object) -> pd.Series:
    selected = frame.copy()
    for column, value in conditions.items():
        selected = selected.loc[selected[column].eq(value)]
    if len(selected) != 1:
        raise ValueError(f"Expected one row for {conditions}; found {len(selected)}")
    return selected.iloc[0]


def _pvalue(estimate: float, standard_error: float) -> float:
    if not np.isfinite(standard_error) or standard_error <= 0:
        return np.nan
    return math.erfc(abs(estimate / standard_error) / math.sqrt(2))


def _coef(row: pd.Series) -> str:
    estimate = float(row["estimate"])
    standard_error = float(row["se"])
    p = _pvalue(estimate, standard_error)
    stars = r"$^{***}$" if p < 0.01 else r"$^{**}$" if p < 0.05 else r"$^{*}$" if p < 0.10 else ""
    return f"{estimate:.3f}{stars}"


def _se(row: pd.Series) -> str:
    return f"({float(row['se']):.3f})"


def _render_single_event(
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
    fig.savefig(destination, bbox_inches="tight", dpi=240)
    plt.close(fig)


def _render_group_event(
    source: Path,
    destination: Path,
    group_column: str,
    labels: dict[int, str],
    ylim: tuple[float, float],
    step: float,
) -> None:
    frame = pd.read_csv(source).sort_values([group_column, "event_time"])
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    ax.axhline(0, color=GREY, linewidth=0.7)
    ax.axvline(0, color=GREY, linestyle="--", linewidth=0.8)
    for group, label in labels.items():
        selected = frame.loc[frame[group_column].eq(group)]
        ax.fill_between(
            selected["event_time"].astype(float),
            selected["ci_low"].astype(float),
            selected["ci_high"].astype(float),
            color=GROUP_COLORS[group],
            alpha=0.10,
            linewidth=0,
        )
        ax.plot(
            selected["event_time"],
            selected["estimate"],
            color=GROUP_COLORS[group],
            linewidth=1.2,
            label=label,
        )
    ax.set_xlim(-21, 40)
    ax.set_ylim(*ylim)
    ax.set_yticks(np.arange(ylim[0], ylim[1] + step / 2, step))
    ax.set_xticks(np.arange(-20, 41, 10))
    ax.set_xlabel("Months relative to November 2022")
    ax.set_ylabel("Estimate")
    ax.legend(frameon=False, ncol=1, fontsize=8, loc="best")
    fig.tight_layout()
    fig.savefig(destination, bbox_inches="tight", dpi=240)
    plt.close(fig)


def _pretrend_row(tables_dir: Path, specs: list[str]) -> str:
    values = [
        _format_pretrend_p(
            _pretrend_p_value(
                tables_dir, spec, outcome, "full_-21_-2", "joint_equal_zero"
            )
        )
        for outcome in ("ln_parados", "ln_contratos")
        for spec in specs
    ]
    return "Pre-trend joint-null $p$-value & " + " & ".join(values) + r" \\"


def _build_main_province_table(tables_dir: Path) -> None:
    outcomes = ("ln_parados", "ln_contratos")
    groups = ((1, "Madrid and Barcelona"), (2, "Rest of Spain"))
    phase_data = {
        outcome: pd.read_csv(
            tables_dir / f"twfe_phase_mainprovince_comparison_{outcome}.csv"
        )
        for outcome in outcomes
    }
    pretrend_data = {
        outcome: pd.read_csv(
            tables_dir / f"twfe_pretrend_mainprovince_comparison_{outcome}.csv"
        )
        for outcome in outcomes
    }

    def phase_row(outcome: str, group_id: int, phase: str) -> pd.Series:
        return _row(phase_data[outcome], group_id=group_id, phase=phase)

    def recent_pretrend(outcome: str, group_label: str) -> str:
        row = _row(
            pretrend_data[outcome],
            geographic_group=group_label,
            window="recent_-10_-2",
            test="joint_equal_zero",
        )
        return _format_pretrend_p(float(row["p_value"]))

    columns = [
        *[phase_row("ln_parados", group_id, "adjustment") for group_id, _ in groups],
        *[phase_row("ln_contratos", group_id, "adjustment") for group_id, _ in groups],
    ]
    adjustment_rows = [
        phase_row(outcome, group_id, "adjustment")
        for outcome in outcomes for group_id, _ in groups
    ]
    later_rows = [
        phase_row(outcome, group_id, "later")
        for outcome in outcomes for group_id, _ in groups
    ]
    lines = [
        r"\begin{table}[H]", r"\centering",
        r"\caption{Geographic heterogeneity in AI exposure effects}",
        r"\label{tab:v1_main_provinces}",
        r"\scriptsize", r"\setlength{\tabcolsep}{4.5pt}",
        r"\begin{tabular}{lcccc}", r"\toprule",
        r"& \multicolumn{2}{c}{\# of registered unemployed} & \multicolumn{2}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}",
        r"& (1) & (2) & (3) & (4) \\", r"\midrule",
        "AI exposure $\\times$ adjustment period & "
        + " & ".join(_coef(row) for row in adjustment_rows) + r" \\",
        " & " + " & ".join(_se(row) for row in adjustment_rows) + r" \\",
        "AI exposure $\\times$ later period & "
        + " & ".join(_coef(row) for row in later_rows) + r" \\",
        " & " + " & ".join(_se(row) for row in later_rows) + r" \\",
        r"\midrule",
        r"Geographic sample & Madrid + Barcelona & Rest of Spain & Madrid + Barcelona & Rest of Spain \\",
        "Pre-treatment joint-null $p$-value & "
        + " & ".join(
            recent_pretrend(outcome, group_label)
            for outcome in outcomes for _, group_label in groups
        ) + r" \\",
        "$p$-value: equal phase effects & "
        + " & ".join(f"{float(row['phase_equality_p']):.3f}" for row in adjustment_rows)
        + r" \\",
        "$p$-value: equal geographic effects, adjustment & "
        + f"\\multicolumn{{2}}{{c}}{{{float(adjustment_rows[0]['between_group_p']):.3f}}} & "
        + f"\\multicolumn{{2}}{{c}}{{{float(adjustment_rows[2]['between_group_p']):.3f}}} \\\\",
        "$p$-value: equal geographic effects, later & "
        + f"\\multicolumn{{2}}{{c}}{{{float(later_rows[0]['between_group_p']):.3f}}} & "
        + f"\\multicolumn{{2}}{{c}}{{{float(later_rows[2]['between_group_p']):.3f}}} \\\\",
        "Observations & " + " & ".join(f"{int(row['observations']):,}" for row in columns) + r" \\",
        r"\bottomrule", r"\end{tabular}",
        r"\begin{tablenotes}[flushleft]", r"\footnotesize",
        r"\item \emph{Notes:} The table reports marginal effects from a pooled province-by-CNO4 panel. Madrid and Barcelona form one geographic group; all other provinces form the nonoverlapping comparison group. The adjustment and later periods cover event times 0--24 and 25--40, respectively. Regressions include province-by-CNO4, province-by-year-month, and CNO1-by-year-month fixed effects. Exposure is divided by 0.10, and standard errors are clustered by CNO4. Pre-treatment entries test the joint null over event times $-10$ through $-2$. The geographic-equality rows test whether the two group-specific exposure gradients are equal within each period. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "main_provinces_v1.tex", lines)


def _build_capability_table(tables_dir: Path) -> None:
    specs = ["nearest_common_frs_cno1_month", "frs_lm_cno1_month"]
    columns = [
        *[_phase_pair(tables_dir, spec, "ln_parados") for spec in specs],
        *[_phase_pair(tables_dir, spec, "ln_contratos") for spec in specs],
    ]
    _six_column_table(
        tables_dir,
        "capability_exposure_v1.tex",
        "Robustness to a capability-based AI exposure measure",
        "tab:v1_capability_exposure",
        columns,
        "Exposure score",
        "LM AIOE is the language-model capability score of Felten, Raj, and Seamans, mapped through the same SOC-to-CNO4 crosswalk as the baseline score. The LM AIOE columns measure a 10-percentile-point increase in its rank among matched occupations. The Anthropic columns re-estimate the preferred model on the same 444 matched CNO4 occupations, separating changes in exposure concept from changes in sample composition. All specifications include CNO4 and CNO1-by-year-month fixed effects and cluster standard errors by CNO4. Pre-trend entries test the joint null over event times $-10$ through $-2$. Because the measures use different scales, magnitudes should not be compared mechanically.",
        [
            r"Exposure measure & Anthropic & LM AIOE & Anthropic & LM AIOE \\",
            r"Exposure scale & 10 pp & 10 percentile points & 10 pp & 10 percentile points \\",
            _pretrend_row(tables_dir, specs),
        ],
    )


def _build_bls_table(tables_dir: Path) -> None:
    data = {
        outcome: pd.read_csv(tables_dir / f"bls_categorical_phase_{outcome}.csv")
        for outcome in ("ln_parados", "ln_contratos")
    }
    pretrend = {
        outcome: pd.read_csv(
            tables_dir / f"bls_categorical_pretrend_{outcome}.csv"
        )
        for outcome in ("ln_parados", "ln_contratos")
    }
    labels = {2: "Moderate", 3: "High", 4: "Very high"}
    lines = [
        r"\begin{table}[H]", r"\centering",
        r"\caption{Robustness to BLS categorical AI exposure}",
        r"\label{tab:v1_bls_exposure}", r"\begin{threeparttable}",
        r"\small", r"\setlength{\tabcolsep}{7pt}",
        r"\begin{tabular}{lcc}", r"\toprule",
        r"& \# of registered unemployed & \# of new contracts \\",
        r"& (1) & (2) \\", r"\midrule",
    ]
    for category, label in labels.items():
        lines.append(rf"\multicolumn{{3}}{{l}}{{\textbf{{{label} exposure}}}} \\")
        for phase, phase_label in [
            ("adjustment", "Adjustment period"),
            ("later", "Later period"),
        ]:
            rows = [
                _row(data[outcome], category=category, phase=phase)
                for outcome in ("ln_parados", "ln_contratos")
            ]
            lines.append(f"{phase_label} & " + " & ".join(_coef(row) for row in rows) + r" \\")
            lines.append(" & " + " & ".join(_se(row) for row in rows) + r" \\")
            lines.append(
                "Impact (percent) & "
                + " & ".join(f"{100 * float(row['estimate']):.1f}" for row in rows)
                + r" \\"
            )
        pretrend_values = [
            _format_pretrend_p(
                float(
                    _row(
                        pretrend[outcome],
                        category=category,
                        window="recent_-10_-2",
                        test="joint_equal_zero",
                    )["p_value"]
                )
            )
            for outcome in ("ln_parados", "ln_contratos")
        ]
        lines.append(
            "Pre-trend joint-null $p$-value & "
            + " & ".join(pretrend_values)
            + r" \\"
        )
        lines.append(r"\addlinespace")
    observations = [
        int(_row(data[outcome], category=2, phase="adjustment")["observations"])
        for outcome in ("ln_parados", "ln_contratos")
    ]
    lines += [
        r"\midrule",
        "Observations & " + " & ".join(f"{value:,}" for value in observations) + r" \\",
        r"\bottomrule", r"\end{tabular}",
        r"\begin{tablenotes}[flushleft]", r"\footnotesize",
        r"\item \emph{Notes:} Entries compare each BLS exposure category with low-exposure occupations. The BLS measure combines theoretical and observed-use indicators and classifies detailed SOC occupations as low, moderate, high, or very high exposure. It is mapped to CNO4 using the fixed SOC crosswalk and covers 501 of 502 occupations. Both regressions include CNO4 and CNO1-by-year-month fixed effects and cluster standard errors by CNO4. The adjustment and later periods cover event times 0--24 and 25--40; all pre-treatment months are omitted. Pre-trend entries test the joint null that event-study coefficients from event times $-10$ through $-2$ equal zero. Impact rows report 100 times the log-point coefficients. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "bls_categorical_exposure_v1.tex", lines)


def _build_three_group_feminization(tables_dir: Path) -> None:
    phase = {
        outcome: pd.read_csv(tables_dir / f"feminization_three_group_phase_{outcome}.csv")
        for outcome in ("ln_parados", "ln_contratos")
    }
    pretrend = {
        outcome: pd.read_csv(tables_dir / f"feminization_three_group_pretrend_{outcome}.csv")
        for outcome in ("ln_parados", "ln_contratos")
    }
    labels = {
        1: r"$F_j<p_{25}$",
        2: r"$p_{25}\leq F_j\leq p_{75}$",
        3: r"$F_j>p_{75}$",
    }
    lines = [
        r"\begin{table}[H]", r"\centering",
        r"\caption{AI exposure effects across occupational-feminization groups}",
        r"\label{tab:v1_feminization_three_group}", r"\begin{threeparttable}",
        r"\small", r"\setlength{\tabcolsep}{6pt}",
        r"\begin{tabular}{lcc}", r"\toprule",
        r"& \# of registered unemployed & \# of new contracts \\",
        r"& (1) & (2) \\", r"\midrule",
    ]
    for group, label in labels.items():
        lines.append(rf"\multicolumn{{3}}{{l}}{{\textbf{{{label}}}}} \\")
        for phase_name, phase_label in [
            ("adjustment", "AI exposure $\\times$ adjustment period"),
            ("later", "AI exposure $\\times$ later period"),
        ]:
            rows = [
                _row(phase[outcome], group=group, phase=phase_name)
                for outcome in ("ln_parados", "ln_contratos")
            ]
            lines.append(f"{phase_label} & " + " & ".join(_coef(row) for row in rows) + r" \\")
            lines.append(" & " + " & ".join(_se(row) for row in rows) + r" \\")
            lines.append(
                "Impact of a 10 pp increase (percent) & "
                + " & ".join(f"{100 * float(row['estimate']):.1f}" for row in rows)
                + r" \\"
            )
        pvalues = []
        for outcome in ("ln_parados", "ln_contratos"):
            selected = _row(
                pretrend[outcome],
                group=group,
                window="recent_-10_-2",
                test="joint_equal_zero",
            )
            pvalues.append(_format_pretrend_p(float(selected["p_value"])))
        lines.append("Pre-trend joint-null $p$-value & " + " & ".join(pvalues) + r" \\")
        lines.append(r"\addlinespace")
    observations = [
        int(_row(phase[outcome], group=1, phase="adjustment")["observations"])
        for outcome in ("ln_parados", "ln_contratos")
    ]
    lines += [
        r"\midrule",
        "Observations & " + " & ".join(f"{value:,}" for value in observations) + r" \\",
        r"\bottomrule", r"\end{tabular}",
        r"\begin{tablenotes}[flushleft]", r"\footnotesize",
        r"\item \emph{Notes:} The table augments the median specification by dividing occupations into three groups using the 25th and 75th percentiles of the predetermined CNO2 female-employment share. The cutoffs are computed across unique CNO2 groups, so each occupational family receives equal weight. Each column reports one regression with group-specific exposure gradients. All specifications include CNO4 and CNO1-by-year-month fixed effects and cluster standard errors by CNO4. Pre-trend entries test the joint null over event times $-10$ through $-2$. Entries are marginal effects, not ATTs.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "feminization_three_group_v1.tex", lines)


def _build_validation_table(tables_dir: Path) -> None:
    coverage = pd.read_csv(tables_dir / "alternative_exposure_comparison_v1.csv").iloc[0]
    lines = [
        r"\begin{table}[H]", r"\centering",
        r"\caption{Alternative AI exposure measures: mapping and rank correlation}",
        r"\label{tab:v1_alternative_exposure_validation}",
        r"\begin{threeparttable}", r"\small",
        r"\begin{tabular}{lcc}", r"\toprule",
        r"& BLS categories & LM AIOE \\",
        r"\midrule",
        f"Matched CNO4 occupations & {int(coverage['bls_matched_cno4'])} & {int(coverage['frs_lm_matched_cno4'])} " + r"\\",
        f"Spearman correlation with Anthropic exposure & {float(coverage['nearest_bls_spearman']):.3f} & {float(coverage['nearest_frs_lm_spearman']):.3f} " + r"\\",
        r"\bottomrule", r"\end{tabular}",
        r"\begin{tablenotes}[flushleft]", r"\footnotesize",
        r"\item \emph{Notes:} Both US measures are mapped to Spanish CNO4 occupations through the same nearest-neighbor SOC crosswalk used for the baseline Anthropic score. The BLS measure is a four-category composite that includes theoretical and observed-use inputs. LM AIOE is the language-model capability score of Felten, Raj, and Seamans. Correlations are computed across matched CNO4 occupations.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "alternative_exposure_validation_v1.tex", lines)


def _build_bls_table_v2(tables_dir: Path) -> None:
    specs = ("benchmark", "preferred", "preferred_no2021")
    outcomes = ("ln_parados", "ln_contratos")
    phase = {
        (spec, outcome): pd.read_csv(tables_dir / f"bls_categorical_phase_{spec}_{outcome}.csv")
        for spec in specs for outcome in outcomes
    }
    pretrend = {
        (spec, outcome): pd.read_csv(tables_dir / f"bls_categorical_pretrend_{spec}_{outcome}.csv")
        for spec in specs for outcome in outcomes
    }
    labels = {2: "Moderate exposure", 3: "High exposure", 4: "Very high exposure"}
    lines = [
        r"\begin{table}[H]", r"\centering",
        r"\caption{Robustness to BLS categorical AI exposure}",
        r"\label{tab:v1_bls_exposure}", r"\begin{threeparttable}", r"\scriptsize",
        r"\setlength{\tabcolsep}{3pt}", r"\begin{tabular}{lcccccc}", r"\toprule",
        r"& \multicolumn{3}{c}{\# of registered unemployed} & \multicolumn{3}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
        r"& (1) & (2) & (3) & (4) & (5) & (6) \\", r"\midrule",
    ]
    for category, label in labels.items():
        lines.append(rf"\multicolumn{{7}}{{l}}{{\textbf{{{label}}}}} \\")
        for phase_name, phase_label in (("adjustment", "Adjustment period"), ("later", "Later period")):
            rows = [
                _row(phase[(spec, outcome)], category=category, phase=phase_name)
                for outcome in outcomes for spec in specs
            ]
            lines.append(phase_label + " & " + " & ".join(_coef(row) for row in rows) + r" \\")
            lines.append(" & " + " & ".join(_se(row) for row in rows) + r" \\")
        pvalues = [
            _format_pretrend_p(float(_row(
                pretrend[(spec, outcome)], category=category,
                window="full_-21_-2", test="joint_equal_zero"
            )["p_value"]))
            for outcome in outcomes for spec in specs
        ]
        lines.append("Pre-treatment joint-null $p$-value & " + " & ".join(pvalues) + r" \\")
        lines.append(r"\addlinespace[4pt]")
    observations = [
        int(_row(phase[(spec, outcome)], category=2, phase="adjustment")["observations"])
        for outcome in outcomes for spec in specs
    ]
    lines += [
        r"\midrule",
        r"CNO1 $\times$ year-month FE & No & Yes & Yes & No & Yes & Yes \\",
        r"2021 included & Yes & Yes & No & Yes & Yes & No \\",
        "Observations & " + " & ".join(f"{value:,}" for value in observations) + r" \\",
        r"\bottomrule", r"\end{tabular}", r"\begin{tablenotes}[flushleft]", r"\footnotesize",
        r"\item \emph{Notes:} Entries compare moderate-, high-, and very-high-exposure occupations with the BLS low-exposure category. The BLS classification combines capability and observed-use evidence and is mapped to Spanish CNO4 occupations through the fixed SOC crosswalk. The adjustment and later periods cover event times 0--24 and 25--40. Columns 1 and 4 include CNO4 and year-month fixed effects; the remaining columns include CNO4 and CNO1-by-year-month fixed effects. Columns 3 and 6 exclude 2021. Standard errors are clustered by CNO4. Diagnostic rows test the joint null over all available pre-treatment coefficients. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "bls_categorical_exposure_v1.tex", lines)


def _build_three_group_feminization_v2(tables_dir: Path) -> None:
    specs = (("full", "Yes"), ("no2021", "No"))
    outcomes = ("ln_parados", "ln_contratos")
    data = {
        (spec, outcome): pd.read_csv(
            tables_dir / f"feminization_three_group_phase_{spec}_{outcome}.csv"
        ) for spec, _ in specs for outcome in outcomes
    }
    labels = {1: r"$F_j<p_{25}$", 2: r"$p_{25}\leq F_j\leq p_{75}$", 3: r"$F_j>p_{75}$"}
    lines = [
        r"\begin{table}[H]", r"\centering",
        r"\caption{AI exposure effects across occupational-feminization groups}",
        r"\label{tab:v1_feminization_three_group}", r"\begin{threeparttable}", r"\small",
        r"\setlength{\tabcolsep}{5pt}", r"\begin{tabular}{lcccc}", r"\toprule",
        r"& \multicolumn{2}{c}{\# of registered unemployed} & \multicolumn{2}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}", r"& (1) & (2) & (3) & (4) \\", r"\midrule",
    ]
    for group, label in labels.items():
        lines.append(rf"\multicolumn{{5}}{{l}}{{\textbf{{{label}}}}} \\")
        for phase_name, phase_label in (("adjustment", "AI exposure $\\times$ adjustment period"), ("later", "AI exposure $\\times$ later period")):
            rows = [
                _row(data[(spec, outcome)], group=group, phase=phase_name)
                for outcome in outcomes for spec, _ in specs
            ]
            lines.append(phase_label + " & " + " & ".join(_coef(row) for row in rows) + r" \\")
            lines.append(" & " + " & ".join(_se(row) for row in rows) + r" \\")
        lines.append(r"\addlinespace[4pt]")
    observations = [
        int(_row(data[(spec, outcome)], group=1, phase="adjustment")["observations"])
        for outcome in outcomes for spec, _ in specs
    ]
    lines += [
        r"\midrule", r"2021 included & Yes & No & Yes & No \\",
        "Observations & " + " & ".join(f"{value:,}" for value in observations) + r" \\",
        r"\bottomrule", r"\end{tabular}", r"\begin{tablenotes}[flushleft]", r"\footnotesize",
        r"\item \emph{Notes:} Occupations are grouped using the 25th and 75th percentiles of the predetermined CNO2 female-employment share. Each column reports one regression with group-specific exposure gradients. Columns 1 and 3 use the full sample; columns 2 and 4 exclude 2021. All specifications include CNO4 and CNO1-by-year-month fixed effects and cluster standard errors by CNO4. The adjustment and later periods cover event times 0--24 and 25--40. Entries are marginal effects of a 10 percentage-point increase in exposure, not ATTs. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "feminization_three_group_v1.tex", lines)


def _build_main_province_table_v2(tables_dir: Path) -> None:
    outcomes = ("ln_parados", "ln_contratos")
    groups = ((1, "Madrid and Barcelona"), (2, "Rest of Spain"))
    samples = (("", "Yes"), ("_no2021", "No"))
    phase = {
        (suffix, outcome): pd.read_csv(
            tables_dir / f"twfe_phase_mainprovince_comparison{suffix}_{outcome}.csv"
        )
        for suffix, _ in samples for outcome in outcomes
    }
    pretrend = {
        (suffix, outcome): pd.read_csv(
            tables_dir / f"twfe_pretrend_mainprovince_comparison{suffix}_{outcome}.csv"
        )
        for suffix, _ in samples for outcome in outcomes
    }
    order = [(suffix, included, group_id, group_label)
             for suffix, included in samples for group_id, group_label in groups]

    def rows_for(phase_name: str) -> list[pd.Series]:
        return [
            _row(phase[(suffix, outcome)], group_id=group_id, phase=phase_name)
            for outcome in outcomes for suffix, _, group_id, _ in order
        ]

    adjustment = rows_for("adjustment")
    later = rows_for("later")
    pvalues = [
        _format_pretrend_p(float(_row(
            pretrend[(suffix, outcome)], geographic_group=group_label,
            window="full_-21_-2", test="joint_equal_zero"
        )["p_value"]))
        for outcome in outcomes for suffix, _, _, group_label in order
    ]

    def panel_block(panel_label: str, start: int, column_numbers: tuple[int, ...]) -> list[str]:
        stop = start + 4
        adjustment_panel = adjustment[start:stop]
        later_panel = later[start:stop]
        return [
            rf"\multicolumn{{5}}{{l}}{{\textbf{{{panel_label}}}}} \\",
            " & " + " & ".join(f"({number})" for number in column_numbers) + r" \\",
            r"\midrule",
            "AI exposure $\\times$ adjustment period & "
            + " & ".join(_coef(row) for row in adjustment_panel) + r" \\",
            " & " + " & ".join(_se(row) for row in adjustment_panel) + r" \\",
            "AI exposure $\\times$ later period & "
            + " & ".join(_coef(row) for row in later_panel) + r" \\",
            " & " + " & ".join(_se(row) for row in later_panel) + r" \\",
            r"\midrule",
            r"Geographic sample & MAD \& BCN & Rest & MAD \& BCN & Rest \\",
            r"2021 included & Yes & Yes & No & No \\",
            "Pre-treatment joint-null $p$-value & "
            + " & ".join(pvalues[start:stop]) + r" \\",
            "$p$-value: equal phase effects & "
            + " & ".join(
                f"{float(row['phase_equality_p']):.3f}" for row in adjustment_panel
            )
            + r" \\",
            "$p$-value: equal geography, adjustment & "
            + f"\\multicolumn{{2}}{{c}}{{{float(adjustment_panel[0]['between_group_p']):.3f}}} & "
            + f"\\multicolumn{{2}}{{c}}{{{float(adjustment_panel[2]['between_group_p']):.3f}}}"
            + r" \\",
            "$p$-value: equal geography, later & "
            + f"\\multicolumn{{2}}{{c}}{{{float(later_panel[0]['between_group_p']):.3f}}} & "
            + f"\\multicolumn{{2}}{{c}}{{{float(later_panel[2]['between_group_p']):.3f}}}"
            + r" \\",
            "Observations & "
            + " & ".join(f"{int(row['observations']):,}" for row in adjustment_panel)
            + r" \\",
        ]

    lines = [
        r"\begin{table}[H]", r"\centering",
        r"\caption{Geographic heterogeneity in AI exposure effects}",
        r"\label{tab:v1_main_provinces}",
        r"\begin{threeparttable}",
        r"\small", r"\setlength{\tabcolsep}{5pt}",
        r"\begin{tabular}{@{}lcccc@{}}", r"\toprule",
        *panel_block("Panel A. Number of registered unemployed", 0, (1, 2, 3, 4)),
        r"\addlinespace[6pt]", r"\midrule",
        *panel_block("Panel B. Number of new contracts", 4, (5, 6, 7, 8)),
        r"\bottomrule", r"\end{tabular}",
        r"\begin{tablenotes}[flushleft]", r"\footnotesize",
        r"\item \emph{Notes:} The table reports marginal effects from a pooled province-by-CNO4 panel. MAD \& BCN denotes Madrid and Barcelona pooled together; Rest denotes all other Spanish provinces. Columns 1--2 and 5--6 use the full sample; columns 3--4 and 7--8 exclude 2021. The adjustment and later periods cover event times 0--24 and 25--40. Regressions include province-by-CNO4, province-by-year-month, and CNO1-by-year-month fixed effects. Exposure is divided by 0.10, and standard errors are clustered by CNO4. Pre-treatment entries test the joint null over all available pre-treatment coefficients. The geographic-equality rows test whether the two group-specific exposure gradients are equal within each period. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "main_provinces_v1.tex", lines)


def _build_external_exposure_tables(tables_dir: Path) -> None:
    definitions = [
        ("nearest_common_frs", "anthropic_matched_exposure_v1.tex",
         "Anthropic exposure on the common matched sample",
         "tab:v1_anthropic_matched_exposure", "AI exposure",
         "The table re-estimates the Anthropic exposure model on occupations matched to LM AIOE, holding sample composition fixed. Exposure is divided by 0.10."),
        ("frs_lm", "lm_aioe_exposure_v1.tex",
         "Robustness to LM AIOE exposure",
         "tab:v1_lm_aioe_exposure", "LM AIOE exposure",
         "LM AIOE measures occupational exposure to language-model capabilities and is mapped to CNO4 through the fixed SOC crosswalk. Coefficients correspond to a 10-percentile-point increase."),
    ]
    for stem, filename, caption, label, row_label, description in definitions:
        specs = [f"{stem}_benchmark", f"{stem}_cno1_month", f"{stem}_cno1_month_no2021"]
        columns = [
            *[_phase_pair(tables_dir, spec, "ln_parados") for spec in specs],
            *[_phase_pair(tables_dir, spec, "ln_contratos") for spec in specs],
        ]
        extra_rows = [
            r"CNO1 $\times$ year-month FE & No & Yes & Yes & No & Yes & Yes \\",
            r"2021 included & Yes & Yes & No & Yes & Yes & No \\",
            _pretrend_row(tables_dir, specs),
        ]
        include_phase_equality = stem != "frs_lm"
        if stem == "frs_lm":
            extra_rows.append(
                "$p$-value: equal phase effects & "
                + " & ".join(_p_equal(column) for column in columns)
                + r" \\"
            )
        _six_column_table(
            tables_dir, filename, caption, label, columns, row_label,
            description + " The adjustment and later periods cover event times 0--24 and 25--40. Columns 1 and 4 include CNO4 and year-month fixed effects; the remaining columns include CNO4 and CNO1-by-year-month fixed effects. Columns 3 and 6 exclude 2021. Standard errors are clustered by CNO4. The pre-treatment row tests the joint null over all available pre-treatment event-study coefficients; the phase-equality row tests whether the adjustment- and later-period coefficients are equal. Entries are marginal effects, not ATTs. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
            extra_rows,
            include_phase_equality=include_phase_equality,
            include_impact=False,
            separate_phases=False,
        )


def build_refinement_outputs(
    project_root: str | Path,
    estimates_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> pd.DataFrame:
    root = Path(project_root)
    tables_dir = Path(estimates_dir) if estimates_dir is not None else root / "intermediate"
    figures_dir = (
        Path(output_dir)
        if output_dir is not None
        else root / "rendered"
    )
    figures_dir.mkdir(parents=True, exist_ok=True)

    _build_main_province_table_v2(tables_dir)
    _build_external_exposure_tables(tables_dir)
    _build_bls_table_v2(tables_dir)
    _build_three_group_feminization_v2(tables_dir)
    _build_validation_table(tables_dir)

    for outcome, label, ylim, step in [
        ("ln_parados", "unemployed", (-0.10, 0.15), 0.05),
        ("ln_contratos", "contracts", (-0.30, 0.30), 0.10),
    ]:
        # This unemployment panel retains the original boxed-axis style.
        with plt.rc_context(matplotlib.rcParamsDefault if outcome == "ln_parados" else {}):
            _render_group_event(
                tables_dir / f"twfe_event_mainprovince_comparison_{outcome}.csv",
                figures_dir / f"MainProvince_comparison_{label}.png",
                "group_id",
                {1: "Madrid and Barcelona", 2: "Rest of Spain"},
                (-0.05, 0.075) if outcome == "ln_parados" else ylim,
                0.025 if outcome == "ln_parados" else step,
            )
        _render_single_event(
            tables_dir / f"twfe_event_frs_lm_cno1_month_{outcome}.csv",
            figures_dir / f"CapabilityExposure_{label}.png",
            (-0.025, 0.025) if outcome == "ln_parados" else ylim,
            0.025 if outcome == "ln_parados" else step,
        )
        _render_group_event(
            tables_dir / f"bls_categorical_event_preferred_{outcome}.csv",
            figures_dir / f"BLSExposure_{label}.png",
            "category",
            {2: "Moderate", 3: "High", 4: "Very high"},
            ylim,
            step,
        )
        _render_group_event(
            tables_dir / f"feminization_three_group_event_{outcome}.csv",
            figures_dir / f"Feminization_three_group_{label}.png",
            "group",
            {1: "Below p25", 2: "p25 to p75", 3: "Above p75"},
            ylim,
            step,
        )

    outputs = [
        "main_provinces_v1.tex",
        "anthropic_matched_exposure_v1.tex",
        "lm_aioe_exposure_v1.tex",
        "bls_categorical_exposure_v1.tex",
        "feminization_three_group_v1.tex",
        "alternative_exposure_validation_v1.tex",
    ]
    return pd.DataFrame(
        {"output": outputs, "exists": [(tables_dir / name).exists() for name in outputs]}
    )
