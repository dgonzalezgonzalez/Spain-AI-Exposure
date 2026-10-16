"""Publication outputs for tier 1 versus pooled tiers 2 and 3."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from .jev_robustness import _star, _render_event_file, _event_y_limits


def build_tier_event_tex(frame: pd.DataFrame, ylim: tuple[float, float], step: float) -> str:
    """Render the same event estimates as native LaTeX vectors for Prism."""
    rows = ["event_time estimate ci_low ci_high"]
    for row in frame.itertuples(index=False):
        rows.append(f"{int(row.event_time)} {row.estimate:.8f} {row.ci_low:.8f} {row.ci_high:.8f}")
    return (r"\begingroup" + "\n" +
            r"\definecolor{tiernavy}{HTML}{08519C}" + "\n" +
            r"\definecolor{tiersky}{HTML}{56B4E9}" + "\n" +
            r"\pgfplotstableread{" + "\n" + "\n".join(rows) + "\n" + r"}\tierdata" + "\n" +
            r"\begin{tikzpicture}" + "\n" +
            r"\begin{axis}[width=0.82\textwidth,height=0.52\textwidth," + "\n" +
            r"font=\footnotesize,xlabel={Months relative to November 2022}," + "\n" +
            r"ylabel={Estimated log-point difference},xmin=-21.7,xmax=40.7," + "\n" +
            f"ymin={ylim[0]:g},ymax={ylim[1]:g},ytick distance={step:g}," + "\n" +
            r"xtick={-20,-10,0,10,20,30,40},scaled y ticks=false," + "\n" +
            r"yticklabel style={/pgf/number format/fixed,/pgf/number format/precision=2}," + "\n" +
            r"tick align=outside,axis line style={gray},tick style={gray}]" + "\n" +
            r"\addplot[draw=none,name path=tierupper] table[x=event_time,y=ci_high]{\tierdata};" + "\n" +
            r"\addplot[draw=none,name path=tierlower] table[x=event_time,y=ci_low]{\tierdata};" + "\n" +
            r"\addplot[draw=none,fill=tiersky,fill opacity=0.28] fill between[of=tierupper and tierlower];" + "\n" +
            rf"\addplot[gray,dashed] coordinates {{(0,{ylim[0]:g}) (0,{ylim[1]:g})}};" + "\n" +
            r"\addplot[gray,thin] coordinates {(-21.7,0) (40.7,0)};" + "\n" +
            r"\addplot[tiernavy,thick,mark=*,mark size=0.8pt] table[x=event_time,y=estimate]{\tierdata};" + "\n" +
            r"\end{axis}" + "\n" + r"\end{tikzpicture}" + "\n" + r"\endgroup" + "\n")


def build_job_tier_outputs(estimates_dir: str | Path, output_dir: str | Path,
                          *, model_family: str = "jev") -> dict[str, Path]:
    if model_family not in {"jev", "tev"}:
        raise ValueError("Unknown occupation model")
    estimates, output = Path(estimates_dir), Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    specs = [f"{model_family}_tiers_{suffix}" for suffix in ("benchmark", "cno1_month", "cno1_month_no2021")]
    columns, records = [], []
    for outcome in ("ln_parados", "ln_contratos"):
        for spec in specs:
            phase = pd.read_csv(estimates / f"twfe_tier_phase_{spec}_{outcome}.csv")
            if len(phase) != 2 or set(zip(phase.tier, phase.phase)) != {
                (1, name) for name in ("adjustment", "later")
            }:
                raise ValueError("Pooled-control tier regression must contain exactly two unique coefficients")
            if "control_group" not in phase or set(phase.control_group) != {"tiers_2_3"}:
                raise ValueError("Tier DiD must use pooled tiers 2 and 3 controls")
            for name in ("observations", "clusters", "equality_p"):
                if phase[name].nunique(dropna=False) != 1:
                    raise ValueError(f"Tier regression has inconsistent {name}")
            if not np.isfinite(phase[["estimate", "se", "equality_p"]].to_numpy()).all():
                raise ValueError("Tier DiD contains missing or nonfinite estimates")
            pretrend = pd.read_csv(estimates / f"twfe_tier_pretrend_{spec}_{outcome}.csv")
            if len(pretrend) != 1 or not np.isfinite(float(pretrend.iloc[0].p_value)):
                raise ValueError("Expected one joint pre-treatment test for tier 1")
            if "control_group" not in pretrend or set(pretrend.control_group) != {"tiers_2_3"}:
                raise ValueError("Pre-treatment test must use pooled tiers 2 and 3 controls")
            for name in ("observations", "clusters"):
                if int(pretrend.iloc[0][name]) != int(phase.iloc[0][name]):
                    raise ValueError(f"Phase and event regressions have inconsistent {name}")
            columns.append((phase.set_index(["tier", "phase"]), pretrend.iloc[0]))
            for record in phase.to_dict("records"):
                records.append({**record, "pretrend_joint_null_p": float(pretrend.iloc[0].p_value)})

    # Keep the manuscript's six specifications and existing label.
    latex = [r"\begin{table}[!htbp]", r"\centering",
             r"\caption{Difference-in-differences: tier 1 versus tiers 2 and 3}",
             rf"\label{{tab:v1_{model_family}_job_tiers}}", r"\begin{threeparttable}",
             r"\scriptsize", r"\setlength{\tabcolsep}{3.5pt}", r"\begin{tabular}{lcccccc}",
             r"\toprule", r"& \multicolumn{3}{c}{\# of registered unemployed} & \multicolumn{3}{c}{\# of new contracts} \\",
             r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}", r"& (1) & (2) & (3) & (4) & (5) & (6) \\", r"\midrule"]
    for tier in (1,):
        for phase in ("adjustment", "later"):
            rows = [frame.loc[(tier, phase)] for frame, _ in columns]
            latex += [rf"Tier {tier} $\times$ {phase} period & " + " & ".join(
                f"{row.estimate:.3f}{_star(float(row.estimate), float(row.se), int(row.clusters))}" for row in rows) + r" \\",
                " & " + " & ".join(f"({row.se:.3f})" for row in rows) + r" \\"]
    def format_p(value: float) -> str:
        return r"$<0.001$" if value < 0.001 else f"{value:.3f}"
    latex += [r"\midrule", r"CNO1 $\times$ year-month FE & No & Yes & Yes & No & Yes & Yes \\",
              r"2021 included & Yes & Yes & No & Yes & Yes & No \\",
              r"Pre-trend joint-null $p$-value & " + " & ".join(format_p(float(pre.p_value)) for _, pre in columns) + r" \\",
              r"$p$-value: equal phase effects & " + " & ".join(format_p(float(frame.iloc[0].equality_p)) for frame, _ in columns) + r" \\",
              "Observations & " + " & ".join(f"{int(frame.iloc[0].observations):,}" for frame, _ in columns) + r" \\",
              r"\bottomrule", r"\end{tabular}", r"\begin{tablenotes}[flushleft]", r"\footnotesize",
              r"\item \emph{Notes:} Each column reports one regression with a tier 1 indicator interacted with both post-treatment phases; tiers 2 and 3 form the pooled control group. The indicator uses the frozen " +
              ("Jev" if model_family == "jev" else "TEV") +
              r" occupation classification. The adjustment and later periods cover event times 0--24 and 25--40; all pre-treatment months form the omitted period. Columns 1 and 4 include CNO4 and year-month fixed effects; the remaining columns include CNO4 and CNO1-by-year-month fixed effects. Columns 3 and 6 exclude 2021. Standard errors are clustered by CNO4. The pre-treatment row jointly tests all available pre-treatment event-study coefficients for tier 1: event times $-21$ through $-2$ when 2021 is included and $-10$ through $-2$ otherwise; October 2022 is omitted. The phase-equality row tests equality of the adjustment and later coefficients. Coefficients are log-point differences for tier 1 relative to pooled tiers 2 and 3, without exposure scaling. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
              r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}"]
    table = output / f"job_tiers_did_{model_family}_v1.tex"
    table.write_text("\n".join(latex) + "\n", encoding="utf-8")
    csv = output / f"job_tiers_did_{model_family}_v1.csv"
    pd.DataFrame(records).to_csv(csv, index=False)
    paths = {"table": table, "table_csv": csv}
    for outcome, variable, step in [("unemployed", "ln_parados", 0.025), ("contracts", "ln_contratos", 0.05)]:
        frame = pd.read_csv(estimates / f"twfe_tier_event_{model_family}_tiers_cno1_month_{variable}.csv")
        if set(frame.tier) != {1} or frame.duplicated(["tier", "event_time"]).any():
            raise ValueError("Event-study file must contain one unique tier 1 path")
        if "control_group" not in frame or set(frame.control_group) != {"tiers_2_3"}:
            raise ValueError("Event study must use pooled tiers 2 and 3 controls")
        for tier in (1,):
            numeric = output / f"JobTiers_{outcome}_{model_family}_tier{tier}.csv"
            frame.loc[frame.tier.eq(tier)].to_csv(numeric, index=False)
            figure = numeric.with_suffix(".png")
            _render_event_file(numeric, figure, _event_y_limits(numeric, step), step,
                               ylabel="Estimated log-point difference")
            vector = numeric.with_suffix(".tex")
            vector.write_text(build_tier_event_tex(frame, _event_y_limits(numeric, step), step * 2), encoding="utf-8")
            paths[f"{outcome}_tier{tier}"] = figure
            paths[f"{outcome}_tier{tier}_tex"] = vector
    return paths
