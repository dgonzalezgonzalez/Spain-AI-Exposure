## Completed local TEV experiment: 31 October 2026

This is the current validation record for `codex/tev-deterministic`, based on main `c855fd9`. Earlier sections below describe historical Jev releases. Main's code/paper, original Jev/GPT-OSS sources and all independent reference targets are preserved. No commits, pushes or replacement of the Jev Prism project were performed.

The author selected fixed cosine top-24 matching, two grouped requests per occupation and reuse of the matching output for flagged crosswalk corrections. The acquisition completed all 502 occupations and 1,004 unique archived requests in 44,245.422 seconds (12.29 hours). Its ZIP passes CRC; every serialized request/runtime/response identity and source/artifact hash passes. Matching probabilities are conditional on each frozen shortlist, not a full-catalogue distribution. The 502-by-756 matrix has exact zeros outside support and sums to one within 1e-10; ten-level direct-score distributions normalize. Full offline replay used 1,004 cache hits and reproduces all 502 estimate records within 1e-12. The original 25 input-manifest entries are unchanged; 11 intentional TEV inputs were added.

The Codex assistant inspected all 502 automatic crosswalks against the frozen Spanish evidence and actual available US descriptions, including unflagged cases. The review records 56 explicit corrections and a note for every occupation. TEV flags 166 baseline matches; 123 final codes differ from baseline. This is assistant-led source review, not independent human adjudication or accuracy ground truth. Catalogue gaps and severely limited retained proxies remain documented in `manual_edgecases.md` and the frozen review JSON.

All retained econometric stages completed with unchanged specifications, Stata/R seed 20260728, 500 SDID placebo repetitions and 1,000 ContDID bootstraps. The ContDID process log explicitly records `biters = 1000`. The initial interrupted SDID run was not accepted: no success marker existed, all processes were absent, logs were preserved, inputs rechecked, and the entire SDID stage rerun at 500. The successful stage timings below exclude the interrupted work and manuscript/packaging checks.

| Stage | Seconds |
|---|---:|
| prepare | 180.719 |
| descriptives | 43.297 |
| estimates | 849.969 |
| sdid | 12965.625 |
| jev | 50.203 |
| mediation | 14.187 |
| contdid | 99.032 |
| edgecases | 26.703 |
| tuning | 20.484 |
| statistics | 2.500 |

All 88 retained assets pass:58 exact hashes,12 printed-numeric table comparisons,2 exact pixel comparisons,1 bounded single-channel rounding comparison and 15 changed-model checks. The latter independently recompute 48 TEV phase coefficients (maximum absolute error 1.481e-8),146 baseline/reviewed-crosswalk phase and event coefficients (2.883e-8),12 mediation coefficients using separate fixed-effect absorption, and 28 pairwise rank correlations (2.221e-16). Clustered standard errors are produced by the retained Stata estimators; these checks do not claim a second independent implementation of every standard error. New model figures are checked against their computed coefficient sources and visually reviewed, not required to match obsolete Jev pixels. Detailed per-asset evidence is in `validation_results.json`.

One immutable-reference convention differs: CNO 6430 is absent from the unemployment SDID donor sample. The renderer's zero allocation is compared with the reference dash only after verifying that absence; every other printed numeric cell is compared unchanged. The reference file is untouched. Frozen English labels are regenerated from the input lookup and may differ in capitalization/translation from curated reference labels. The longtable renderer restores local spacing and clarifies that weights are full-post weights. No donor weight or estimator changed. The deliberate `paper/sdid_estimates_manuscript.tex` wording discrepancy is preserved as instructed.

All 31 unittest tests and all 36 frozen input checks pass on the existing Windows 11/Python 3.12.10/R 4.5.2/StataNow 19 environment. The existing R library's 64 versions/source hashes were checked against the lockfile. R warns that two packages were built under 4.5.3; the actual run used 4.5.2 and completed. No fresh installation or other platform coverage is claimed.

