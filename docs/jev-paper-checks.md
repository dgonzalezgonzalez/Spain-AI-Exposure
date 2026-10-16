# Frozen Jev paper checks

The paper uses the existing 502 Jev occupation classifications. No inference
is repeated by the econometric or publication commands below. The three
exposure specifications change only the exposure treatment; their baseline
phase estimates reproduce the coauthors' original results.

The tier exercise estimates one tier 1 indicator against pooled tiers 2 and 3.
The indicator enters with adjustment-period (0–24) and later-period (25–40)
interactions. Benchmark columns absorb CNO4 and
year-month fixed effects. Preferred columns and all displayed event studies
absorb CNO4 and CNO1-by-year-month fixed effects. The third column for each
outcome excludes 2021. Standard errors are clustered by CNO4.

Run the checks after preparing the coauthor occupation panel:

```powershell
py -3 scripts/run_occupation_paper_checks.py --model-family jev
```

Use `--tiers-only` to rerun only the binary tier comparison while preserving
the frozen exposure estimates. The 16 October 2026 run uses 232 tier 1
occupations and 270 pooled comparison occupations (207 in tier 2 and 63 in
tier 3). Classification, panel, windows, fixed effects, and clustering are
unchanged. Pooling requires re-estimation; the coefficients are not an
average of the earlier pairwise estimates.

The complete replication runner also executes these specifications before
publication rendering. `data/processed/jev/paper_joint_checks` freezes the
estimator CSVs, the occupation-input hash, the baseline-panel hash, and both
Stata source hashes and exact source copies. Git preserves those snapshot
bytes without line-ending conversion. The recorded run used StataNow 19 MP
and reghdfe 6.13.1.
One tier 1 event path comes from each outcome/specification regression.
The pre-trend test jointly tests that path's pre-treatment coefficients;
the phase-equality test compares the two tier 1 phase coefficients.
Estimator CSVs identify the comparison group as `tiers_2_3`, and the renderer
rejects stale pairwise estimates.

Render the frozen tier results and appendix fragments without Stata:

```powershell
py -3 scripts/jev_paper_outputs.py tiers --estimates-dir data/processed/jev/paper_joint_checks
py -3 scripts/build_model_appendices.py --model-family jev
```

The live manuscript places task bundling in Online Appendix O.H. Its updated
text is archived in `analysis/paper_replication/appendix_oh_jev.tex`, with
Prism table paths under `output/tables`. Its figures embed native LaTeX vectors
generated from the same tier 1 event CSVs, including their 95 percent bounds,
because Prism's binary-upload endpoint failed. The renderer also writes PNGs
and standalone vector fragments (`JobTiers_*_jev_tier1.tex`); vectors require
`pgfplots` with the `fillbetween` library. The generated
`figuresNtables/appendix_oe_jev_tiers.tex` remains a minimal definition/figure/
prompt fragment, rather than the manuscript narrative. The three-tier
mediation exercise is unchanged because it controls for the three original
tiers' monthly paths rather than estimating a pairwise tier comparison.
The main text's paragraph referring to O.H is synchronized with the pooled
results. The JSON prompts are checked against the frozen actual requests
before fragments are generated. The internal combined shareout is ignored.

The preferred adjustment/later estimates are 0.030882/0.064305 for log
registered unemployment and -0.065601/-0.082576 for log new contracts.
Their pre-treatment joint-null p-values are 0.117912 and 0.407687; without
2021 they are 0.457435 and 0.327548. All six phase specifications were
independently recomputed by alternating FE demeaning and least squares,
matching Stata within 1e-8; all 59 repository tests passed.

TEV remains an optional local experiment. Its full hierarchy exceeded the
two-hour budget on the available GPU, and fresh production-batch probabilities
failed repeatability checks. It supplies no results to the current paper.
