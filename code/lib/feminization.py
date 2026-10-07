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

    # The three-bin appendix check treats each CNO2 family once when defining
    # the cutoffs. This prevents large CNO2 families with many CNO4 children
    # from determining the quartile thresholds mechanically.
    family_percentiles = feminization["feminization_2017_2019"].quantile([0.25, 0.75])
    family_p25 = float(family_percentiles.loc[0.25])
    family_p75 = float(family_percentiles.loc[0.75])
    pd.DataFrame(
        {
            "percentile": [25, 75],
            "female_share": [family_p25, family_p75],
            "population": ["unique CNO2 groups", "unique CNO2 groups"],
        }
    ).to_csv(tables_dir / "feminization_three_group_cutoffs_v1.csv", index=False)

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
    composition["feminization_three_group"] = np.select(
        [
            composition["feminization_2017_2019"] < family_p25,
            composition["feminization_2017_2019"] > family_p75,
        ],
        [1, 3],
        default=2,
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
                "female_share_cno2_p25": family_p25,
                "female_share_cno2_p75": family_p75,
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
    """Build the retained median-split feminization outputs."""

    root = Path(project_root)
    input_dir = Path(input_dir) if input_dir is not None else root / "data" / "prepared"
    tables_dir = Path(estimates_dir) if estimates_dir is not None else root / "intermediate"
    figures_dir = (
        Path(output_dir)
        if output_dir is not None
        else root / "uploads" / "figuresNtables"
    )
    figures_dir.mkdir(parents=True, exist_ok=True)

    outcomes = {"ln_parados": "unemployed", "ln_contratos": "contracts"}
    median_split = {
        outcome: pd.read_csv(tables_dir / f"feminization_median_phase_{outcome}.csv")
        for outcome in outcomes
    }
    median_split_no2021 = {
        outcome: pd.read_csv(tables_dir / f"feminization_median_phase_no2021_{outcome}.csv")
        for outcome in outcomes
    }
    median_pretrends_for_main = {
        outcome: pd.read_csv(tables_dir / f"feminization_median_pretrend_{outcome}.csv")
        for outcome in outcomes
    }
    median_pretrends_no2021 = {
        outcome: pd.read_csv(tables_dir / f"feminization_median_pretrend_no2021_{outcome}.csv")
        for outcome in outcomes
    }
    median_samples = {"full": median_split, "no2021": median_split_no2021}
    median_pretrend_samples = {
        "full": median_pretrends_for_main,
        "no2021": median_pretrends_no2021,
    }

    median_lines = [
        r"\begin{table}[!htbp]", r"\centering",
        r"\caption{AI exposure effects by occupational feminization}",
        r"\label{tab:v1_feminization_median_split}", r"\begin{threeparttable}",
        r"\scriptsize", r"\setlength{\tabcolsep}{3.5pt}",
        r"\begin{tabular}{@{}lcccc@{}}", r"\toprule",
        r"& \multicolumn{2}{c}{\# of registered unemployed} & \multicolumn{2}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}",
        r"& (1) & (2) & (3) & (4) \\",
        r"\midrule",
    ]
    for phase_index, (phase, phase_label) in enumerate([
        ("adjustment", "Panel A. Adjustment period"),
        ("later", "Panel B. Later post-treatment period"),
    ]):
        median_lines.append(rf"\multicolumn{{5}}{{l}}{{\textbf{{{phase_label}}}}} \\")
        for group, group_label in [
            ("below_median", r"\mathbf{1}\{F_i < \widetilde F\}"),
            ("above_or_equal_median", r"\mathbf{1}\{F_i \geq \widetilde F\}"),
        ]:
            rows = [
                _row(median_samples[sample][outcome], phase=phase, group=group)
                for outcome in outcomes
                for sample in ("full", "no2021")
            ]
            median_lines += [
                f"AI exposure $\\times {group_label}$ & "
                + " & ".join(_coef(row) for row in rows) + r" \\",
                " & " + " & ".join(_se(row) for row in rows) + r" \\",
            ]
        if phase_index == 0:
            median_lines.append(r"\addlinespace[2pt]")
    observations = [
        int(_row(median_samples[sample][outcome], phase="adjustment", group="below_median")["observations"])
        for outcome in outcomes
        for sample in ("full", "no2021")
    ]
    median_lines += [
        r"\midrule",
        r"CNO1 $\times$ year-month FE & Yes & Yes & Yes & Yes \\",
        r"2021 included & Yes & No & Yes & No \\",
        "Pre-trend joint-null $p$-value: $F_i < \\widetilde F$ & "
        + " & ".join(
            _pvalue(
                _row(
                    median_pretrend_samples[sample][outcome],
                    group="below_median",
                    test="joint_equal_zero",
                )["p_value"]
            )
            for outcome in outcomes
            for sample in ("full", "no2021")
        )
        + r" \\",
        "Pre-trend joint-null $p$-value: $F_i \\geq \\widetilde F$ & "
        + " & ".join(
            _pvalue(
                _row(
                    median_pretrend_samples[sample][outcome],
                    group="above_or_equal_median",
                    test="joint_equal_zero",
                )["p_value"]
            )
            for outcome in outcomes
            for sample in ("full", "no2021")
        )
        + r" \\",
        "Observations & " + " & ".join(f"{value:,}" for value in observations) + r" \\",
        r"\bottomrule", r"\end{tabular}", r"\begin{tablenotes}[flushleft]", r"\footnotesize",
        r"\item \emph{Notes:} Each column reports one regression. Columns 1--2 use registered unemployment and columns 3--4 use new contracts; columns 2 and 4 exclude 2021. $F_i$ is the predetermined female employment share of occupation $i$'s CNO2 group, measured from pooled EPA employment over 2017--2019, and $\widetilde F=0.303$ is its median. The rows report linear combinations of the exposure-by-period-by-group coefficients. The adjustment and later periods cover event times 0--24 and 25--40. All regressions include CNO4 and CNO1-by-year-month fixed effects. Exposure is measured in ten-percentage-point units, and standard errors in parentheses are clustered by CNO4. Pre-trend rows test the joint null that all available event-study coefficients equal zero: event times $-21$ through $-2$ in columns 1 and 3 and $-10$ through $-2$ in columns 2 and 4; October 2022 is omitted. Entries are marginal effects, not ATTs. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}",
    ]
    _write_tex(tables_dir / "feminization_median_split_v1.tex", median_lines)

    for outcome, label in outcomes.items():
        ylim = (-0.08, 0.12) if outcome == "ln_parados" else (-0.30, 0.30)
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

    return pd.concat(median_split.values(), ignore_index=True)