The main practical finding is mixed. TEV agrees with Jev on 382/502 tiers and 346/502 matching argmaxes; reviewed crosswalks agree on 428/502. Tier counts change from 232/207/63 to 153/284/65. Direct exposure averages 4.18% versus 12.54%; its scale is not interchangeable. Preferred tier pre-treatment p-values change from 0.118/0.408 to 0.009529/0.007288 for unemployment/contracts. This prevents claiming a drop-in replacement of equivalent empirical quality. The shortlist, verifier architecture and assistant review also differ, so changes cannot be attributed solely to the model. Actual phase comparisons and interpretation are in `tev_comparison.md` and `tev_estimate_comparison.csv`.

The local runtime is pinned to Ollama 0.40.13, TEV1 4 B Q4_K_M and the recorded binary/weight digests, four CPU threads, context 8192, batch 128, no GPU, F 16 KV and cold model unloads. Both production request shapes for the largest request passed bit-identical cold pairs; warm probability drift had been observed. These observations support bounded empirical cold-start repeatability, while archived responses provide exact cached replication. They do not establish universal deterministic fresh inference.


## Historical Jev validation records

# Replication validation report

## Current update: 19 October 2026

Historical Jev-release validation (not a completed TEV certification): all **88 retained publication assets** pass: **27 tables and 61 PNG panels**. Current per-file evidence is `validation_results.json`; status counts are 66 exact hashes, 13 matching numeric tables, 2 matching pixel arrays, 1 bounded pixel-rounding difference, 3 new-result checks, 2 preserved pooled-tier path checks, and 1 expanded-matrix check. Earlier validation below records historical snapshots rather than a fresh full-estimator rerun.

The cached Jev screen is unchanged (502 occupations, 216 flagged). Only required-choice GPT-OSS verification was refreshed, followed by complete manual review and 13 explicit corrections. Final exposure covers all 502 occupations with no missing values or missing-to-zero conversion; 139 final matches differ from baseline. Required-choice proxies are documented and are not exact equivalence claims. `manual_edgecases.md` is the requested three-column audit. No new Jev calls were made.

`master.py --step edgecases` ran successfully in 35.234 seconds on the existing Windows/Python 3.12.10/StataNow19 environment. Both baseline and alternative regressions use identical occupation coverage and outcome-specific samples. Panel A's printed numeric cells, significance stars and sample counts match Panel A of O.D.7. An independent NumPy within-OLS implementation checked 146 phase and event coefficients against Stata; maximum absolute difference 2.839670825652979e-8 (tolerance 1e-7). Clustered standard errors and Wald tests come from the retained Stata estimators.

The eight-measure matrix preserves pairwise-complete counts and adds verified-match observed exposure. All 28 correlations independently reproduce with SciPy (maximum absolute difference 1.1102230246251565e-16); the new measure has 502 observations. Its baseline rank correlation is 0.84 at displayed precision. The matrix is now Figure O.D.10 at the end of O.D.; the new event study is O.D.9 and the table O.D.8.

Pre-edit Prism sources contained co-author revisions absent from main: acknowledgements, Garicano discussion, pooled tiers 2 and 3 as controls, and updated notes. These were preserved. The pooled-tier Stata runs and renderer now reproduce that existing comparison. The two independent inline vector paths exported before editing agree within 5.000000000837668e-9; obsolete PNG targets describe an older comparison and were not replaced by generated targets. Historical unretained panels were removed from publication output folders. The mediation note retains Prism's equivalent tier-3 reference description; additive tier-by-month fixed effects absorb all tier paths.

All **26 unittest tests passed** (including 4 new crosswalk/within-fit regressions). A pre-existing unclosed-file ResourceWarning occurs in the Jev missing-occupation failure-path test; it does not fail the test. Input checksum and archive CRC checks passed. Local pdfLaTeX/BibTeX compilation produced a 106-page paper with resolved citations and labels. The new method, table, event panels, prompts and matrix were visually inspected. A stale runtime ranking-table citation was aligned with the already-correct renderer and existing bibliography key; no numeric content changed. R/SDID, other costly estimators, fresh installations and other platforms were not rerun or newly certified for this update.

