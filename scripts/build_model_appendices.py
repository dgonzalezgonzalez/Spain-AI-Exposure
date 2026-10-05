"""Prepare Jev/TEV appendix fragments and the internal coauthor shareout source."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.jev_questions import direct_exposure_question, tier_question
from src.tev import string_question

PACKAGE = ROOT / "analysis/paper_replication"


def prompt_tex(question: dict) -> str:
    return "{\\singlespacing\n\\begin{Verbatim}[breaklines=true,breakanywhere=true,fontsize=\\footnotesize]\n" + json.dumps(
        question, ensure_ascii=False, indent=2) + "\n\\end{Verbatim}\n}\n"


def exposure_construction(label: str) -> str:
    return r"""Let $i=1,\ldots,N$ index O*NET occupations and $j=1,\ldots,J$ index Spanish CNO4d occupations, as in Section 2.2.2, and let $y_i$ denote Anthropic observed exposure. MODEL evaluates every branch of the occupation hierarchy. If $\mathcal P(i)$ denotes the path to occupation $i$ and $q_{j\ell}$ the conditional branch probabilities,
\begin{equation}
\label{eq:v1_FAMILY_occupation_probabilities}
p_{ji}=\prod_{\ell\in\mathcal P(i)}q_{j\ell},\qquad \sum_{i=1}^{N}p_{ji}=1.
\end{equation}
The highest-probability and probability-weighted measures are
\begin{equation}
\label{eq:v1_FAMILY_mapped_exposure}
\widehat y^{\,N}_j=y_{i^*(j)},\quad i^*(j)=\arg\max_i p_{ji};\qquad
\widehat y^{\,W}_j=\sum_{i=1}^{N}p_{ji}y_i.
\end{equation}
For the direct Score, $\pi_{jk}$ is MODEL's probability for level $k\in\{0,\ldots,9\}$, giving
\begin{equation}
\label{eq:v1_FAMILY_direct_exposure}
\widehat y^{\,D}_j=\sum_{k=0}^{9}\frac{k}{9}\pi_{jk},\qquad \sum_{k=0}^{9}\pi_{jk}=1.
\end{equation}
""".replace("MODEL", label).replace("FAMILY", label.lower())


def exposure_events(family: str, outcome: str) -> str:
    caption = "registered unemployment" if outcome == "unemployed" else "new contracts"
    measures = [("nearest", "Highest-probability O*NET occupation"),
                ("weighted", "Probability-weighted exposure"), ("direct", "Direct observed-exposure Score")]
    lines = [r"\clearpage", r"\begin{figure}[H]", r"\centering",
             rf"\caption{{Event-study estimates using {family.title() if family == 'jev' else 'TEV'}: {caption}}}",
             rf"\label{{fig:v1_{family}_exposure_{outcome}}}"]
    for index, (measure, label) in enumerate(measures):
        if index == 2:
            lines += [r"\vspace{0.22cm}", r"\begin{center}"]
        lines += [r"\begin{subfigure}{0.48\textwidth}",
                  rf"\includegraphics[width=\textwidth]{{\figdir/Robustness_{outcome}_{family}_{measure}.png}}",
                  rf"\caption{{{label}}}", r"\end{subfigure}"]
        if index == 0:
            lines += [r"\hfill"]
        if index == 2:
            lines += [r"\end{center}"]
    lines += [r"\begin{minipage}{0.94\textwidth}", r"\footnotesize \emph{Notes:} " +
              f"The dependent variable is the logarithm of {caption}. Panels (a)--(c) use the highest-probability O*NET category, probability-weighted exposure, and direct Score, respectively. " +
              "Each regression includes CNO4 and CNO1-by-year-month fixed effects. Coefficients are marginal effects of a 10 percentage-point increase in the indicated exposure measure. " +
              "October 2022 is omitted; the dashed line marks November 2022. Shaded areas show 95 percent confidence intervals with standard errors clustered by CNO4. Each panel uses its own vertical scale.",
              r"\end{minipage}", r"\end{figure}"]
    return "\n".join(lines) + "\n"


def tier_events(family: str, outcome: str) -> str:
    caption = "registered unemployment" if outcome == "unemployed" else "new contracts"
    lines = [r"\clearpage", r"\begin{figure}[H]", r"\centering",
             rf"\caption{{Joint job-tier event study: {caption}}}", rf"\label{{fig:v1_{family}_tiers_{outcome}}}"]
    for tier in (1, 2):
        lines += [r"\begin{subfigure}{0.70\textwidth}",
                  rf"\includegraphics[width=\textwidth]{{\figdir/JobTiers_{outcome}_{family}_tier{tier}.png}}",
                  rf"\caption{{Tier {tier} relative to tier 3}}", r"\end{subfigure}", r"\vspace{0.22cm}"]
    lines += [r"\begin{minipage}{0.94\textwidth}", r"\footnotesize \emph{Notes:} " +
              f"Both tier paths are estimated jointly in one regression for the logarithm of {caption}. Tier 3 is the omitted control group. " +
              "The specification includes CNO4 and CNO1-by-year-month fixed effects. Coefficients are log-point differences, with no exposure scaling. " +
              "October 2022 is the omitted reference month; the dashed line marks November 2022. Shaded areas are 95 percent confidence intervals with standard errors clustered by CNO4. Each graph uses its own vertical scale.",
              r"\end{minipage}", r"\end{figure}"]
    return "\n".join(lines) + "\n"


def large_shareout_pair(family: str, measure: str, label: str, *, tiers: bool = False) -> str:
    prefix = "JobTiers" if tiers else "Robustness"
    lines = [r"\clearpage", r"\begin{landscape}", r"\begin{figure}[H]", r"\centering", rf"\caption{{{label}}}"]
    for index, (outcome, caption) in enumerate([("unemployed", "Registered unemployment"), ("contracts", "New contracts")]):
        lines += [r"\begin{subfigure}{0.48\linewidth}",
                  rf"\includegraphics[width=\linewidth]{{\figdir/{prefix}_{outcome}_{family}_{measure}.png}}",
                  rf"\caption{{{caption}}}", r"\end{subfigure}"]
        if index == 0:
            lines.append(r"\hfill")
    notes = ("Both treatment-tier paths enter the same regression, with tier 3 as the control. Coefficients are log-point differences. "
             if tiers else "Coefficients are marginal effects of a 10 percentage-point increase in the indicated exposure measure. ")
    lines += [r"\begin{minipage}{0.94\linewidth}", r"\footnotesize \emph{Notes:} " + notes +
              "Outcomes are in logarithms. Regressions include CNO4 and CNO1-by-year-month fixed effects. October 2022 is omitted; the dashed line marks November 2022. " +
              "Shaded areas are 95 percent confidence intervals with standard errors clustered by CNO4. Each graph uses its own vertical scale.",
              r"\end{minipage}", r"\end{figure}", r"\end{landscape}"]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-family", choices=("jev", "tev"), default="jev")
    family = parser.parse_args().model_family
    label = "Jev" if family == "jev" else "TEV"
    data = ROOT / f"data/processed/{family}"
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    if manifest["partial_run"] or manifest["spanish_count"] != 502:
        raise ValueError("Paper appendices require a completed 502-occupation experiment")
    questions = json.loads((data / "questions.json").read_text(encoding="utf-8"))
    tier = tier_question() if family == "jev" else string_question(tier_question())
    direct = direct_exposure_question()
    if questions["tier"] != tier or questions["direct_exposure"] != direct:
        raise ValueError("Appendix definitions differ from frozen actual prompts")
    figures = PACKAGE / "figuresNtables" if family == "jev" else PACKAGE / "figuresNtables/tev"
    required = [f"robustness_checks_{family}_v1.tex", f"job_tiers_did_{family}_v1.tex"]
    required += [f"Robustness_{outcome}_{family}_{measure}.png" for outcome in ("unemployed", "contracts") for measure in ("nearest", "weighted", "direct")]
    required += [f"JobTiers_{outcome}_{family}_tier{tier}.png" for outcome in ("unemployed", "contracts") for tier in (1, 2)]
    matrix = "Exposure_correlation_matrix.png" if family == "jev" else "Exposure_correlation_matrix_tev.png"
    for name in [*required, matrix]:
        if not (figures / name).is_file():
            raise FileNotFoundError(figures / name)
    od = f"\\clearpage\n\\subsection*{{{label} Exposure Measures}}\n" + exposure_construction(label)
    od += f"\\input{{\\figdir/robustness_checks_{family}_v1.tex}}\n"
    for outcome in ("unemployed", "contracts"):
        od += exposure_events(family, outcome)
    status = json.loads((figures / "exposure_measure_matrix_source_status_v1.json").read_text(encoding="utf-8"))
    od += ("\\clearpage\n\\begin{figure}[H]\n\\centering\n\\caption{Correlations across occupational exposure measures}\n" +
    rf"\label{{fig:v1_{family}_exposure_correlations}}" + "\n" + rf"\includegraphics[width=0.98\textwidth]{{\figdir/{matrix}}}" + "\n" +
    "\\begin{minipage}{0.94\\textwidth}\n\\footnotesize \\emph{Notes:} Spearman rank correlations across Spanish CNO4 occupations; cells show correlations and pairwise-complete occupation counts. Each occupation receives equal weight. BLS categories and LM-AIOE percentiles use the baseline occupation crosswalk. " +
    f"BLS exposure maps to {status['bls_occupations']} occupations; LM-AIOE maps to {status['frs_lm_aioe_occupations']}.\n" +
    "\\end{minipage}\n\\end{figure}\n\\clearpage\n\\subsubsection*{Direct observed-exposure prompt}\n" + prompt_tex(direct))
    oe = ("\\clearpage\n\\section{Three Job Tiers}\n\\label{sec:v1_job_tiers}\n" +
    f"Let $\\tau_{{jt}}$ be {label}'s probability for tier $t\\in\\{{1,2,3\\}}$. The assigned tier and treatment indicators are\n" +
    "\\begin{equation}\n" + rf"\label{{eq:v1_{family}_tier_assignment}}" + "\n" +
    r"\widehat T_j=\arg\max_t\tau_{jt},\qquad D_j^r=\mathbf{1}\{\widehat T_j=r\},\quad r=1,2." +
    "\n\\end{equation}\n" +
    "Probability vectors are normalized after API rounding; ties select the smallest tier number. Tier 3 is the omitted control group.\n" +
    f"\\input{{\\figdir/job_tiers_did_{family}_v1.tex}}\n")
    for outcome in ("unemployed", "contracts"):
        oe += tier_events(family, outcome)
    oe += "\\clearpage\n\\subsubsection*{Three-tier categorization prompt}\n" + prompt_tex(tier)
    for name, source in [(f"appendix_od_{family}.tex", od), (f"appendix_oe_{family}_tiers.tex", oe)]:
        (figures / name).write_text(source, encoding="utf-8")
    internal_od, internal_oe = od, oe
    for outcome in ("unemployed", "contracts"):
        internal_od = internal_od.replace(exposure_events(family, outcome), "")
        internal_oe = internal_oe.replace(tier_events(family, outcome), "")
    large_exposure = "".join(large_shareout_pair(family, measure, f"{label}: {title}") for measure, title in [
        ("nearest", "highest-probability category"), ("weighted", "probability-weighted exposure"), ("direct", "direct exposure Score")])
    large_tiers = "".join(large_shareout_pair(family, f"tier{tier}", f"Tier {tier} relative to tier 3", tiers=True) for tier in (1, 2))
    internal_od = internal_od.replace(f"\\input{{\\figdir/robustness_checks_{family}_v1.tex}}", f"\\input{{\\figdir/robustness_checks_{family}_v1.tex}}\n" + large_exposure)
    internal_oe = internal_oe.replace(f"\\input{{\\figdir/job_tiers_did_{family}_v1.tex}}", f"\\input{{\\figdir/job_tiers_did_{family}_v1.tex}}\n" + large_tiers)
    header = r"""\documentclass[10pt]{article}
\usepackage[a4paper,margin=11mm]{geometry}
\usepackage[T1]{fontenc}
\usepackage{lmodern,graphicx,pdflscape,booktabs,threeparttable,float,subcaption,amsmath,fvextra,setspace}
\setlength{\parindent}{0pt}
\newcommand{\figdir}{FIGDIR}
\begin{document}
""".replace("FIGDIR", "figuresNtables" if family == "jev" else "figuresNtables/tev")
    (PACKAGE / f"shareout_{family}_results.tex").write_text(header + internal_od + internal_oe + "\n\\end{document}\n", encoding="utf-8")
    print(f"Prepared {label} O.D./O.E. fragments and internal shareout source.")


if __name__ == "__main__":
    main()
