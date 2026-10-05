# Frozen Jev paper checks

The paper uses the existing 502 Jev occupation classifications. No inference
is repeated by the econometric or publication commands below. The three
exposure specifications change only the exposure treatment; their baseline
phase estimates reproduce the coauthors' original results.

The tier exercise jointly estimates two treatment indicators, tier 1 and tier
2, with tier 3 omitted. Each indicator enters with adjustment-period (0–24)
and later-period (25–40) interactions. Benchmark columns absorb CNO4 and
year-month fixed effects. Preferred columns and all displayed event studies
absorb CNO4 and CNO1-by-year-month fixed effects. The third column for each
outcome excludes 2021. Standard errors are clustered by CNO4.

Run the checks after preparing the coauthor occupation panel:

```powershell
py -3 scripts/run_occupation_paper_checks.py --model-family jev
```

The complete replication runner also executes these specifications before
publication rendering. `data/processed/jev/paper_joint_checks` freezes the
estimator CSVs, the occupation-input hash, the baseline-panel hash, and both
Stata source hashes and exact source copies. Git preserves those snapshot
bytes without line-ending conversion. The recorded run used StataNow 19 MP
and reghdfe 6.13.1.
Both tier event paths come from a single regression per outcome/specification.
The table's pre-trend and phase-equality tests are joint across both tiers.

Render the frozen tier results and appendix fragments without Stata:

```powershell
py -3 scripts/jev_paper_outputs.py tiers --estimates-dir data/processed/jev/paper_joint_checks
py -3 scripts/build_model_appendices.py --model-family jev
```

Upload the two generated appendix fragments, their table inputs, and referenced
figures into Prism's `uploads/figuresNtables`. Insert O.D.'s fragment followed
by O.E.'s fragment immediately before Occupational Feminization; automatic
numbering moves that section to O.F. The JSON prompts are checked against the
frozen actual requests before fragments are generated. The internal combined
`shareout_jev_results.tex` and PDF are ignored by Git.

TEV remains an optional local experiment. Its full hierarchy exceeded the
two-hour budget on the available GPU, and fresh production-batch probabilities
failed repeatability checks. It supplies no results to the current paper.
