# Fixed effects terminology and task-bundling discussion

The current Prism draft defines fixed effects (FE) at the first main-text use
in the introduction and uses FE thereafter, including figure and table notes.
Section, subsection, and subsubsection headings use sentence case in the main
text, paper appendix, and online appendix, preserving names and acronyms.
Replication prompts, filenames, labels, and citation keys are unchanged.

Online Appendix H is titled **Task bundling and labor-market adjustment**.
The existing label `sec:v1_job_tiers` is retained. The author-marked locations
now contain descriptions of the three tiers, the bundling argument, and a
discussion of the coefficients and event studies. The main robustness section
introduces this as the second of three additional analyses, between alternative
estimators and aggregate calibration.

## Sources and interpretation

- [Garicano, Li, and Wu, Weak Bundle, Strong Bundle: How AI Redraws Job
  Boundaries](https://www.yanhuiwu.com/documents/Weak_strong_bundle.pdf),
  CEPR DP21453. The highlighted paragraph on physical PDF page 24 motivates
  the discussion: strong bundles can retain human tasks and downstream revenue,
  making labor's share more resilient than task exposure alone would imply.
- [Markus' Academy, AI and Messy Jobs](https://markusacademy.substack.com/p/ai-and-messy-jobs),
  9 July 2026. The tier descriptions also match the frozen Jev prompt already
  reproduced in the appendix.
- The current live `job_tiers_did_jev_v1.tex` and four tier event-study figures
  govern the results discussion. They match the working branch's frozen
  `data/processed/jev/paper_joint_checks` results. No estimates were replaced.

The text distinguishes the negative but insignificant preferred unemployment
estimates from the tier 1 adjustment-period contract estimate, which remains
significant after family-by-month FE. After excluding 2021, no contract estimate
is significant at 5%, and tier 1 adjustment is significant at 10%. Full-sample
pre-treatment tests reject; removing 2021 improves unemployment diagnostics
but contract diagnostics still reject. These comparisons do not identify a
causal protective effect of bundling, and the previous stronger claim is qualified.

## Source control and regeneration

- `lib/terminology.py` is the production rendering boundary for tracked
  table generators. It now renders fixed effects as FE while protecting
  verbatim material and technical references.
- `docs/prism_fe_job_tier_revision.patch` records the focused current
  `main.tex` edits. `docs/prism_fe_imports.patch` records the 18 changed live
  tables and two included appendix sources. Apply zero-context patches with
  `git apply --unidiff-zero` from the corresponding source root.
- The two appendix prose files are saved under `figuresNtables/`.
- The Jev table generators currently live on the coauthors' newer
  `codex/Jev-occupation-exposure` branch (source version `b2f741d`).
  `docs/jev_fe_generator.patch` updates those actual table writers to use the
  shared formatter and includes that formatter for the newer branch.
  Apply it from that branch's repository root with
  `git apply --unidiff-zero /path/to/jev_fe_generator.patch`.
- `test_artifacts/paper_generator_sources_fe.zip` is a local corrected source
  archive, extending the previously corrected supplied source archive with the
  shared FE formatter and corrected Jev writers. It is an ignored deliverable.

The 18 changed imported tables were rerendered from frozen live sources through
the production formatter. Their numerical tokens are unchanged, and their
rendered text matches exactly. Existing tracked table snapshots were rerendered
without replacing their older statistical versions. Eight targeted unit tests
pass, including a regression check for protected FE terminology. Prism compiled
successfully after refreshing its stalled preview; the first FE definition,
Appendix H title, tier descriptions, coefficients, citations, and cross-references
were verified in the compiled PDF.

## Separate exploratory comparison

The requested additional comparison, its script, estimates, LaTeX source, and
PDF are local ignored files in `test_artifacts/tier_comparison/`; none is part
of this commit or the paper. No regression results from that exercise are
recorded here. A time-invariant tier indicator is absorbed by occupation FE;
tier-by-period interactions are the separately disclosed meaningful comparison.
Baseline coefficients, standard errors, sample sizes, clusters, and phase
equality tests were checked against the exact frozen Table 2 results.

The native standalone compiler could not initialize its preview ("Unable to
find standard directories for platform"). The preserved source was compiled
using the existing MiKTeX installation, and the one-page PDF was rendered with
Poppler and visually checked, with no compilation or layout warnings.
