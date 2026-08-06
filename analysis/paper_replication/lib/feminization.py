"""Prepare and present the V1 occupational-feminization analysis."""

from __future__ import annotations

from pathlib import Path
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


NAVY = "#08519C"
SKY = "#56B4E9"
GREY = "#7F8C8D"
EVENT_MIN = -21
EVENT_MAX = 40


def _epa_number(value: object) -> float:
    if pd.isna(value) or str(value).strip() in {"", ".."}:
        return np.nan
    return float(str(value).replace(".", "").replace(",", "."))


def _feminization_window(frame: pd.DataFrame, start: tuple[int, int], end: tuple[int, int]) -> pd.DataFrame:
    start_index = start[0] * 4 + start[1]
    end_index = end[0] * 4 + end[1]
    selected = frame.loc[frame["quarter_index"].between(start_index, end_index)].copy()
    pooled = (
        selected.groupby(["cno2", "occupation_cno2", "sex"], as_index=False)["employment"]
        .sum(min_count=1)
        .pivot(index=["cno2", "occupation_cno2"], columns="sex", values="employment")
        .reset_index()
    )
    pooled["female_share"] = pooled["Mujeres"] / (pooled["Mujeres"] + pooled["Hombres"])
    return pooled[["cno2", "occupation_cno2", "female_share"]]


