"""Render the paired job-tier conditioning exercise from Stata CSV outputs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def p_text(value: str) -> str:
    number = float(value)
    return r"$<0.001$" if number < 0.001 else f"{number:.3f}"


def coefficient(row: dict[str, str]) -> str:
    p = float(row["p"])
    stars = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""
    return f"{float(row['estimate']):.3f}" + (f"$^{{{stars}}}$" if stars else "")


def render_table(estimates: Path, diagnostics: Path) -> str:
    results = {(r["outcome"], r["specification"], r["term"]): r for r in read_rows(estimates)}
    pre = {(r["outcome"], r["specification"]): r for r in read_rows(diagnostics)}
    columns = [(y, s) for y in ("ln_parados", "ln_contratos") for s in ("baseline", "month_fe")]
    for outcome in ("ln_parados", "ln_contratos"):
        baseline = results[outcome, "baseline", "dose_adjustment"]
        adjusted = results[outcome, "month_fe", "dose_adjustment"]
        for key in ("observations", "clusters"):
            if baseline[key] != adjusted[key]:
                raise ValueError(f"Comparison samples differ for {outcome}: {key}")
        for specification in ("baseline", "month_fe"):
            diagnostic = pre[outcome, specification]
            if int(float(diagnostic["df_num"])) != 20:
                raise ValueError("Expected 20 pre-treatment restrictions, event times -21 through -2")
            if diagnostic["observations"] != baseline["observations"]:
                raise ValueError("Static and dynamic regressions use different samples")
    lines = [
        r"\begin{table}[H]", r"\centering",
        r"\caption{AI Exposure and Labor Market Outcomes: Job Tier Mediation Analysis}",
        r"\label{tab:v1_job_tier_mediation}", r"\begin{threeparttable}",
        r"\scriptsize", r"\setlength{\tabcolsep}{3.5pt}", r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"& \multicolumn{2}{c}{\# of registered unemployed} & \multicolumn{2}{c}{\# of new contracts} \\",
        r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}", r"& (1) & (2) & (3) & (4) \\", r"\midrule",
    ]
    for phase in ("adjustment", "later"):
        rows = [results[y, s, f"dose_{phase}"] for y, s in columns]
        lines.append(rf"AI exposure $\times$ {phase} period & " + " & ".join(coefficient(r) for r in rows) + r" \\")
        lines.append(" & " + " & ".join(f"({float(r['se']):.3f})" for r in rows) + r" \\")
    lines.extend([
        r"\midrule", r"CNO1 $\times$ year-month FE & Yes & Yes & Yes & Yes \\",
        r"Tier $\times$ year-month FE & No & Yes & No & Yes \\",
        r"$p$-value: equal phase effects & " + " & ".join(p_text(results[y, s, "dose_adjustment"]["equality_p"]) for y, s in columns) + r" \\",
        r"Pre-treatment joint-null $p$-value & " + " & ".join(p_text(pre[y, s]["p_value"]) for y, s in columns) + r" \\",
        r"Observations & " + " & ".join(f"{int(results[y, s, 'dose_adjustment']['observations']):,}" for y, s in columns) + r" \\",
        r"\bottomrule", r"\end{tabular}", r"\begin{tablenotes}[flushleft]", r"\footnotesize",
        r"\item \emph{Notes:} Columns 1 and 3 reproduce the preferred specifications in columns 2 and 5 of Table~\ref{tab:v1_main_effects}. Columns 2 and 4 additionally include tier-by-year-month FE, allowing each Jev job tier its own monthly path. CNO1-by-year-month and tier-by-year-month FE enter additively. Tier 3 is the reference category for an equivalent explicit tier-interaction representation; adding all three tiers' interactions would be collinear with the time FE. Time-invariant tier indicators are absorbed by CNO4 FE. All columns use the same outcome-specific sample and include CNO4 and CNO1-by-year-month FE. The dependent variables are logarithms. The adjustment period is November 2022--November 2024 (event times 0--24), and the later period is December 2024--March 2026 (event times 25--40); all available pre-treatment months form the omitted category. Exposure is divided by 0.10, so coefficients correspond to a 10 percentage-point increase. Parenthesized standard errors are clustered by CNO4 (502 clusters). The equality row tests whether the two exposure coefficients are equal. The pre-treatment joint-null row reports the clustered Wald test that all exposure event-study coefficients at event times $-21$ through $-2$ equal zero, with October 2022 omitted, using each column's FE and sample. $^{***}p<0.01$, $^{**}p<0.05$, and $^{*}p<0.10$.",
        r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}",
    ])
    return "\n".join(lines) + "\n"


def standalone(table: str) -> str:
    # Supply the external Table 2 reference only in the isolated editor preview.
    return "\n".join([
        r"\documentclass[11pt]{article}", r"\usepackage[margin=0.8in]{geometry}",
        r"\usepackage{booktabs,threeparttable,amsmath,float}", r"\pagestyle{empty}",
        r"\makeatletter\newlabel{tab:v1_main_effects}{{2}{}}\makeatother",
        r"\renewcommand{\thetable}{O.H.\arabic{table}}", r"\setcounter{table}{1}",
        r"\begin{document}", table.rstrip(), r"\end{document}", "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--standalone", type=Path)
    parser.add_argument("--appendix", type=Path, help="Update the marked generated table in Appendix H")
    args = parser.parse_args()
    table = render_table(args.results_dir / "job_tier_mediation_estimates.csv", args.results_dir / "job_tier_mediation_pretrends.csv")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(table, encoding="utf-8")
    if args.standalone:
        args.standalone.write_text(standalone(table), encoding="utf-8")
    if args.appendix:
        source = args.appendix.read_text(encoding="utf-8")
        start = "% BEGIN GENERATED JOB TIER MEDIATION TABLE\n"
        end = "% END GENERATED JOB TIER MEDIATION TABLE"
        if source.count(start) != 1 or source.count(end) != 1:
            raise ValueError("Appendix must contain exactly one pair of generation markers")
        prefix, rest = source.split(start)
        _, suffix = rest.split(end)
        args.appendix.write_text(prefix + start + table + end + suffix, encoding="utf-8")


if __name__ == "__main__":
    main()