## Historical validation: 7 October 2026

The manuscript snapshot is dated 7 October 2026. All **87 retained assets** pass comparison with independently downloaded Prism assets: **26 LaTeX tables and 61 PNG panels**. The complete per-file results are in [validation_results.json](validation_results.json). The master produces only those 87 publication assets in `output/tables/` and `output/figures/`; logs, source checks, and estimator CSVs stay under `data/work/`.

Printed numeric table cells, sample counts, and significance stars match. Table whitespace, layout commands, comments, and terminology are normalized for comparison. Table statuses: {'exact': 14, 'numbers_match': 12}. Figure statuses: {'exact': 58, 'pixels_match': 2, 'pixels_match_with_rounding': 1}. Sixty panels have identical decoded RGB pixels; the adjusted SDID contracts event panel differs at four pixels, in six RGB channel values, each by one level out of 255. Its mean normalized pixel error is 3.390108152586327e-9. The validator accepts only same-size images with maximum channel difference at most one and mean normalized error at most 1e-8; substantive line, label, or geometry differences fail.

The EPA–SEPE panel was intentionally restyled at the author's request: no embedded title, manuscript navy/sky palette, and restrained horizontal grid. Survey weights, SEPE aggregation, sample period, and quarterly plotting dates are unchanged. The updated figure was uploaded to Prism, the manuscript compiled successfully, and a newly downloaded manuscript asset was SHA-256-identical to the renderer's PNG. Original and revised reference hashes and the reason are in [manuscript_changes.json](manuscript_changes.json). The original figure remains as a backup in Prism. This is an authorized presentation revision, not a replacement of an unexplained failed reference.

All 11 audited sample/calibration/tier facts match manuscript precision; their exact computed values and checks are in [validated_statistics.json](validated_statistics.json). For example, the panel contains 502 occupations over 63 months (31,626 rows), the preferred adjustment unemployment coefficient is 0.012061944129354, and calibration is 1.42%, 2.01%, and 1.64% at published precision. These are the explicitly audited in-text facts; the remaining reported estimates are checked through their mapped tables and figures.

## Verification procedure

A release ZIP was extracted into a new directory with spaces in its path, without generated/intermediate results. The full master prepared data and ran TWFE, baseline SDID, Jev robustness, joint tiers, mediation, and all retained continuous-DiD estimators. Stata used 500 placebo repetitions and R used 1,000 bootstrap repetitions. Targeted rendering and R stages were rerun after resolving historical plotting conventions. The corrected four strict-SDID phase fits were independently rerun against that clean extraction's prepared panel, in four separate Stata processes, each with all 500 repetitions. Their parallel verification took 60.3 minutes. No production table draws coefficients from stored paper targets.

Python dependencies were installed in a new virtual environment from `requirements-lock.txt`; `pip check` reported no broken requirements. The 22 standard-library regression tests passed. The 23 frozen input hashes, decompressed hashes, the Economic Index member hash, and all 71 vendored Stata software hashes pass. Offline cosine replay reproduces all 502 nearest/weighted occupation assignments to tolerance 1e-12. Jev replay verifies exact request/cache provenance and reproduces archived probabilities, direct scores, and 232/207/63 tier assignments without live API calls.

The EPA weight extract was also recreated from the 21 archived provider ZIPs using `code/acquisition/extract_epa_weights.py`. Its deterministic gzip hash matches the shipped extract, covering 143,554 unemployed public survey records. The source ZIP hashes/member names are in [epa_microdata_sources.json](epa_microdata_sources.json). Live SEPE downloads are optional; a fresh scrape of every provider report was not part of the frozen verification.

An additional directory with accented characters passed Python input staging, a Stata strict projected point-fit check (two development repetitions), and R package loading plus reading the 31,626-row panel. This is a path interoperability check, separate from production inference; it does not establish platform coverage or a fresh R installation. Its scope and result are in [portability_check.json](portability_check.json).

