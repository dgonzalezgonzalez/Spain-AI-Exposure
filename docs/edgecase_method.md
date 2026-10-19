# Complete occupational crosswalk robustness

The retained robustness exercise starts from the frozen nearest-neighbor crosswalk.
Jev's **15 October 2026 cached screen** is unchanged: `jev-1.13.0`, 502 occupations,
and a `wrong_match >= 0.5` gate selecting 216 occupations. The separate
heterogeneity probability is diagnostic and does not change this gate.

The author requested complete occupation coverage on 19 October 2026. Accordingly,
the retained GPT-OSS 120B stage requires one selection for every flagged occupation.
It replaces the exploratory abstention policy. The earlier exploratory 32
`NO_EQUIVALENT` and 38 `HETEROGENEOUS` outputs are not used in this exercise.
Each request supplies the same Spanish evidence and 30 cosine-ranked U.S.
candidates. The model selects a substantive equivalent or the best available
proxy; it cannot generate an exposure value. Published Anthropic exposure is
joined only after matching. This preserves all 502 Spanish occupations.

The authors review the complete automatic crosswalk, including unflagged cases.
Only clear residual conflicts receive explicit overrides in
`code/lib/edgecase_replay.py`; debatable scope and cross-national proxies remain.
The three-column author-review table documents the automatic and final titles.
Some occupations have no exact equivalent among the 756 exposure-bearing U.S.
categories. Required choice provides a proxy in these cases and cannot establish
that an exact counterpart exists or that its true exposure is known.

The known detector false positive was CNO 5941 (armed security guards), whose
baseline `33-9032 Security Guards` assignment was retained by the verifier.
This is one checked false positive, not an estimate that there was only one
false positive across all 502 occupations. No manual correction is applied there.
The exploratory count of 65 obvious concerns was a manual triage of old baseline
matches, not a gold-standard evaluation or a count of remaining errors.

`data/input/edgecases/frozen_requests.zip` retains the exact Jev and required-choice
GPT-OSS requests and raw responses used by the release. Metadata record versions,
settings, source hashes, counts and any completion repair. Default replication is
offline: `master.py --step edgecases` reconstructs the complete crosswalk, merges
it into the prepared SEPE panel and runs the same phase and event-study
specifications. No service credentials are included or required for replay.

Temperature 0, seed 42, top-k 1, top-p 1, min-p 0, repeat penalty 1 and
repeat-last-n 0 are fixed; reasoning effort is medium. The normal output budget is
6,144 tokens. An incomplete final answer caused by the budget is repaired at
8,192 tokens, without rerolling successful matches. Model aliases and hardware can
change, so the archived responses, rather than fresh inference, define the release.

Publication assets are `robustness_checks_edgecases_v1.tex` and the unemployment
and contracts `Robustness_*_edgecases.png` panels. The table's Panel A is the
original six-column baseline; Panel B changes the exposure crosswalk only. Both
panels use CNO4 clustering, the original periods and fixed effects, and a 10 pp
exposure increment. The two event-study panels use the preferred within-CNO1
specification and the original October 2022 reference month.

New results have no pre-existing independent manuscript target. Validation
therefore independently recomputes phase and displayed event-study coefficients
using Python within-transformed least squares and checks occupation coverage and
sample sizes against Stata. Existing reference assets remain independent targets;
updated job-tier targets come from the latest Prism export, preserving co-author
edits already present before this exercise.

The common publication label is **Verified-match observed exposure**. It identifies Panel B in Table O.D.8, the two event-study panels in Figure O.D.9, and the eighth measure in the correlation matrix. The matrix now follows the edge-case prompts at the end of Online Appendix O.D. and is numbered O.D.10. Its 28 off-diagonal rank correlations are independently checked with SciPy, including pairwise occupation counts; the new measure has 502 observations.

Preserved co-author edits already in Prism use tier 1 versus pooled tiers 2 and 3. Main-branch tier code and retained outputs were aligned with those existing estimates. The two inline vector paths exported before editing are an immutable independent target. Legacy PNG references for earlier tier comparisons remain historical evidence and are not replaced with generated images. Only current retained pooled-tier panels remain in publication output folders.
