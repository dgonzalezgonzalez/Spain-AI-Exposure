# Source cell 2

from pathlib import Path
import math
import shutil
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path.cwd().resolve()
while PROJECT_ROOT != PROJECT_ROOT.parent and not (PROJECT_ROOT / "data").is_dir():
    PROJECT_ROOT = PROJECT_ROOT.parent
if not (PROJECT_ROOT / "data").is_dir():
    raise FileNotFoundError("Run this notebook from the replication-package folder.")

CODE_DIR = PROJECT_ROOT
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = RAW_DIR
INPUT_DIR = PROJECT_ROOT / "data" / "prepared"
INTERMEDIATE_DIR = PROJECT_ROOT / "intermediate"
FINAL_DIR = PROJECT_ROOT / "uploads" / "figuresNtables"
LOGS_DIR = PROJECT_ROOT / "logs"

TABLES_DIR = INTERMEDIATE_DIR
PAPER_FIGURES_DIR = FINAL_DIR
FIGURES_DIR = FINAL_DIR
OUTPUT_ROOT = FINAL_DIR
UPLOAD_DIR = FINAL_DIR

if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
for directory in [INPUT_DIR, INTERMEDIATE_DIR, FINAL_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

HIGH_CUTOFF = 0.1169
EVENT_PERIOD = pd.Timestamp("2022-11-01")
EVENT_MIN, EVENT_MAX = -21, 40

NAVY = "#08519C"
SKY = "#56B4E9"
GREY = "#7F8C8D"
LIGHT_GREY = "#D9E2E8"

plt.rcParams.update({
    "figure.dpi": 140, "savefig.dpi": 320, "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.22,
    "grid.color": "#9AA4AD", "axes.axisbelow": True,
})

def stars(beta, se):
    if pd.isna(beta) or pd.isna(se) or se <= 0:
        return ""
    p = math.erfc(abs(beta / se) / math.sqrt(2))
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""

def coefficient(beta, se, digits=3):
    suffix = stars(beta, se)
    value = f"{beta:.{digits}f}"
    return value + (rf"$^{{{suffix}}}$" if suffix else "")

def standard_error(se, digits=3):
    return f"({se:.{digits}f})" if pd.notna(se) else ""

def latex_escape(value):
    text = str(value)
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%",
                    "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def read_first(filename):
    path = INTERMEDIATE_DIR / filename
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    return frame.iloc[0] if len(frame) else None

def avg_row(specification, outcome):
    return read_first(f"twfe_average_{specification}_{outcome}.csv")

def longdiff_row(specification, outcome):
    return read_first(f"twfe_longdiff_{specification}_{outcome}.csv")

def require(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Required estimator output is missing: {path}")
    return path

def save_tex(filename, lines):
    path = INTERMEDIATE_DIR / filename
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Built {path.name}")
    return path



# Source cell 4
total_panel = pd.read_csv(INPUT_DIR / "est_total_cno4.csv", dtype={"cno4": str})
total_panel["period_date"] = pd.to_datetime(total_panel["period"] + "-01")
total_panel["exposure_group"] = np.select(
    [
        total_panel["exposure_nearest"].eq(0),
        total_panel["exposure_nearest"].ge(HIGH_CUTOFF),
    ],
    ["Zero exposure", "High exposure"],
    default="Middle exposure",
)
reference = (
    total_panel.loc[
        total_panel["period_date"].eq(EVENT_PERIOD),
        ["cno4", "parados", "contratos"],
    ]
    .rename(columns={"parados": "parados_reference", "contratos": "contratos_reference"})
)
total_panel = total_panel.merge(reference, on="cno4", how="left", validate="many_to_one")
for outcome in ["parados", "contratos"]:
    denominator = total_panel[f"{outcome}_reference"]
    total_panel[f"{outcome}_index"] = np.where(
        denominator.gt(0),
        100 * total_panel[outcome] / denominator,
        np.nan,
    )

monthly = (
    total_panel.groupby(["period_date", "exposure_group"], as_index=False)
    .agg(
        parados_index=("parados_index", "mean"),
        contratos_index=("contratos_index", "mean"),
        n_parados=("parados_index", "count"),
        n_contratos=("contratos_index", "count"),
    )
)

styles = {
    "Zero exposure": (GREY, "--"),
    "Middle exposure": (SKY, "-"),
    "High exposure": (NAVY, "-"),
}
for outcome, ylabel, ylim, filename in [
    ("parados_index", "Index, November 2022 = 100", (70, 145), "Figure1_panelA.png"),
    ("contratos_index", "Index, November 2022 = 100", (40, 180), "Figure1_panelB.png"),
]:
    fig, ax = plt.subplots(figsize=(6.2, 3.7))
    for label in ["Zero exposure", "Middle exposure", "High exposure"]:
        subset = monthly.loc[monthly["exposure_group"].eq(label)]
        color, linestyle = styles[label]
        ax.plot(
            subset["period_date"],
            subset[outcome],
            label=label,
            color=color,
            linestyle=linestyle,
            linewidth=1.45,
        )
    ax.axvline(EVENT_PERIOD, color=GREY, linestyle=":", linewidth=1)
    ax.set_xlabel("Month")
    ax.set_ylabel(ylabel)
    ax.set_ylim(*ylim)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(PAPER_FIGURES_DIR / filename, bbox_inches="tight")
    plt.close(fig)

monthly.to_csv(TABLES_DIR / "descriptive_patterns_by_exposure_v1.csv", index=False)
print("Saved Figure 1 panels.")



# Source cell 6
def render_event_file(source, destination, ylim, ylabel="Estimated marginal effect", ytick_step=None):
    frame = pd.read_csv(require(source)).sort_values("event_time")
    event_grid = pd.DataFrame({"event_time": np.arange(EVENT_MIN, EVENT_MAX + 1)})
    frame = event_grid.merge(frame, on="event_time", how="left")
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
    ax.set_xlim(EVENT_MIN, EVENT_MAX)
    ax.set_ylim(*ylim)
    if ytick_step is not None:
        ax.set_yticks(np.arange(ylim[0], ylim[1] + ytick_step / 2, ytick_step))
    ax.set_xticks(np.arange(-20, 41, 10))
    ax.set_xlabel("Months relative to November 2022")
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    fig.savefig(destination, bbox_inches="tight")
    plt.close(fig)

render_event_file(
    TABLES_DIR / "twfe_event_preferred_cno1_month_ln_parados.csv",
    PAPER_FIGURES_DIR / "Figure2_panelA.png",
    (-0.05, 0.05),
    ytick_step=0.025,
)
render_event_file(
    TABLES_DIR / "twfe_event_preferred_cno1_month_ln_contratos.csv",
    PAPER_FIGURES_DIR / "Figure2_panelB.png",
    (-0.20, 0.20),
    ytick_step=0.05,
)
print("Saved preferred TWFE event-study panels.")



# Source cell 10
support_cno1 = pd.read_csv(require(TABLES_DIR / "exposure_support_within_cno1d.csv"))
support_cno2 = pd.read_csv(require(TABLES_DIR / "exposure_support_within_cno2.csv"))

for frame, label, filename in [
    (support_cno1, "Within-CNO1 standard deviation", "Support_panelA.png"),
    (support_cno2, "Within-CNO2 standard deviation", "Support_panelB.png"),
]:
    values = frame["sd_exposure"].fillna(0)
    fig, ax = plt.subplots(figsize=(5.7, 3.5))
    ax.hist(values, bins=min(15, max(5, len(values))), color=SKY, edgecolor="white")
    ax.axvline(values.median(), color=NAVY, linewidth=1.3, linestyle="--")
    ax.set_xlabel(label)
    ax.set_ylabel("Number of occupation families")
    fig.tight_layout()
    fig.savefig(PAPER_FIGURES_DIR / filename, bbox_inches="tight")
    plt.close(fig)

support_summary = pd.DataFrame([
    {
        "level": "CNO1",
        "families": len(support_cno1),
        "median_sd": support_cno1["sd_exposure"].fillna(0).median(),
        "median_range": support_cno1["range_exposure"].median(),
        "zero_range_share": (support_cno1["range_exposure"] == 0).mean(),
    },
    {
        "level": "CNO2",
        "families": len(support_cno2),
        "median_sd": support_cno2["sd_exposure"].fillna(0).median(),
        "median_range": support_cno2["range_exposure"].median(),
        "zero_range_share": (support_cno2["range_exposure"] == 0).mean(),
    },
])
support_summary.to_csv(TABLES_DIR / "family_support_summary_v1.csv", index=False)

support_tex = [
    r"\begin{table}[!htbp]",
    r"\centering",
    r"\caption{Within-family variation in AI exposure}",
    r"\label{tab:v1_family_support}",
    r"\begin{threeparttable}",
    r"\begin{tabular}{lcccc}",
    r"\toprule",
    r"Family level & Families & Median SD & Median range & Zero-range share \\",
    r"\midrule",
]
for row in support_summary.itertuples():
    support_tex.append(
        f"{row.level} & {row.families} & {row.median_sd:.3f} & "
        f"{row.median_range:.3f} & {100*row.zero_range_share:.1f}\\% \\\\"
    )
support_tex += [
    r"\bottomrule",
    r"\end{tabular}",
    r"\begin{tablenotes}[flushleft]",
    r"\footnotesize",
    r"\item \emph{Notes:} Statistics are computed across the 502 CNO4 occupations using the nearest-neighbor exposure score. A zero range means that all CNO4 occupations inside the family have the same exposure. Smaller within-family dispersion implies weaker identifying variation after family-by-month effects are absorbed.",
    r"\end{tablenotes}",
    r"\end{threeparttable}",
    r"\end{table}",
]
save_tex("family_support_v1.tex", support_tex)

robust_event_specs = [
    ("preferred_cno1_month", "ln_parados", "ln_contratos"),
    ("log_plus_one_cno1_month", "ln_parados_p1", "ln_contratos_p1"),
    ("cosine_weighted_cno1_month", "ln_parados", "ln_contratos"),
]
for panel, (spec, outcome_u, outcome_c) in enumerate(robust_event_specs, start=1):
    unemployed_ylim = (-0.10, 0.20) if panel == 4 else (-0.05, 0.05)
    unemployed_step = 0.05 if panel == 4 else 0.025
    render_event_file(TABLES_DIR / f"twfe_event_{spec}_{outcome_u}.csv", PAPER_FIGURES_DIR / f"Robustness_unemployed_panel{panel}.png", unemployed_ylim, ylabel="Estimated marginal effect", ytick_step=unemployed_step)
    render_event_file(TABLES_DIR / f"twfe_event_{spec}_{outcome_c}.csv", PAPER_FIGURES_DIR / f"Robustness_contracts_panel{panel}.png", (-0.30, 0.30), ylabel="Estimated marginal effect", ytick_step=0.10)

# Leave-one-CNO1-out sensitivity for the preferred long difference.
leaveout_rows = []
for omitted in range(10):
    for outcome in ["ln_parados", "ln_contratos"]:
        row = longdiff_row(f"leaveout_cno1_{omitted}", outcome)
        if row is None:
            raise FileNotFoundError(
                f"Missing leave-one-family output for CNO1={omitted}, {outcome}."
            )
        leaveout_rows.append({
            "omitted_cno1": omitted,
            "outcome": outcome,
            "estimate": row.estimate,
            "se": row.se,
            "ci_low": row.ci_low,
            "ci_high": row.ci_high,
            "observations": row.observations,
        })
leaveout = pd.DataFrame(leaveout_rows)
leaveout.to_csv(TABLES_DIR / "leave_one_cno1_summary_v1.csv", index=False)
for outcome, filename, ylim in [
    ("ln_parados", "LeaveOneCNO1_unemployed.png", (-0.03, 0.06)),
    ("ln_contratos", "LeaveOneCNO1_contracts.png", (-0.06, 0.06)),
]:
    frame = leaveout.loc[leaveout["outcome"].eq(outcome)].copy()
    fig, ax = plt.subplots(figsize=(5.8, 3.6))
    ax.axhline(0, color=GREY, linewidth=0.7)
    ax.vlines(
        frame["omitted_cno1"], frame["ci_low"], frame["ci_high"],
        color=SKY, linewidth=2.5,
    )
    ax.scatter(frame["omitted_cno1"], frame["estimate"], color=NAVY, s=22)
    ax.set_xticks(range(10))
    ax.set_xlabel("Omitted CNO1 family")
    ax.set_ylabel("Long-difference estimate")
    ax.set_ylim(*ylim)
    fig.tight_layout()
    fig.savefig(PAPER_FIGURES_DIR / filename, bbox_inches="tight")
    plt.close(fig)



# Retained stratified continuous-DiD event-study panels.
render_event_file(
    TABLES_DIR / 'contdid_figure_event_cno1_stratified_ln_parados.csv',
    PAPER_FIGURES_DIR / 'ContDID_panel1.png',
    (-0.05, 0.15),
)
render_event_file(
    TABLES_DIR / 'contdid_figure_event_cno1_stratified_ln_contratos.csv',
    PAPER_FIGURES_DIR / 'ContDID_panel2.png',
    (-0.30, 0.30),
    ytick_step=0.10,
)

render_event_file(
    TABLES_DIR / "twfe_binary_event_binary_high_all_preferred_ln_contratos.csv",
    PAPER_FIGURES_DIR / "Binary_event_contracts.png",
    (-0.30, 0.30), ylabel="Estimated treatment effect", ytick_step=0.10,
)

# Source cell 14
def render_sdid_path(source, destination, ylim=None, ytick_step=None):
    frame = pd.read_csv(require(source)).sort_values("event_time")
    counterfactual = frame["counterfactual"]
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    ax.plot(frame["event_time"], frame["treated"], color=NAVY, linewidth=1.4, label="High exposure")
    ax.plot(
        frame["event_time"], counterfactual,
        color=SKY, linewidth=1.4, label="Synthetic lower-exposure counterfactual",
    )
    ax.axvline(0, color=GREY, linestyle="--", linewidth=0.8)
    ax.set_xlim(EVENT_MIN, EVENT_MAX)
    if ylim is not None:
        ax.set_ylim(*ylim)
        if ytick_step is not None:
            ax.set_yticks(np.arange(ylim[0], ylim[1] + ytick_step / 2, ytick_step))
    ax.set_xlabel("Months relative to November 2022")
    ax.set_ylabel("Log outcome")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(destination, bbox_inches="tight")
    plt.close(fig)

for spec, prefix in [
    ("expanded_donor_cno1_month", "SDID_adjusted"),
]:
    render_sdid_path(
        TABLES_DIR / f"sdid_paths_{spec}_ln_parados.csv",
        PAPER_FIGURES_DIR / f"{prefix}_path_unemployed.png",
        (6.0, 8.5),
        0.5,
    )
    render_event_file(
        TABLES_DIR / f"sdid_event_{spec}_ln_parados.csv",
        PAPER_FIGURES_DIR / f"{prefix}_event_unemployed.png",
        (-0.05, 0.10),
        ylabel="Synthetic DID effect",
        ytick_step=0.025,
    )
    render_sdid_path(
        TABLES_DIR / f"sdid_paths_{spec}_ln_contratos.csv",
        PAPER_FIGURES_DIR / f"{prefix}_path_contracts.png",
        (3.5, 7.5),
        1.0,
    )
    render_event_file(
        TABLES_DIR / f"sdid_event_{spec}_ln_contratos.csv",
        PAPER_FIGURES_DIR / f"{prefix}_event_contracts.png",
        (-0.25, 0.25),
        ylabel="Synthetic DID effect",
    )

english_titles = pd.read_csv(
    PROCESSED_DIR / "cno4_english_titles.csv", dtype={"cno4": str}
)
english_titles["cno4"] = english_titles["cno4"].str.zfill(4)
occupation_level = (
    total_panel[["cno4", "exposure_nearest"]]
    .drop_duplicates("cno4")
    .merge(english_titles[["cno4", "occupation_title_english"]], on="cno4", how="left")
)
treated = occupation_level.loc[occupation_level["exposure_nearest"] > HIGH_CUTOFF].copy()
treated = treated.sort_values("exposure_nearest", ascending=False)

omega_u = pd.read_csv(
    require(TABLES_DIR / "sdid_omega_expanded_donor_cno1_month_ln_parados.csv"),
    dtype={"cno4": str},
)
omega_c = pd.read_csv(
    require(TABLES_DIR / "sdid_omega_expanded_donor_cno1_month_ln_contratos.csv"),
    dtype={"cno4": str},
)
for frame in [omega_u, omega_c]:
    frame["cno4"] = frame["cno4"].str.zfill(4)
donors = (
    omega_u[["cno4", "exposure_nearest", "occupation_title", "omega"]]
    .rename(columns={"omega": "weight_unemployed"})
    .merge(
        omega_c[["cno4", "omega"]].rename(columns={"omega": "weight_contracts"}),
        on="cno4",
        how="outer",
    )
    .fillna({"weight_unemployed": 0, "weight_contracts": 0})
)
donors = donors.loc[
    (donors["weight_unemployed"].abs() > 1e-10)
    | (donors["weight_contracts"].abs() > 1e-10)
].copy()
donors["max_weight"] = donors[["weight_unemployed", "weight_contracts"]].max(axis=1)
donors = donors.sort_values("max_weight", ascending=False)
donors.to_csv(TABLES_DIR / "sdid_positive_weight_donors_v1.csv", index=False)
treated.to_csv(TABLES_DIR / "sdid_treated_occupations_v1.csv", index=False)

weight_audit = pd.DataFrame([
    {
        "outcome": "ln_parados",
        "weight_sum": omega_u["omega"].sum(),
        "positive_weight_donors": int((omega_u["omega"] > 1e-10).sum()),
        "effective_donors": 1 / np.square(omega_u["omega"]).sum(),
        "largest_weight": omega_u["omega"].max(),
        "top_10_weight_share": omega_u.nlargest(10, "omega")["omega"].sum(),
        "treated_mean_exposure": omega_u["treated_mean_exposure"].iloc[0],
        "donor_weighted_exposure": omega_u["donor_weighted_exposure"].iloc[0],
        "exposure_contrast": omega_u["exposure_contrast"].iloc[0],
    },
    {
        "outcome": "ln_contratos",
        "weight_sum": omega_c["omega"].sum(),
        "positive_weight_donors": int((omega_c["omega"] > 1e-10).sum()),
        "effective_donors": 1 / np.square(omega_c["omega"]).sum(),
        "largest_weight": omega_c["omega"].max(),
        "top_10_weight_share": omega_c.nlargest(10, "omega")["omega"].sum(),
        "treated_mean_exposure": omega_c["treated_mean_exposure"].iloc[0],
        "donor_weighted_exposure": omega_c["donor_weighted_exposure"].iloc[0],
        "exposure_contrast": omega_c["exposure_contrast"].iloc[0],
    },
])
for outcome in ("ln_parados", "ln_contratos"):
    time_weights = pd.read_csv(TABLES_DIR / f"sdid_lambda_expanded_donor_cno1_month_{outcome}.csv")
    time_weights = time_weights.loc[time_weights["event_time"].lt(0)].dropna(subset=["lambda"])
    assert np.isclose(time_weights["lambda"].sum(), 1, atol=1e-6)
    select = weight_audit["outcome"].eq(outcome)
    weight_audit.loc[select, "largest_month_weight"] = time_weights["lambda"].max()
    weight_audit.loc[select, "last_six_month_share"] = time_weights.loc[
        time_weights["event_time"].between(-6, -1), "lambda"
    ].sum()
weight_audit.to_csv(TABLES_DIR / "sdid_weight_audit_v1.csv", index=False)
assert np.allclose(weight_audit["weight_sum"], 1, atol=1e-6)

donor_tex = [
    r"\small",
    r"\begin{longtable}{p{0.08\textwidth}>{\raggedright\arraybackslash}p{0.43\textwidth}rrr}",
    r"\caption{Treated occupations and positive-weight synthetic-DiD donors}\label{tab:v1_sdid_donors}\\",
    r"\toprule",
    r"CNO4 & Occupation & Exposure & \shortstack{Weight: \\ unemployed} & \shortstack{Weight: \\ contracts} \\",
    r"\midrule",
    r"\endfirsthead",
    r"\multicolumn{5}{c}{\tablename\ \thetable\ -- continued} \\",
    r"\toprule",
    r"CNO4 & Occupation & Exposure & \shortstack{Weight: \\ unemployed} & \shortstack{Weight: \\ contracts} \\",
    r"\midrule",
    r"\endhead",
    r"\multicolumn{5}{l}{\textit{Panel A. Treated occupations}} \\",
]
for row in treated.itertuples():
    donor_tex.append(
        f"{row.cno4} & {latex_escape(row.occupation_title_english)} & "
        f"{row.exposure_nearest:.3f} & & \\\\"
    )
donor_tex += [
    r"\midrule",
    r"\multicolumn{5}{l}{\textit{Panel B. Donors with positive weight in at least one outcome}} \\",
]
for row in donors.itertuples():
    title = row.occupation_title
    donor_tex.append(
        f"{row.cno4} & {latex_escape(title)} & {row.exposure_nearest:.3f} & "
        f"{row.weight_unemployed:.4f} & {row.weight_contracts:.4f} \\\\"
    )
donor_tex += [
    r"\midrule",
    r"\multicolumn{5}{p{0.93\textwidth}}{\footnotesize \emph{Notes:} Panel A lists occupations above the fixed 0.1169 cutoff. Panel B is ordered by the larger of the two outcome-specific weights and omits donors receiving zero weight in both estimations. Occupation descriptions are English translations of official CNO titles. Donor weights sum to one separately by outcome.} \\",
    r"\bottomrule",
    r"\end{longtable}",
    r"\normalsize",
]
save_tex("sdid_donor_weights_v1.tex", donor_tex)

weight_summary_tex = [
    r"\begin{table}[!htbp]",
    r"\centering",
    r"\caption{Synthetic-DiD donor-weight diagnostics}",
    r"\label{tab:v1_sdid_weight_diagnostics}",
    r"\begin{threeparttable}",
    r"\small",
    r"\begin{tabular}{lcc}",
    r"\toprule",
    r"& \# of registered unemployed & \# of new contracts \\",
    r"\midrule",
]
weight_labels = {
    "positive_weight_donors": "Positive-weight donors",
    "effective_donors": "Effective number of donors",
    "largest_weight": "Largest donor weight",
    "largest_month_weight": "Largest month weight",
    "last_six_month_share": "Share of weights in the 6 months prior to treatment",
    "top_10_weight_share": "Share held by top 10 donors",
    "treated_mean_exposure": "Mean treated exposure",
    "donor_weighted_exposure": "Donor-weighted exposure",
    "exposure_contrast": "Exposure contrast",
}
u_audit = weight_audit.loc[weight_audit["outcome"].eq("ln_parados")].iloc[0]
c_audit = weight_audit.loc[weight_audit["outcome"].eq("ln_contratos")].iloc[0]
for variable, label in weight_labels.items():
    if variable == "positive_weight_donors":
        values = [f"{int(u_audit[variable]):,}", f"{int(c_audit[variable]):,}"]
    elif variable == "effective_donors":
        values = [f"{u_audit[variable]:.1f}", f"{c_audit[variable]:.1f}"]
    else:
        values = [f"{u_audit[variable]:.3f}", f"{c_audit[variable]:.3f}"]
    weight_summary_tex.append(f"{label} & {values[0]} & {values[1]} \\\\")
weight_summary_tex += [
    r"\bottomrule",
    r"\end{tabular}",
    r"\begin{tablenotes}[flushleft]",
    r"\footnotesize",
    r"\item \emph{Notes:} The effective number of donors is \(1/\sum_j\widehat{\omega}_j^2\). The exposure contrast is the treated mean minus the donor-weighted mean. Calculations use the CNO1-by-month-adjusted expanded-donor synthetic-DiD specification.",
    r"\end{tablenotes}",
    r"\end{threeparttable}",
    r"\end{table}",
]
save_tex("sdid_weight_diagnostics_v1.tex", weight_summary_tex)

lambda_rows = []
for specification, prefix in [
    ("expanded_donor_cno1_month", "adjusted"),
]:
    for outcome, outcome_label in [
        ("ln_parados", "unemployed"),
        ("ln_contratos", "contracts"),
    ]:
        frame = pd.read_csv(
            require(TABLES_DIR / f"sdid_lambda_{specification}_{outcome}.csv")
        ).sort_values("event_time")
        lambda_rows.append(
            frame.assign(specification_label=prefix, outcome_label=outcome_label)
        )
lambda_frame = pd.concat(lambda_rows, ignore_index=True)
lambda_frame.to_csv(TABLES_DIR / "sdid_time_weights_v1.csv", index=False)
print(weight_audit)



# Source cell 16
heterogeneity_groups = [
    ("Age: under 30", "age", "lt18_to_29"),
    ("Age: 30--39", "age", "30-39"),
    ("Age: 40 or older", "age", "40_to_gt44"),
    ("Gender: men", "gender", "hombre"),
    ("Gender: women", "gender", "mujer"),
]

def heterogeneity_spec(dimension, tag, specification):
    suffix = {
        "benchmark": "benchmark",
        "preferred": "cno1_month",
        "preferred_cno3": "cno1_month_cluster_cno3",
    }[specification]
    return f"{dimension}_{tag}_{suffix}"

# Preferred subgroup event studies. All panels for a given outcome share a
# common vertical range to preserve visual comparability.
for stale_path in PAPER_FIGURES_DIR.glob("Heterogeneity_*_contdid_panel*.png"):
    stale_path.unlink(missing_ok=True)
for stale_path in PAPER_FIGURES_DIR.glob("Heterogeneity_*_sdid_panel*.png"):
    stale_path.unlink(missing_ok=True)
for index, (_, dimension, tag) in enumerate(heterogeneity_groups, start=1):
    specification = heterogeneity_spec(dimension, tag, "preferred")
    render_event_file(
        TABLES_DIR / f"twfe_event_{specification}_ln_parados.csv",
        PAPER_FIGURES_DIR / f"Heterogeneity_unemployed_panel{index}.png",
        (-0.05, 0.075), ylabel="Estimate", ytick_step=0.025,
    )
    render_event_file(
        TABLES_DIR / f"twfe_event_{specification}_ln_contratos.csv",
        PAPER_FIGURES_DIR / f"Heterogeneity_contracts_panel{index}.png",
        (-0.30, 0.30), ylabel="Estimate", ytick_step=0.10,
    )



# Source cell 18
from lib.report_outputs import build_phase_outputs

phase_summary = build_phase_outputs(PROJECT_ROOT, estimates_dir=INTERMEDIATE_DIR, output_dir=FINAL_DIR)
print(phase_summary)

# Organize the feminization estimates produced by Stata into the
# paper-facing tables and appendix figures.
from lib.feminization import build_feminization_outputs
feminization_summary = build_feminization_outputs(PROJECT_ROOT, input_dir=INPUT_DIR, estimates_dir=INTERMEDIATE_DIR, output_dir=FINAL_DIR)
print(feminization_summary)

# Format the additions requested in the referee-response pass.
from lib.refinement_outputs import build_refinement_outputs
refinement_summary = build_refinement_outputs(
    PROJECT_ROOT, estimates_dir=INTERMEDIATE_DIR, output_dir=FINAL_DIR
)
print(refinement_summary)



# Source cell 20
validation = []

def record(check, passed, detail):
    validation.append({"check": check, "passed": bool(passed), "detail": str(detail)})

age_audit = pd.read_csv(INTERMEDIATE_DIR / "sepe_may2024_age_backcast_cell_audit_v1.csv")
province_audit = pd.read_csv(INTERMEDIATE_DIR / "sepe_may2024_province_backcast_cell_audit_v1.csv")
cutoff_audit = pd.read_csv(INTERMEDIATE_DIR / "treatment_cutoff_audit_v1.csv")

record("Age reconstruction audit is complete", len(age_audit) == 502 * 6 * 2, len(age_audit))
record("Province reconstruction audit is complete", len(province_audit) == 502 * 52 * 2, len(province_audit))
record("Total panel has 502 CNO4 units", total_panel["cno4"].nunique() == 502, total_panel["cno4"].nunique())
record("Total panel has 63 months", total_panel["period"].nunique() == 63, total_panel["period"].nunique())

feminization_panel = pd.read_csv(INPUT_DIR / "est_feminization_cno4.csv", dtype={"cno4": str})
record("Feminization panel has one row per CNO4-month", len(feminization_panel) == 502 * 63, len(feminization_panel))
record("EPA feminization index maps all CNO4 occupations", feminization_panel["feminization_2017_2019"].notna().all(), feminization_panel["cno4"].nunique())
record("Median split partitions the feminization panel", set(feminization_panel["feminization_above_median"].dropna().unique()) == {0, 1}, feminization_panel["feminization_above_median"].value_counts().to_dict())
record("Three-bin feminization partitions the panel", set(feminization_panel["feminization_three_group"].dropna().unique()) == {1, 2, 3}, feminization_panel["feminization_three_group"].value_counts().to_dict())

alternative_exposure_audit = pd.read_csv(INTERMEDIATE_DIR / "alternative_exposure_comparison_v1.csv")
record("BLS categories map at least 99 percent of CNO4", int(alternative_exposure_audit.loc[0, "bls_matched_cno4"]) >= 497, int(alternative_exposure_audit.loc[0, "bls_matched_cno4"]))
record("Capability score maps at least 85 percent of CNO4", int(alternative_exposure_audit.loc[0, "frs_lm_matched_cno4"]) >= 427, int(alternative_exposure_audit.loc[0, "frs_lm_matched_cno4"]))
record("Expanded SDID donor pool partitions all occupations", cutoff_audit.loc[0, "treated_above_0_1169"] + cutoff_audit.loc[0, "donors_at_or_below_0_1169"] == 502, cutoff_audit.iloc[0].to_dict())

for estimator, source in [
    ("Preferred TWFE unemployed", INTERMEDIATE_DIR / "twfe_event_preferred_cno1_month_ln_parados.csv"),
    ("Preferred TWFE contracts", INTERMEDIATE_DIR / "twfe_event_preferred_cno1_month_ln_contratos.csv"),
    ("Stratified ContDID unemployed", INTERMEDIATE_DIR / "contdid_event_cno1_stratified_ln_parados.csv"),
    ("Adjusted SDID unemployed", INTERMEDIATE_DIR / "sdid_event_expanded_donor_cno1_month_ln_parados.csv"),
    ("Adjusted SDID contracts", INTERMEDIATE_DIR / "sdid_event_expanded_donor_cno1_month_ln_contratos.csv"),
]:
    frame = pd.read_csv(require(source))
    record(f"{estimator} event window", frame["event_time"].min() == EVENT_MIN and frame["event_time"].max() == EVENT_MAX, (frame["event_time"].min(), frame["event_time"].max()))

if "weight_audit" in globals():
    record("SDID donor weights sum to one", np.allclose(weight_audit["weight_sum"], 1, atol=1e-6), weight_audit[["outcome", "weight_sum"]].to_dict("records"))

for outcome in ["ln_parados", "ln_contratos"]:
    pooled_age = pd.read_csv(require(INTERMEDIATE_DIR / f"age_pooled_phase_{outcome}.csv"))
    record(f"Pooled age tests cover all groups: {outcome}", set(pooled_age["age_group"]) == {"Under 30", "30--39", "40 or older"}, sorted(pooled_age["age_group"].unique()))
    pooled_under40 = pd.read_csv(require(INTERMEDIATE_DIR / f"age_under40_pooled_phase_{outcome}.csv"))
    record(f"Under-40 pooled test covers both phases: {outcome}", set(pooled_under40["phase"]) == {"adjustment", "later"}, sorted(pooled_under40["phase"].unique()))

validation_frame = pd.DataFrame(validation)
validation_frame.to_csv(INTERMEDIATE_DIR / "production_validation_v1.csv", index=False)
print(validation_frame)
if not validation_frame["passed"].all():
    raise AssertionError("One or more production checks failed.")