## Resolved historical differences and manuscript qualification

- The source-check figure uses original EPA microdata weighting vintage, rather than the currently revised aggregate table. The supplied quarter/activity/weight extract contains no identifiers.
- The continuous-DiD contracts figure uses original retained-family positive-occupation shares (218 occupations), while the updated phase table uses outcome-complete shares (205). Each covariance follows its own weights. Both manuscript results are explicitly reproduced, and the distinction is documented in the codebook.
- Strict SDID fits use the original branch's donor-based projected CNO1-by-month covariate adjustment, refitted during each placebo. Baseline phase fits use full-sample CNO1-by-month residualization held fixed across placebos. The manuscript table note describes all columns as fixed residualization. **At the author's request, that manuscript note remains unchanged.** The generated table and codebook describe the implemented distinction; this discrepancy concerns methodological wording, not the reproduced numeric cells.

## Software, hardware, and runtime

Verified host: Windows 11 x64 (build 26200), Intel Core i7-1165G7, four physical cores/eight logical processors, 16 GB RAM. Python 3.12.10 and exact library versions are recorded in [python_environment.json](python_environment.json). StataNow 19 MP and R 4.5.2 were used. Stata ado files are pinned by [stata_manifest.json](stata_manifest.json); R packages and GitHub commits are pinned by `renv.lock`.

The initial clean full-run timings below were measured on this host, with another verification job using resources concurrently. They are stage observations, not guaranteed standalone runtimes. The original strict phase implementation was subsequently corrected and rerun, so the SDID timing here does not include the corrected strict native-projection cost.

| Stage | Initial clean-run minutes |
|---|---:|
| prepare | 2.7 |
| descriptives | 0.5 |
| estimates | 15.7 |
| sdid | 99.8 |
| jev | 1.0 |
| mediation | 0.2 |
| contdid | 1.7 |
| tuning | 0.3 |
| statistics | 0.0 |

Native projected strict SDID is substantially more expensive than the baseline phase residualization. For production, allow several hours on this host; the master runs phases sequentially, whereas the four corrected verification jobs were run in parallel. Stage timing JSONs and logs are emitted on every local run.

## Verification limits

R analysis used an existing library whose 64 package versions and required GitHub source SHAs match `renv.lock`; the package-local setup validator succeeded. A complete R dependency restoration from an empty Windows library was not verified because the required Rtools45 compiler was unavailable. Install the documented compiler before such a restore. No R library or proprietary Stata executable is bundled.

Other operating systems and Stata versions were not independently run. The code resolves paths from the package, uses cached inputs offline, and was tested in a clean extraction, but that does not establish identical results on untested platforms. Changing software, data vintages, API responses, or repetition counts can change inference and will be caught by the comparison checks.

## Output-layout revision

At the author's request, final tables now reside in `output/tables/` and figure panels in `output/figures/`. Independent reference assets were moved to `docs/reference/`; internal caches reside in `data/work/` and validation/timing reports in `logs/`. All 87 existing publication assets retained their exact pre-move SHA-256 hashes. No estimation or rendering was rerun for this directory-only revision; the cached-output comparison was rerun against the relocated references.

The 87 verified publication outputs are now versioned in Git and included in the release ZIP. The initial directory revision shipped only folder placeholders; this packaging correction adds the existing output files without changing their bytes or rerunning the analysis.

## Manuscript and Prism migration

The current manuscript, two appendix sources, bibliography, preserved SDID wording, and compiled PDF now live in `paper/`. Root `main.tex` declares the document class and inputs `paper/main.tex`; active references use the same `paper/`, `output/tables/`, and `output/figures/` paths in Git and Prism. The 95 mirrored files were verified against a fresh Prism export. A complete 560-file historical backup and the original PDF were verified before migration. See [prism_sync.md](prism_sync.md) and [prism_sync_manifest.json](prism_sync_manifest.json).

