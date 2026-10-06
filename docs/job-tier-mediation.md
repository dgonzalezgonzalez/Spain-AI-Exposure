# Job-tier conditioning comparison in Online Appendix H

The exercise compares the preferred Table 2 exposure regressions with the same
sample and specification plus Jev tier-by-year-month FE. CNO1-by-year-month and
tier-by-year-month FE enter additively; this is not CNO1-by-tier-by-month FE.
The earlier privately emailed comparison used four tier-by-phase controls.
Actual monthly FE now replace those controls, as clarified with the author.
The rounded coefficients remain the same; equality tests and standard errors
change slightly. The phase-control variant is retained in the small CSV files
for comparison, but is not displayed in the manuscript table.

Time-invariant tier levels are absorbed by occupation FE. In an explicit
interaction parameterization, one tier is a reference because the three tier
indicators sum to one in each month. Absorbing all tier-month groups implements
the same model with the redundant levels normalized internally.

## Reproduction

Use the frozen full-panel input underlying the current Table 2 and job-tier
analysis: `runtime/jev_checks_90d4e394d10e/data/prepared/est_total_cno4_jev.csv`.
The panel comes from the coauthors' existing Jev run; main does not contain the
ignored runtime data. Stata requires the existing `reghdfe` and `ftools` packages.

```stata
do analysis/paper_replication/job_tier_mediation.do "path/to/est_total_cno4_jev.csv" "output_directory" "path/to/ado/plus"
```

The output CSVs are `job_tier_mediation_estimates.csv` and
`job_tier_mediation_pretrends.csv`. Small validated copies are tracked with the
table inputs. To regenerate both the table fragment and its marked insertion:

```powershell
python scripts/build_job_tier_mediation_table.py --results-dir analysis/paper_replication/figuresNtables --output analysis/paper_replication/figuresNtables/job_tier_mediation_v1.tex --appendix analysis/paper_replication/figuresNtables/appendix_oe_jev_tiers.tex
```

The optional `--standalone` argument updates the existing standalone editor
source in place. Its isolated preview supplies the external Table 2 reference;
the manuscript uses `\ref{tab:v1_main_effects}` directly.

The generated table is embedded in the existing Prism appendix file between
generation markers to avoid requiring a new cloud file. It appears after
Figure O.H.2 and before the unchanged classification prompt. The discussion
replaces the author's `Therefore... %COMPLETE HERE.` comment and preserves their
preceding edits. The source patch records the exact cloud-file update.

## Verification and interpretation

Baseline coefficients, standard errors, equality tests, observations and
clusters exactly reproduce the frozen preferred Table 2 CSVs. Baseline Wald
statistics and p-values also exactly match the independent `run_twfe` outputs.
The diagnostic uses exposure-by-event-time coefficients for -21 through -2,
with October 2022 omitted, in the complete event study through March 2026.
The adjusted diagnostic uses the same sample and additional tier-month FE.
Unemployment p-values are 0.0026627015 and 0.0032119348; contract p-values are
0.031847086 and 0.015175181. Both adjusted tests reject at 5 percent.

The title follows the author's requested “Job Tier Mediation Analysis” wording.
The discussion makes clear that conditioning on a fixed occupational tier does
not identify a post-treatment mediator or a causal indirect effect. Changes in
point estimates are suggestive of tier-related dynamics; they do not establish
stronger bundling as a protective mechanism, or a significant difference
between coefficients across specifications. The unemployment slopes are
positive and attenuate; the hiring slopes increase. The pre-trend caveat stays
beside this interpretation.

The existing standalone editor was kept open. Its native compiler still reports
`Unable to find standard directories for platform`; the same existing source
and PDF were compiled with the installed MiKTeX toolchain, without creating a
replacement document. Prism compilation and rendered table placement are
checked separately.