def prepare_gender_composition_inputs(
    project_root: str | Path,
    input_dir: str | Path | None = None,
    audit_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Create the estimation panels used by the Stata gender analysis."""

    root = Path(project_root)
    raw_dir = root / "data" / "raw"
    input_dir = Path(input_dir) if input_dir is not None else root / "data" / "prepared"
    tables_dir = Path(audit_dir) if audit_dir is not None else root / "intermediate"
    input_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    epa_path = raw_dir / "ine_epa_ocupados_65134.csv"
    epa = pd.read_csv(epa_path, sep=";", dtype=str, encoding_errors="replace")
    occupation_column, sex_column, unit_column, period_column, value_column = epa.columns
    epa = epa.loc[
        epa[occupation_column].str.match(r"^\d{2}\s", na=False)
        & epa[unit_column].eq("Valor absoluto")
        & epa[sex_column].isin(["Hombres", "Mujeres"])
    ].copy()
    epa["cno2"] = epa[occupation_column].str[:2]
    epa["occupation_cno2"] = epa[occupation_column].str[3:]
    epa["sex"] = epa[sex_column]
    epa["year"] = epa[period_column].str[:4].astype(int)
    epa["quarter"] = epa[period_column].str[-1].astype(int)
    epa["quarter_index"] = epa["year"] * 4 + epa["quarter"]
    epa["employment"] = epa[value_column].map(_epa_number)

    main_index = _feminization_window(epa, (2017, 1), (2019, 4)).rename(
        columns={"female_share": "feminization_2017_2019"}
    )
    sample_pre_index = _feminization_window(epa, (2021, 1), (2022, 3)).rename(
        columns={"female_share": "feminization_2021q1_2022q3"}
    )
    feminization = main_index.merge(
        sample_pre_index[["cno2", "feminization_2021q1_2022q3"]],
        on="cno2",
        how="left",
        validate="one_to_one",
    )
    feminization["feminization_change"] = (
        feminization["feminization_2021q1_2022q3"]
        - feminization["feminization_2017_2019"]
    )
    feminization.to_csv(tables_dir / "cno2_feminization_index_v1.csv", index=False)

    total = pd.read_csv(input_dir / "est_total_cno4.csv", dtype={"cno4": str, "cno2": str})
    total["cno4"] = total["cno4"].str.zfill(4)
    total["cno2"] = total["cno2"].str.zfill(2)

    occupation_index = (
        total[["cno4", "cno2", "cno1d", "exposure_nearest"]]
        .drop_duplicates("cno4")
        .merge(feminization, on="cno2", how="left", validate="many_to_one")
    )
    if occupation_index["feminization_2017_2019"].isna().any():
        missing = occupation_index.loc[
            occupation_index["feminization_2017_2019"].isna(), "cno2"
        ].drop_duplicates().tolist()
        raise ValueError(f"Missing EPA feminization index for CNO2 groups: {missing}")

    percentiles = occupation_index["feminization_2017_2019"].quantile([0.25, 0.50, 0.75])
    median = float(percentiles.loc[0.50])
    percentile_table = pd.DataFrame(
        {
            "percentile": [25, 50, 75],
            "female_share": [percentiles.loc[0.25], percentiles.loc[0.50], percentiles.loc[0.75]],
        }
    )
    percentile_table["female_share_10pp_centered"] = (
        percentile_table["female_share"] - median
    ) / 0.10
    percentile_table.to_csv(tables_dir / "feminization_percentiles_v1.csv", index=False)

    index_columns = [
        "cno2", "occupation_cno2", "feminization_2017_2019",
        "feminization_2021q1_2022q3", "feminization_change",
    ]
    composition = total.merge(
        feminization[index_columns], on="cno2", how="left", validate="many_to_one"
    )
    composition["feminization_10pp_centered"] = (
        composition["feminization_2017_2019"] - median
    ) / 0.10
    composition["feminization_above_median"] = (
        composition["feminization_10pp_centered"] >= 0
    ).astype(int)
    composition.to_csv(input_dir / "est_feminization_cno4.csv", index=False)

    exposure_correlation = occupation_index["exposure_nearest"].corr(
        occupation_index["feminization_2017_2019"]
    )
    occupation_index["exposure_within_cno1"] = occupation_index["exposure_nearest"] - (
        occupation_index.groupby("cno1d")["exposure_nearest"].transform("mean")
    )
    occupation_index["feminization_within_cno1"] = occupation_index["feminization_2017_2019"] - (
        occupation_index.groupby("cno1d")["feminization_2017_2019"].transform("mean")
    )
    within_cno1_correlation = occupation_index["exposure_within_cno1"].corr(
        occupation_index["feminization_within_cno1"]
    )
    stability_correlation = feminization["feminization_2017_2019"].corr(
        feminization["feminization_2021q1_2022q3"]
    )
    validation = pd.DataFrame(
        [
            {
                "cno2_groups": len(feminization),
                "mapped_cno4": occupation_index["cno4"].nunique(),
                "epa_window_main": "2017Q1-2019Q4",
                "epa_window_robustness": "2021Q1-2022Q3",
                "feminization_stability_correlation": stability_correlation,
                "exposure_feminization_correlation_cno4": exposure_correlation,
                "exposure_feminization_correlation_within_cno1": within_cno1_correlation,
                "female_share_p25": percentiles.loc[0.25],
                "female_share_p50": percentiles.loc[0.50],
                "female_share_p75": percentiles.loc[0.75],
                "composition_rows": len(composition),
            }
        ]
    )
    validation.to_csv(tables_dir / "feminization_validation_v1.csv", index=False)
    return validation


def _stars(estimate: float, se: float) -> str:
    if pd.isna(estimate) or pd.isna(se) or se <= 0:
        return ""
    p_value = math.erfc(abs(estimate / se) / math.sqrt(2))
    if p_value < 0.01:
        return "***"
    if p_value < 0.05:
        return "**"
    if p_value < 0.10:
        return "*"
    return ""


def _coef(row: pd.Series, digits: int = 3) -> str:
    suffix = _stars(float(row["estimate"]), float(row["se"]))
    value = f"{float(row['estimate']):.{digits}f}"
    return value + (rf"$^{{{suffix}}}$" if suffix else "")


def _se(row: pd.Series, digits: int = 3) -> str:
    return f"({float(row['se']):.{digits}f})"


def _pvalue(value: float) -> str:
    return "$<0.001$" if float(value) < 0.001 else f"{float(value):.3f}"


def _write_tex(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _event_frame(path: Path, estimand: str | None = None, percentile: int | None = None) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if estimand is not None:
        frame = frame.loc[frame["estimand"].eq(estimand)]
    if percentile is not None:
        frame = frame.loc[frame["percentile"].eq(percentile)]
    return frame.sort_values("event_time").copy()


def _render_single_event(frame: pd.DataFrame, destination: Path, ylabel: str, ylim: tuple[float, float]) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    ax.fill_between(
        frame["event_time"].to_numpy(float), frame["ci_low"].to_numpy(float),
        frame["ci_high"].to_numpy(float), color=SKY, alpha=0.25, linewidth=0,
    )
    ax.plot(frame["event_time"], frame["estimate"], color=NAVY, linewidth=1.25)
    ax.scatter(frame["event_time"], frame["estimate"], color=NAVY, s=9, zorder=3)
    ax.axhline(0, color=GREY, linewidth=0.7)
    ax.axvline(0, color=GREY, linestyle="--", linewidth=0.8)
    ax.set_xlim(EVENT_MIN, EVENT_MAX)
    ax.set_ylim(*ylim)
    ax.set_xticks(np.arange(-20, 41, 10))
    ax.set_xlabel("Months relative to November 2022")
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    fig.savefig(destination, bbox_inches="tight", dpi=320)
    plt.close(fig)


def _render_two_gender_event(frame: pd.DataFrame, destination: Path, ylim: tuple[float, float]) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    styles = {"men": (GREY, "--", "Men"), "women": (NAVY, "-", "Women")}
    for estimand in ("men", "women"):
        subset = frame.loc[frame["estimand"].eq(estimand)].sort_values("event_time")
        color, linestyle, label = styles[estimand]
        ax.plot(subset["event_time"], subset["estimate"], color=color, linestyle=linestyle,
                linewidth=1.3, label=label)
    ax.axhline(0, color=GREY, linewidth=0.7)
    ax.axvline(0, color=GREY, linestyle=":", linewidth=0.8)
    ax.set_xlim(EVENT_MIN, EVENT_MAX)
    ax.set_ylim(*ylim)
    ax.set_xticks(np.arange(-20, 41, 10))
    ax.set_xlabel("Months relative to November 2022")
    ax.set_ylabel("Marginal effect")
    ax.legend(frameon=False, loc="upper left", ncol=2)
    fig.tight_layout()
    fig.savefig(destination, bbox_inches="tight", dpi=320)
    plt.close(fig)


def _render_two_group_event(frame: pd.DataFrame, destination: Path, ylim: tuple[float, float]) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    styles = {
        "below_median": (GREY, "--", "Below median"),
        "above_or_equal_median": (NAVY, "-", "At or above median"),
    }
    for group, (color, linestyle, label) in styles.items():
        subset = frame.loc[frame["group"].eq(group)].sort_values("event_time")
        ax.fill_between(
            subset["event_time"].to_numpy(float),
            subset["ci_low"].to_numpy(float),
            subset["ci_high"].to_numpy(float),
            color=color, alpha=0.16, linewidth=0,
        )
        ax.plot(
            subset["event_time"], subset["estimate"], color=color,
            linestyle=linestyle, linewidth=1.25, label=label,
        )
        ax.scatter(subset["event_time"], subset["estimate"], color=color, s=9, zorder=3)
    ax.axhline(0, color=GREY, linewidth=0.7)
    ax.axvline(0, color=GREY, linestyle="--", linewidth=0.8)
    ax.set_xlim(EVENT_MIN, EVENT_MAX)
    ax.set_ylim(*ylim)
    ax.set_xticks(np.arange(-20, 41, 10))
    ax.set_xlabel("Months relative to November 2022")
    ax.set_ylabel("Marginal effect")
    ax.legend(frameon=False, loc="upper left", ncol=1)
    fig.tight_layout()
    fig.savefig(destination, bbox_inches="tight", dpi=320)
    plt.close(fig)


def _row(frame: pd.DataFrame, **conditions: object) -> pd.Series:
    selected = frame.copy()
    for column, value in conditions.items():
        selected = selected.loc[selected[column].eq(value)]
    if len(selected) != 1:
        raise ValueError(f"Expected one result for {conditions}, found {len(selected)}")
    return selected.iloc[0]

def build_feminization_outputs(
    project_root: str | Path,
    input_dir: str | Path | None = None,
    estimates_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Build only the continuous and median-split feminization outputs."""

    root = Path(project_root)
    input_dir = Path(input_dir) if input_dir is not None else root / "data" / "prepared"
    tables_dir = Path(estimates_dir) if estimates_dir is not None else root / "intermediate"
    figures_dir = Path(output_dir) if output_dir is not None else root / "figuresNtables"
    figures_dir.mkdir(parents=True, exist_ok=True)

    outcomes = {"ln_parados": "unemployed", "ln_contratos": "contracts"}
    continuous = {
        outcome: pd.read_csv(tables_dir / f"feminization_phase_{outcome}.csv")
        for outcome in outcomes
    }
    median_split = {
        outcome: pd.read_csv(tables_dir / f"feminization_median_phase_{outcome}.csv")
        for outcome in outcomes
    }

    main_lines = [
        r"\begin{table}[!htbp]", r"\centering",
        r"\caption{AI exposure and occupational feminization}",
        r"\label{tab:v1_feminization_main}", r"\begin{threeparttable}",
        r"\scriptsize", r"\setlength{\tabcolsep}{3.5pt}",
        r"\begin{tabular}{lcccccc}", r"\toprule",
        r"& \multicolumn{3}{c}{\# of registered unemployed} & \multicolumn{3}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
        r"& 25th pct. & Median & 75th pct. & 25th pct. & Median & 75th pct. \\",
        r"\midrule",
    ]
    for phase, label in [("adjustment", "AI exposure $\\times$ adjustment period"),
                         ("later", "AI exposure $\\times$ later period")]:
        rows = [
            _row(continuous[outcome], phase=phase, percentile=percentile)
            for outcome in outcomes for percentile in (25, 50, 75)
        ]
        main_lines.append(label + " & " + " & ".join(_coef(row) for row in rows) + r" \\")
        main_lines.append(" & " + " & ".join(_se(row) for row in rows) + r" \\")
        main_lines.append(
            "Impact of a 10 pp increase (percent) & "
            + " & ".join(f"{100*float(row['estimate']):.1f}" for row in rows) + r" \\")
        main_lines.append(r"\addlinespace")
    observations = [
        int(_row(continuous[outcome], phase="adjustment", percentile=percentile)["observations"])
        for outcome in outcomes for percentile in (25, 50, 75)
    ]
    main_lines += [
        "Observations & " + " & ".join(f"{value:,}" for value in observations) + r" \\",
        r"CNO4 FE & Yes & Yes & Yes & Yes & Yes & Yes \\",
        r"CNO1 $\times$ year-month FE & Yes & Yes & Yes & Yes & Yes & Yes \\",
        r"Clustered standard errors & CNO4 & CNO4 & CNO4 & CNO4 & CNO4 & CNO4 \\",
        r"\bottomrule", r"\end{tabular}", r"\begin{tablenotes}[flushleft]", r"\footnotesize",
        r"\item \emph{Notes:} Entries are marginal effects of a 10 percentage-point increase in AI exposure, evaluated at the indicated percentiles of the predetermined CNO2 female-employment share. The index is the female share of EPA employment pooled over 2017--2019; its 25th percentile, median, and 75th percentile are 0.234, 0.303, and 0.539. The adjustment and later periods cover event times 0--24 and 25--40. The specification includes CNO4 and CNO1-by-year-month fixed effects. Standard errors in parentheses are clustered by CNO4. Entries are marginal effects, not ATTs. The impact rows report 100 times the log-point coefficients and carry no additional significance markers. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "occupational_feminization_main_v1.tex", main_lines)

    median_lines = [
        r"\begin{table}[!htbp]", r"\centering",
        r"\caption{AI exposure effects by occupational feminization}",
        r"\label{tab:v1_feminization_median_split}", r"\begin{threeparttable}",
        r"\small", r"\setlength{\tabcolsep}{5pt}",
        r"\begin{tabular}{@{}p{0.58\textwidth}>{\centering\arraybackslash}p{0.17\textwidth}>{\centering\arraybackslash}p{0.17\textwidth}@{}}", r"\toprule",
        r"& (1) & (2) \\",
        r"& \# of registered unemployed & \# of new contracts \\",
        r"\midrule",
    ]
    for phase_index, (phase, phase_label) in enumerate([
        ("adjustment", "Panel A. Adjustment period"),
        ("later", "Panel B. Later post-treatment period"),
    ]):
        median_lines.append(rf"\multicolumn{{3}}{{l}}{{\textbf{{{phase_label}}}}} \\")
        for group, group_label in [
            ("below_median", r"$\mathbb{1}\{F_i < \widetilde F\}$"),
            ("above_or_equal_median", r"$\mathbb{1}\{F_i \geq \widetilde F\}$"),
        ]:
            unemployed = _row(median_split["ln_parados"], phase=phase, group=group)
            contracts = _row(median_split["ln_contratos"], phase=phase, group=group)
            median_lines += [
                f"AI exposure $\\times$ {group_label} & {_coef(unemployed)} & {_coef(contracts)} " + r"\\",
                " & " + _se(unemployed) + " & " + _se(contracts) + r"\\",
                r"\quad Impact of a 10 pp increase (percent) & "
                f"{100*float(unemployed['estimate']):.1f} & {100*float(contracts['estimate']):.1f} " + r"\\",
            ]
        if phase_index == 0:
            median_lines.append(r"\addlinespace[2pt]")
    observations_unemployed = int(_row(median_split["ln_parados"], phase="adjustment", group="below_median")["observations"])
    observations_contracts = int(_row(median_split["ln_contratos"], phase="adjustment", group="below_median")["observations"])
    median_lines += [
        f"Observations & {observations_unemployed:,} & {observations_contracts:,} " + r"\\",
        r"CNO4 FE & Yes & Yes \\",
        r"CNO1 $\times$ year-month FE & Yes & Yes \\",
        r"Clustered standard errors & CNO4 & CNO4 \\",
        r"\bottomrule", r"\end{tabular}", r"\begin{tablenotes}[flushleft]", r"\footnotesize",
        r"\item \emph{Notes:} Each column reports one regression: column 1 uses registered unemployment and column 2 uses new contracts. The rows report linear combinations of the exposure-by-period-by-group coefficients from that regression. The indicators equal one for occupations below the CNO2 female-employment-share median of 0.303 or at or above it, respectively. The adjustment and later periods cover event times 0--24 and 25--40. Exposure is measured in ten-percentage-point units. Standard errors in parentheses are clustered by CNO4. Entries are marginal effects, not ATTs; the impact rows report 100 times the corresponding log-point coefficient and carry no additional significance markers. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "feminization_median_split_v1.tex", median_lines)

    continuous_pretrends = {
        outcome: pd.read_csv(tables_dir / f"feminization_pretrend_{outcome}.csv")
        for outcome in outcomes
    }
    median_pretrends = {
        outcome: pd.read_csv(tables_dir / f"feminization_median_pretrend_{outcome}.csv")
        for outcome in outcomes
    }
    detrended_pretrends = {
        outcome: pd.read_csv(tables_dir / f"feminization_median_pretrend_detrended_{outcome}.csv")
        for outcome in outcomes
    }
    pretrend_lines = [
        r"\begin{table}[!htbp]", r"\centering",
        r"\caption{Pre-treatment diagnostics for feminization specifications}",
        r"\label{tab:v1_feminization_pretrends}", r"\begin{threeparttable}", r"\small",
        r"\begin{tabular}{llcc}", r"\toprule",
        r"Outcome & Specification & Joint nullity & Joint equality \\", r"\midrule",
        r"\multicolumn{4}{l}{\textbf{Panel A. Continuous feminization}} \\",
    ]
    for outcome, label in [("ln_parados", "Registered unemployed"),
                           ("ln_contratos", "New contracts")]:
        for percentile in (25, 50, 75):
            frame = continuous_pretrends[outcome]
            zero = _row(frame, percentile=percentile, test="joint_equal_zero")
            equal = _row(frame, percentile=percentile, test="joint_equal_coefficients")
            pretrend_lines.append(
                f"{label} & {percentile}th percentile & {_pvalue(zero['p_value'])} & {_pvalue(equal['p_value'])} " + r"\\"
            )
    pretrend_lines += [r"\midrule", r"\multicolumn{4}{l}{\textbf{Panel B. Median split}} \\"]
    for outcome, label in [("ln_parados", "Registered unemployed"),
                           ("ln_contratos", "New contracts")]:
        for group, group_label in [("below_median", "Below median"),
                                   ("above_or_equal_median", "At or above median")]:
            frame = median_pretrends[outcome]
            zero = _row(frame, group=group, test="joint_equal_zero")
            equal = _row(frame, group=group, test="joint_equal_coefficients")
            pretrend_lines.append(
                f"{label} & {group_label} & {_pvalue(zero['p_value'])} & {_pvalue(equal['p_value'])} " + r"\\"
            )
    pretrend_lines += [r"\midrule", r"\multicolumn{4}{l}{\textbf{Panel C. Median split with detrended outcomes}} \\"]
    for outcome, label in [("ln_parados", "Registered unemployed"),
                           ("ln_contratos", "New contracts")]:
        for group, group_label in [("below_median", "Below median"),
                                   ("above_or_equal_median", "At or above median")]:
            frame = detrended_pretrends[outcome]
            zero = _row(frame, group=group, test="joint_equal_zero")
            equal = _row(frame, group=group, test="joint_equal_coefficients")
            pretrend_lines.append(
                f"{label} & {group_label} & {_pvalue(zero['p_value'])} & {_pvalue(equal['p_value'])} " + r"\\"
            )
    pretrend_lines += [
        r"\bottomrule", r"\end{tabular}", r"\begin{tablenotes}[flushleft]", r"\footnotesize",
        r"\item \emph{Notes:} Entries are $p$-values from tests of event-study coefficients over event times $-21$ through $-2$; October 2022 is the omitted month. The joint-nullity test sets all coefficients in the window equal to zero. The joint-equality test permits a common nonzero level but requires the coefficients to be equal to one another. Panel A evaluates continuous-feminization marginal effects at the indicated percentiles. Panel B reports the median-group results using the original outcomes. Panel C reports the same median-group specification after detrending each outcome using the pre-treatment regression of the outcome on month fixed effects and CNO4-specific linear trends. Inference clusters by CNO4.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "feminization_pretrends_v1.tex", pretrend_lines)

    for outcome, label in outcomes.items():
        path = tables_dir / f"feminization_event_{outcome}.csv"
        ylim = (-0.08, 0.12) if outcome == "ln_parados" else (-0.30, 0.30)
        for percentile in (25, 50, 75):
            frame = _event_frame(path, percentile=percentile)
            _render_single_event(
                frame, figures_dir / f"Feminization_{label}_p{percentile}.png",
                "Marginal effect", ylim,
            )
        median_event = pd.read_csv(tables_dir / f"feminization_median_event_{outcome}.csv")
        _render_two_group_event(
            median_event, figures_dir / f"Feminization_median_{label}.png", ylim,
        )
        detrended_event = pd.read_csv(
            tables_dir / f"feminization_median_event_detrended_{outcome}.csv"
        )
        _render_two_group_event(
            detrended_event, figures_dir / f"Feminization_median_detrended_{label}.png", ylim,
        )

    composition = pd.read_csv(input_dir / "est_feminization_cno4.csv", dtype={"cno4": str})
    occupation = composition.drop_duplicates("cno4").copy()
    occupation["exposure_within_cno1"] = occupation["exposure_nearest"] - occupation.groupby(
        "cno1d"
    )["exposure_nearest"].transform("mean")
    occupation["feminization_within_cno1"] = occupation["feminization_2017_2019"] - occupation.groupby(
        "cno1d"
    )["feminization_2017_2019"].transform("mean")
    x = occupation["exposure_within_cno1"].to_numpy(float)
    y = occupation["feminization_within_cno1"].to_numpy(float)
    slope, intercept = np.polyfit(x, y, 1)
    grid = np.linspace(x.min(), x.max(), 100)
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    ax.scatter(x, y, color=SKY, alpha=0.65, s=16, edgecolor="none")
    ax.plot(grid, intercept + slope * grid, color=NAVY, linewidth=1.3)
    ax.axhline(0, color=GREY, linewidth=0.7)
    ax.axvline(0, color=GREY, linewidth=0.7)
    ax.set_xlabel("AI exposure, residualized by CNO1")
    ax.set_ylabel("Female employment share, residualized by CNO1")
    fig.tight_layout()
    fig.savefig(figures_dir / "Feminization_support_exposure.png", bbox_inches="tight", dpi=320)
    plt.close(fig)

    cno2 = pd.read_csv(tables_dir / "cno2_feminization_index_v1.csv", dtype={"cno2": str})
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    ax.scatter(cno2["feminization_2017_2019"], cno2["feminization_2021q1_2022q3"],
               color=SKY, s=22, edgecolor="none")
    limits = [
        min(cno2["feminization_2017_2019"].min(), cno2["feminization_2021q1_2022q3"].min()),
        max(cno2["feminization_2017_2019"].max(), cno2["feminization_2021q1_2022q3"].max()),
    ]
    ax.plot(limits, limits, color=GREY, linestyle="--", linewidth=0.9)
    ax.set_xlim(limits)
    ax.set_ylim(limits)
    ax.set_xlabel("Female employment share, 2017--2019")
    ax.set_ylabel("Female employment share, 2021Q1--2022Q3")
    fig.tight_layout()
    fig.savefig(figures_dir / "Feminization_support_stability.png", bbox_inches="tight", dpi=320)
    plt.close(fig)

    validation = pd.read_csv(tables_dir / "feminization_validation_v1.csv")
    summary_rows = []
    for outcome in outcomes:
        for phase in ("adjustment", "later"):
            for percentile in (25, 50, 75):
                row = _row(continuous[outcome], phase=phase, percentile=percentile)
                summary_rows.append({
                    "analysis": "continuous_feminization", "outcome": outcome,
                    "phase": phase, "estimand": f"p{percentile}",
                    "estimate": row["estimate"], "se": row["se"],
                })
            for group in ("below_median", "above_or_equal_median"):
                row = _row(median_split[outcome], phase=phase, group=group)
                summary_rows.append({
                    "analysis": "median_split_feminization", "outcome": outcome,
                    "phase": phase, "estimand": group,
                    "estimate": row["estimate"], "se": row["se"],
                })
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(tables_dir / "feminization_summary_v1.csv", index=False)

    artifact_rows = []
    for path in sorted(figures_dir.glob("Feminization*.png")):
        artifact_rows.append({"type": "figure", "name": path.name, "path": str(path)})
    for path in sorted(tables_dir.glob("*feminization*.tex")):
        artifact_rows.append({"type": "table", "name": path.name, "path": str(path)})
    pd.DataFrame(artifact_rows).to_csv(tables_dir / "feminization_artifact_index_v1.csv", index=False)

    return pd.concat(
        [validation.assign(output="validation"),
         pd.DataFrame([{"output": "estimation_summary", "rows": len(summary)}])],
        ignore_index=True,
        sort=False,
    )