The local pdfLaTeX/BibTeX build resolves all citations and cross-references. Prism also compiled successfully; its downloaded 101-page PDF is the versioned `paper/main.pdf`. Selected pages were visually inspected. The original export had 104 pages; publication table formatting and compilation produced the new pagination, without changes to estimates or narrative wording. A duplicate section label was removed, and a missing citation key in the exposure-ranking table and its renderer was replaced with the existing bibliography key for the same source. The SDID manuscript note remains unchanged, as explicitly requested, through its separate manuscript input.

All 87 numerical/pixel comparisons and 22 regression tests pass after the migration. No estimation stage was rerun. `code/build_paper.py` builds the paper separately, checks reference convergence, and keeps build intermediates in ignored `logs/`. `AGENTS.md` now specifies replication documentation, folder structure, backup and Prism synchronization checks for future agents.

For the 19 October 2026 appendix wording update, Prism compiled the edited sources successfully to a 106-page PDF. Pages 56, 62, 63, and 64 were inspected. The two revised appendix sources and the downloaded current PDF are versioned in `paper/`; the PDF SHA-256 is `2cd4a262c83ecb6a9d392b513a94dbfd56aea53cc48f3104af4454955055e800`. No estimates, data, tables, or figures were regenerated, and no statistical tests were rerun. `docs/output_map.csv` and `docs/paper_outputs.json` remain valid because the edits did not change source line positions. Prism latest project ZIP passes CRC but embeds a prior PDF (SHA-256 `8885c4fc32541dec903c1b6fc9ea04c830673935750ffd175a38a10494c44933`); the current PDF was downloaded separately. One extra Prism-only `paper/main_2.pdf` remains per author request. Full backups and hashes are recorded in `docs/prism_sync.md` and `docs/prism_sync_manifest.json`.


## Table O.G.4 occupation labels: 27 October 2026

Panel B now maps CNO4 codes to the existing frozen English-title lookup in `code/05_Output_tuning_v1.py`. Missing exposure values after the outer join are filled from the contracts weight export; CNO4 6430 is absent from the unemployment export but has exposure zero in both the contracts export and estimation panel. The renderer asserts that neither metadata field is missing. Regenerated only this table block: all 378 missing donor labels are restored and the exposure cell for 6430 changes from NaN to 0.000. Every other cell, weight, row order, and table line is unchanged. All 26 unittest tests pass on the existing Windows Python environment. No estimators were rerun. Local pdfLaTeX/BibTeX compilation succeeds with resolved references; `paper/main.pdf` was rebuilt.

The existing Prism project (`d2a38c9d-2c46-440b-92e1-6d206cb7f593`) also compiles successfully to 109 pages. A fresh project export passes ZIP CRC and confirms that only `output/tables/sdid_donor_weights_v1.tex` changed, byte-identical to Git. Newer co-author edits already present in Prism `paper/main.tex` and `paper/references.bib` were left untouched; the local PDF reflects the repository sources. Panel B on page 88 and the final table page 100 were visually checked. Project exports, the current Prism PDF, and browser screenshots are retained outside the release at `C:/Users/dgonzalez/Documents/PrismBackups/Spain-AI-exposure-20261027-OG4/`. The pre-edit ZIP SHA-256 is `f103fe732f7f14b90116ca0eda24ab6fc00413ed989b37b72d9868e277c5ccc4`; the final Prism PDF SHA-256 is `cdd455c77d8db0dc19ea6a811199d4c7c07083defe595edf4f3e5cd5edbf62e3`.


## Local TEV branch: acquisition and review complete, 31 October 2026

The experimental branch starts at main `c855fd9` and retains the package layout.
The author selected a faster top-24 cosine-shortlist experiment rather than
exhaustive matching. There are exactly two grouped requests per occupation;
matching is reused for flagged crosswalk corrections. Weighted exposure is
conditional on the shortlist and must not be described as full-catalogue weighting.
The shortlist contains the previous Jev argmax for 485 of 502 occupations; this
is candidate coverage, not a ground-truth accuracy estimate.

