# Local TEV versus frozen Jev decisions

This comparison aligns all 502 CNO4 occupations. It compares the actual new local TEV outputs with unchanged Jev inputs. All retained econometric stages have now completed at the original specifications, seeds and production repetition counts.

| Decision | Agreement |
|---|---|
| Three-tier assignment | 382/502 (76.1%) |
| Matching argmax | 346/502 (68.9%) |
| Final reviewed crosswalk | 428/502 (85.3%) |

| Tier | TEV | Jev |
|---|---:|---:|
| 1 | 153 | 232 |
| 2 | 284 | 207 |
| 3 | 65 | 63 |

Exposures below are on the original 0–1 scale; mean absolute differences are shown in percentage points. Means and correlations are unweighted across occupations.

| Exposure | TEV mean (%) | Jev mean (%) | Mean absolute difference (pp) | Pearson | Spearman | Differences above 10 pp |
|---|---:|---:|---:|---:|---:|---:|
| nearest | 8.61 | 8.26 | 2.33 | 0.847 | 0.826 | 37 |
| conditional shortlist-weighted | 8.57 | 8.41 | 2.50 | 0.908 | 0.895 | 34 |
| direct | 4.18 | 12.54 | 8.40 | 0.819 | 0.903 | 167 |
| reviewed crosswalk | 8.53 | 8.55 | 1.00 | 0.944 | 0.943 | 19 |

TEV flags 166 baseline matches, compared with 216 in the frozen Jev screen. The new assistant-led review makes 56 explicit corrections; 123 final TEV crosswalk codes differ from the baseline. The original Jev/GPT-OSS crosswalk used 13 author corrections. Counts do not measure relative accuracy: reviewers, initial matches, architectures and residual errors differ.

The direct-exposure scores have high rank association but a substantially lower level under TEV (4.18% versus 12.54% on average). Similar ranks therefore do not establish score calibration or interchangeable magnitudes. Tier 1 also contains 79 fewer occupations. These are material differences, even where some matching-based exposures remain highly correlated.

## Interpretation and limits

Agreement is not accuracy. There is no independent labelled ground truth or blind human adjudication here. The Codex assistant inspected every new automatic crosswalk and recorded duty-based corrections/retention notes, including severe catalogue gaps. No old manual override list was applied automatically.

TEV uses a fixed cosine top-24 shortlist and shares its matching output with the flagged-correction stage. The Jev comparison uses its original matching workflow and a separate 30-candidate GPT-OSS verifier. Differences cannot be attributed solely to substituting the model. The shortlist contains the old Jev argmax for 485 occupations; this is candidate coverage, not accuracy. Weighted TEV exposure is conditional on those 24 candidates.

The pinned local runtime passed exact cold pairs for both production request shapes on the largest request. All 1,004 archived requests and responses pass identity/CRC checks; full offline replay reproduces 502 estimate records within 1e-12. This supports cached replication and bounded empirical cold-start repeatability, not universal deterministic fresh inference on arbitrary hardware or every request.

Production acquisition took 44,245.422 seconds (12.29 hours) on the verified i7-1165G7/16-GB Windows CPU setup. The completed SDID restart took 12,965.625 seconds; other stage timings are recorded in the validation report.

## Econometric comparison

The table reports preferred within-CNO1 phase coefficients. Exposure regressions are per 10 percentage points; tier coefficients are unscaled log-point differences for tier 1 versus pooled tiers 2 and 3. TEV weighted exposure is conditional on its shortlist. All 60 phase comparisons, including benchmark and no-2021 specifications, are recorded in `tev_estimate_comparison.csv`. Historical unrounded Jev coefficients come from the preserved main-release run; their preferred printed values agree with the unchanged independent publication tables. These comparison values are not analysis inputs or regenerated reference targets.

| Measure | Outcome | Jev adjustment | TEV adjustment | Jev later | TEV later |
|---|---|---:|---:|---:|---:|
| nearest | unemployment | 0.018 | 0.016 | 0.030 | 0.022 |
| nearest | contracts | 0.003 | 0.010 | 0.002 | 0.005 |
| weighted | unemployment | 0.022 | 0.017 | 0.037 | 0.026 |
| weighted | contracts | 0.000 | 0.009 | -0.003 | 0.004 |
| direct | unemployment | 0.040 | 0.060 | 0.082 | 0.142 |
| direct | contracts | -0.009 | 0.001 | -0.005 | 0.003 |
| edgecases | unemployment | 0.015 | 0.016 | 0.023 | 0.024 |
| edgecases | contracts | 0.004 | 0.004 | 0.005 | 0.001 |
| tiers | unemployment | 0.031 | 0.065 | 0.064 | 0.116 |
| tiers | contracts | -0.066 | -0.086 | -0.083 | -0.083 |

The tier pre-treatment diagnostics deteriorate materially. Jev's preferred joint-null p-values were 0.118 for unemployment and 0.408 for contracts; TEV's are 0.009529 and 0.007288. Excluding 2021, the TEV unemployment test still rejects (p=0.005422), while the contract test does not (p=0.226034). Consequently, larger post-release tier differences are not evidence of a better classifier or a more credible causal design.

Matching-based unemployment coefficients retain the positive sign, and contract responses generally remain imprecise. Direct-score coefficients become much larger as its exposure scale contracts; this is not mechanically evidence of a larger economic effect. Reviewed-crosswalk estimates are relatively close to the original estimates, but the review is not independent accuracy validation.

The experiment supports exact cached replication and shows that a small local model can produce usable structured decisions on this laptop. It does not establish quality equivalence to Jev or justify a drop-in replacement across all tasks. In particular, the tier diagnostics and direct-score calibration warrant separate validation against independent occupational judgements before replacing the main paper's workflow. Model, shortlist, verifier architecture and assistant review differences remain inseparable in this experiment.
