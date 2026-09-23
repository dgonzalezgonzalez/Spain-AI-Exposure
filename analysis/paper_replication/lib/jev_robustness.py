"""Paper outputs for Jev exposure robustness and cross-measure correlations."""

from __future__ import annotations

import math
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


NAVY = "#08519C"
SKY = "#56B4E9"
GREY = "#7F8C8D"
EVENT_MIN, EVENT_MAX = -21, 40

MEASURES = {
    "exposure_nearest": "Anthropic nearest",
    "exposure_weighted": "Anthropic cosine-weighted",
    "observed_exposure_jev_nearest": "Jev nearest category",
    "observed_exposure_jev_weighted": "Jev probability-weighted",
    "observed_exposure_jev_direct": "Jev direct score",
    "bls_ai_category_code": "BLS ordinal category",
    "frs_lm_percentile": "LM-AIOE percentile",
}

BLS_CATEGORY_ORDER = {"low": 1, "moderate": 2, "high": 3, "very high": 4}


def _normalize_cno4(values: pd.Series) -> pd.Series:
    return values.astype("string").str.extract(r"(\d+)", expand=False).str.zfill(4)


def _soc6(values: pd.Series) -> pd.Series:
    return values.astype("string").str.replace(r"\D", "", regex=True).str.zfill(6)


def prepare_jev_panel(
    prepared_panel: str | Path,
    jev_estimates: str | Path,
    output_path: str | Path,
) -> dict[str, int]:
    """Join frozen Jev estimates to every CNO4-month and add 10 pp scalings."""

    prepared = pd.read_csv(prepared_panel, dtype={"cno4": "string"})
    estimates = pd.read_csv(jev_estimates, dtype={"cno4": "string"})
    exposure_columns = [
        "observed_exposure_jev_nearest",
        "observed_exposure_jev_weighted",
        "observed_exposure_jev_direct",
    ]
    missing = [column for column in ["cno4", *exposure_columns] if column not in estimates]
    if missing:
        raise ValueError(f"Jev estimate file is missing columns: {missing}")

    prepared["cno4"] = _normalize_cno4(prepared["cno4"])
    estimates["cno4"] = _normalize_cno4(estimates["cno4"])
    estimates = estimates[["cno4", *exposure_columns]].copy()
    if estimates["cno4"].duplicated().any():
        raise ValueError("Jev estimates must contain exactly one row per CNO4 code.")
    for column in exposure_columns:
        estimates[column] = pd.to_numeric(estimates[column], errors="coerce")
        if estimates[column].isna().any() or not estimates[column].between(0, 1).all():
            raise ValueError(f"{column} must be complete and between zero and one.")

    merged = prepared.merge(estimates, on="cno4", how="left", validate="many_to_one")
    if merged[exposure_columns].isna().any().any():
        missing_codes = sorted(merged.loc[merged[exposure_columns[0]].isna(), "cno4"].unique())
        raise ValueError(f"No Jev score for {len(missing_codes)} panel occupations: {missing_codes[:8]}")
    for column in exposure_columns:
        merged[f"exposure_jev_{column.removeprefix('observed_exposure_jev_')}_10pp"] = (
            merged[column] / 0.10
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output, index=False)
    return {
        "panel_rows": len(merged),
        "occupations": int(merged["cno4"].nunique()),
        "months": int(merged["period"].nunique()) if "period" in merged else 0,
    }


def _star(beta: float, se: float) -> str:
    if not np.isfinite(beta) or not np.isfinite(se) or se <= 0:
        return ""
    p_value = math.erfc(abs(beta / se) / math.sqrt(2))
    return "***" if p_value < 0.01 else "**" if p_value < 0.05 else "*" if p_value < 0.10 else ""


def _render_event_file(source: Path, destination: Path, ylim: tuple[float, float], ytick_step: float) -> None:
    frame = pd.read_csv(source).sort_values("event_time")
    grid = pd.DataFrame({"event_time": np.arange(EVENT_MIN, EVENT_MAX + 1)})
    frame = grid.merge(frame, on="event_time", how="left")
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
    ax.set_yticks(np.arange(ylim[0], ylim[1] + ytick_step / 2, ytick_step))
    ax.set_xticks(np.arange(-20, 41, 10))
    ax.set_xlabel("Months relative to November 2022")
    ax.set_ylabel("Estimated marginal effect")
    fig.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, bbox_inches="tight")
    plt.close(fig)