Ollama 0.40.13, TEV1 4B Q4_K_M, exact weight and CPU binary hashes, four CPU
threads, and cold model reloads are pinned in code/acquisition/tev-runtime.json.
Both production request shapes for CNO 6110 (the largest actual request) matched
bit for bit in cold pairs. All 31 current unittest tests pass, including Noul
validation and independent evidence separation. The frozen original input
checksums pass master.py --check-inputs. Production acquisition completed in
44,245.422 seconds: 502 occupations and 1,004 unique archived requests. Archive
CRC, every request/runtime identity, source hashes and artifact hashes pass.
The conditional 502-by-756 matrix and all ten-level score vectors normalize
within 1e-10. Full raw-cache offline replay reproduces all 502 estimate records
within 1e-12. All 502 crosswalks were source-reviewed by the assistant, with
56 explicit corrections; this is not independent human adjudication. Original
25 input-manifest entries remain unchanged; eleven intentional TEV inputs were
added. The 31 tests pass. Preparation (180.7s), descriptives (43.3s) and full TWFE
(850.0s) completed; queued SDID and remaining estimators are in progress.
This was a progress checkpoint; the current completion record above supersedes it. See tev_comparison.md for the actual decision comparison.
The Jev publication project and independent references remain unchanged.


### Interrupted estimator recovery, 31 October 2026

The initial SDID process and both supervisor processes were absent at the 02:02 Madrid check, while their stale status files still indicated running/waiting. SDID had no success marker and its log ended inside a 500-placebo computation at 00:52. No Stata or R estimator process remained. Windows had not rebooted; no corresponding application-crash event explained the termination, so the cause remains unknown. The interrupted logs were preserved under ignored `logs/interrupted_20261031_0052/`.

All frozen inputs were rechecked successfully. The already completed preparation, descriptives and TWFE stages were retained. The entire incomplete SDID stage was restarted at its original seed and 500 repetitions; no incomplete bootstrap output was accepted as a finished estimate. A single hidden supervisor queues the remaining TEV, mediation, 1,000-bootstrap continuous-DiD, reviewed-crosswalk, rendering, statistics and validation stages. Current runtime state is in `logs/tev_pipeline_status.json`; all subsequent queued stages then completed; current final checks are recorded above.


### Actual software environment

The final environment audit records all 32 Python packages in `tev_software_environment.json`. Nine ancillary versions differ from main's historical lock (HTML/network parsers, contourpy, fonttools, kiwisolver, pyparsing and tzdata); core numerical libraries match. The TEV branch's `requirements-lock.txt` now records the versions actually used. No installation or package version was changed during acquisition/estimation, and the existing original lock remains preserved in main/Git history. Successful numerical and pixel comparisons describe this actual environment, not a fresh installation. PDF inspection additionally used the installed pypdf and Poppler tools.


### Final manuscript and package checks

Root `main.tex` compiles successfully with local MiKTeX pdfLaTeX/BibTeX. All citations and cross-references resolve; the final log has no overfull boxes. The separate TEV PDF contains 109 pages. Updated methods/footnote, actual result prose, exposure and crosswalk tables/figures, tier paths/table, mediation table, correlation matrix, prompt endings and the SDID donor longtable were visually inspected from Poppler renders. A two-line orphan at the end of the local request template was removed by a small local line-spacing adjustment. The PDF SHA-256 is `220b04c42a50e3c458c5d10e4cafecdf546dd764ce6a73eba4cb2cf5e45e5274`.

The release ZIP is generated with all 88 publication assets, manuscript/PDF, analysis code, frozen inputs and raw response archive, tests and documentation. Runtime logs/caches, installed environments and model binaries are excluded. CRC, member hashes, output counts, input routing from an extraction with spaces, and full offline TEV replay are checked without rerunning expensive estimators. The ZIP checksum is recorded in `dist/latest_code.zip.sha256`; the ignored machine audit is `logs/tev_archive_validation.json`. The existing Jev Prism project remains untouched. No commits or pushes were made.