def build_jev_robustness_outputs(
    estimates_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Build a baseline-plus-three-Jev long-difference table and six event plots."""

    estimates = Path(estimates_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    panels = [
        ("Panel A. Baseline specification", "", "Nearest-neighbor AI exposure"),
        ("Panel B. Jev: highest-probability U.S. occupation", "nearest", "Jev highest-probability category"),
        ("Panel C. Jev: probability-weighted U.S. occupations", "weighted", "Jev probability-weighted exposure"),
        ("Panel D. Jev: directly imputed observed exposure", "direct", "Jev direct observed-exposure score"),
    ]
    specifications = [
        ("benchmark_twfe", "preferred_cno1_month", "preferred_cno1_month_cluster_cno3")
        if not measure
        else (
            f"benchmark_jev_{measure}",
            f"jev_{measure}_cno1_month",
            f"jev_{measure}_cno1_month_cluster_cno3",
        )
        for _, measure, _ in panels
    ]

    rows: list[dict[str, object]] = []
    latex = [
        r"\begin{landscape}",
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Robustness to Jev-imputed AI exposure measures}",
        r"\label{tab:v1_jev_robustness}",
        r"\begin{threeparttable}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3.5pt}",
        r"\begin{tabular}{lcccccc}",
        r"\toprule",
        r"& \multicolumn{3}{c}{\# of registered unemployed} & \multicolumn{3}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
        r"& (1) & (2) & (3) & (4) & (5) & (6) \\",
        r"\midrule",
    ]
    for (label, measure, score_label), specs in zip(panels, specifications):
        panel_rows = []
        for outcome in ("ln_parados", "ln_contratos"):
            for specification in specs:
                path = estimates / f"twfe_longdiff_{specification}_{outcome}.csv"
                if not path.exists():
                    raise FileNotFoundError(f"Missing long-difference result: {path}")
                record = pd.read_csv(path).iloc[0].to_dict()
                record["panel"] = label
                record["measure"] = score_label
                rows.append(record)
                panel_rows.append(record)
        latex.append(rf"\multicolumn{{7}}{{l}}{{\textit{{{label}}}}} \\")
        betas = [float(row["estimate"]) for row in panel_rows]
        ses = [float(row["se"]) for row in panel_rows]
        latex.append(
            "AI exposure & "
            + " & ".join(f"{beta:.3f}{_star(beta, se)}" for beta, se in zip(betas, ses))
            + r" \\"
        )
        latex.append(" & " + " & ".join(f"({se:.3f})" for se in ses) + r" \\")
        latex.append(
            "Impact of a 10 pp increase (percent) & "
            + " & ".join(f"{100 * beta:.1f}" for beta in betas)
            + r" \\"
        )
        latex.append(
            "Observations & "
            + " & ".join(f"{int(row['observations']):,}" for row in panel_rows)
            + r" \\"
        )
        latex.append(r"\addlinespace")
    latex.extend(
        [
            r"\midrule",
            r"CNO1 fixed effects & No & Yes & Yes & No & Yes & Yes \\",
            r"Clustered standard errors & CNO4 & CNO4 & CNO3 & CNO4 & CNO4 & CNO3 \\",
            r"\bottomrule",
            r"\end{tabular}",
            r"\begin{tablenotes}[flushleft]",
            r"\footnotesize",
            r"\item \emph{Notes:} Entries are occupation-level long-difference estimates between November 2022 and November 2025. Panel A uses the Anthropic nearest-neighbor exposure. Panels B--D use, respectively, the Jev-assigned U.S. occupation with the highest probability, the probability-weighted average across U.S. occupations, and Jev's direct score for observed exposure. Columns 1 and 4 are unconditional first-difference regressions; columns 2, 3, 5, and 6 absorb CNO1 fixed effects. Standard errors are clustered as indicated. Each exposure measure is divided by 0.10, so coefficients correspond to a 10 percentage-point increase. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
            r"\end{tablenotes}",
            r"\end{threeparttable}",
            r"\end{table}",
            r"\end{landscape}",
        ]
    )

    table_path = output / "robustness_checks_jev_v1.tex"
    table_path.write_text("\n".join(latex) + "\n", encoding="utf-8")
    results_path = output / "robustness_checks_jev_v1.csv"
    pd.DataFrame(rows).to_csv(results_path, index=False)

    figure_paths: dict[str, Path] = {}
    for measure, spec_measure in [
        ("nearest", "nearest"),
        ("weighted", "weighted"),
        ("direct", "direct"),
    ]:
        for outcome, outcome_file, limits, step in [
            ("unemployed", "ln_parados", (-0.05, 0.05), 0.025),
            ("contracts", "ln_contratos", (-0.30, 0.30), 0.10),
        ]:
            source = estimates / f"twfe_event_jev_{spec_measure}_cno1_month_{outcome_file}.csv"
            if not source.exists():
                raise FileNotFoundError(f"Missing event-study result: {source}")
            destination = output / f"Robustness_{outcome}_jev_{measure}.png"
            _render_event_file(source, destination, limits, step)
            figure_paths[f"{outcome}_{measure}"] = destination
    return {"table": table_path, "table_csv": results_path, **figure_paths}


def _find_workbook(root: Path, filename: str, explicit: str | Path | None) -> Path | None:
    if explicit:
        candidate = Path(explicit)
        return candidate if candidate.is_file() else None
    candidates = [
        root / "data" / "raw" / filename,
        root / "analysis" / "paper_replication" / "runtime" / "data" / "raw" / filename,
        root / "analysis" / "paper_replication" / "data_sources" / filename,
        root / "data_sources" / filename,
    ]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def build_exposure_correlation_matrix(
    project_root: str | Path,
    prepared_panel: str | Path,
    jev_estimates: str | Path,
    output_dir: str | Path,
    *,
    bls_workbook: str | Path | None = None,
    frs_workbook: str | Path | None = None,
) -> dict[str, object]:
    """Create the lower-triangle Spearman matrix, leaving BLS cells blank if absent."""

    root, output = Path(project_root), Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(prepared_panel, dtype={"cno4": "string"})
    panel["cno4"] = _normalize_cno4(panel["cno4"])
    panel = panel.drop_duplicates("cno4")[["cno4", "exposure_nearest", "exposure_weighted"]]
    jev = pd.read_csv(jev_estimates, dtype={"cno4": "string"})
    jev["cno4"] = _normalize_cno4(jev["cno4"])
    jev_vars = [
        "observed_exposure_jev_nearest",
        "observed_exposure_jev_weighted",
        "observed_exposure_jev_direct",
    ]
    merged = panel.merge(jev[["cno4", *jev_vars]], on="cno4", validate="one_to_one")

    bls_path = _find_workbook(root, "bls_ai_exposure_categories_2025_35.xlsx", bls_workbook)
    frs_path = _find_workbook(
        root, "felten_raj_seamans_language_modeling_aioe.xlsx", frs_workbook
    )
    crosswalk_candidates = [
        root / "data" / "processed" / "spanish_occupation_matches_cosine_nearest.csv",
        root / "data" / "raw" / "spanish_occupation_matches_cosine_nearest.csv",
        root / "analysis" / "paper_replication" / "runtime" / "data" / "raw" / "spanish_occupation_matches_cosine_nearest.csv",
    ]
    crosswalk_path = next((path for path in crosswalk_candidates if path.is_file()), crosswalk_candidates[0])
    crosswalk = pd.read_csv(
        crosswalk_path,
        dtype={"CNO4": "string", "cno4": "string", "anthropic_occ_code": "string"},
    )
    if "cno4" not in crosswalk:
        crosswalk["cno4"] = crosswalk["CNO4"]
    crosswalk["cno4"] = _normalize_cno4(crosswalk["cno4"])
    crosswalk["soc6"] = _soc6(crosswalk["anthropic_occ_code"])
    crosswalk = crosswalk[["cno4", "soc6"]].drop_duplicates("cno4")
    merged = merged.merge(crosswalk, on="cno4", how="left", validate="one_to_one")

    merged["bls_ai_category_code"] = np.nan
    if bls_path:
        bls = pd.read_excel(bls_path, sheet_name="AI Exposure Categories", skiprows=1, dtype=str)
        bls["soc6"] = _soc6(bls["2025 National Employment Matrix code"])
        bls["bls_ai_category_code"] = (
            bls["Relative AI exposure"].astype("string").str.strip().str.casefold().map(BLS_CATEGORY_ORDER)
        )
        bls = bls[["soc6", "bls_ai_category_code"]].drop_duplicates("soc6")
        merged = merged.drop(columns="bls_ai_category_code").merge(
            bls, on="soc6", how="left", validate="many_to_one"
        )

    merged["frs_lm_percentile"] = np.nan
    if frs_path:
        frs = pd.read_excel(frs_path, sheet_name="LM AIOE", dtype={"SOC Code": str})
        frs["soc6"] = _soc6(frs["SOC Code"])
        frs["frs_lm_aioe"] = pd.to_numeric(frs["Language Modeling AIOE"], errors="coerce")
        frs = frs[["soc6", "frs_lm_aioe"]].drop_duplicates("soc6")
        merged = merged.merge(frs, on="soc6", how="left", validate="many_to_one")
        merged["frs_lm_percentile"] = merged["frs_lm_aioe"].rank(method="average", pct=True)

    measure_names = list(MEASURES)
    merged[measure_names].to_csv(output / "exposure_measure_matrix_inputs_v1.csv", index=False)
    correlations = pd.DataFrame(np.nan, index=measure_names, columns=measure_names, dtype=float)
    pairwise_n = pd.DataFrame(0, index=measure_names, columns=measure_names, dtype=int)
    long_rows: list[dict[str, object]] = []
    for i, measure_a in enumerate(measure_names):
        for j, measure_b in enumerate(measure_names):
            if j > i:
                continue
            if measure_a == measure_b:
                values_a = pd.to_numeric(merged[measure_a], errors="coerce").dropna()
                count = len(values_a)
                rho = 1.0 if count >= 2 and values_a.nunique() > 1 else np.nan
            else:
                complete = merged[[measure_a, measure_b]].apply(
                    pd.to_numeric, errors="coerce"
                ).dropna()
                count = len(complete)
                if count >= 2:
                    rank_a = complete[measure_a].rank(method="average")
                    rank_b = complete[measure_b].rank(method="average")
                    rho = float(rank_a.corr(rank_b, method="pearson"))
                else:
                    rho = np.nan
            correlations.loc[measure_a, measure_b] = correlations.loc[measure_b, measure_a] = rho
            pairwise_n.loc[measure_a, measure_b] = pairwise_n.loc[measure_b, measure_a] = count
            long_rows.append({"measure_a": measure_a, "measure_b": measure_b, "spearman_rho": rho, "occupations": count})
    correlations.to_csv(output / "exposure_measure_spearman_correlations_v1.csv", index_label="measure")
    pairwise_n.to_csv(output / "exposure_measure_pairwise_n_v1.csv", index_label="measure")
    pd.DataFrame(long_rows).to_csv(output / "exposure_measure_spearman_correlations_long_v1.csv", index=False)

    labels = [
        "Anthropic\nnearest",
        "Anthropic\ncosine-weighted",
        "Jev\nhighest-probability",
        "Jev\nprobability-weighted",
        "Jev\ndirect",
        "BLS category\n(data pending)",
        "LM-AIOE\npercentile",
    ]
    values = correlations.to_numpy(dtype=float)
    mask = np.triu(np.ones_like(values, dtype=bool), k=0)
    shown = np.ma.array(values, mask=mask | ~np.isfinite(values))
    cmap = plt.get_cmap("Blues").with_extremes(bad="#F0F1F2")
    fig, ax = plt.subplots(figsize=(8.6, 7.8))
    image = ax.imshow(shown, cmap=cmap, vmin=0.5, vmax=1.0, interpolation="none")
    ax.set_xticks(np.arange(len(labels)), labels=labels, rotation=30, ha="right", rotation_mode="anchor")
    ax.set_yticks(np.arange(len(labels)), labels=labels)
    ax.tick_params(axis="both", length=0, labelsize=9)
    ax.set_xticks(np.arange(-0.5, len(labels), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(labels), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.4)
    ax.tick_params(which="minor", bottom=False, left=False)
    for i in range(len(labels)):
        for j in range(i):
            rho = values[i, j]
            n = int(pairwise_n.iat[i, j])
            if np.isfinite(rho):
                red, green, blue, _ = cmap((rho - 0.5) / 0.5)
                luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
                color = "#FFFFFF" if luminance < 0.48 else "#17324D"
                ax.text(j, i, f"{rho:.2f}\n(n={n})", ha="center", va="center", color=color, fontsize=8)
            elif (measure_names[i] == "bls_ai_category_code" or measure_names[j] == "bls_ai_category_code") and not bls_path:
                ax.text(j, i, "—", ha="center", va="center", color="#56616A", fontsize=9)
    fig.subplots_adjust(top=0.98, bottom=0.20, left=0.24, right=0.87)
    colorbar = fig.colorbar(image, ax=ax, fraction=0.045, pad=0.04)
    colorbar.set_label("Spearman $\\rho$", rotation=90)
    figure_path = output / "Exposure_correlation_matrix.png"
    fig.savefig(figure_path, dpi=320, bbox_inches="tight")
    plt.close(fig)

    status = {
        "bls_source": str(bls_path) if bls_path else None,
        "frs_source": str(frs_path) if frs_path else None,
        "bls_occupations": int(merged["bls_ai_category_code"].notna().sum()),
        "frs_lm_aioe_occupations": int(merged["frs_lm_percentile"].notna().sum()),
        "matrix_measures": len(measure_names),
    }
    pd.Series(status).to_json(output / "exposure_measure_matrix_source_status_v1.json", indent=2)
    return {**status, "figure": figure_path, "correlations": output / "exposure_measure_spearman_correlations_v1.csv"}
