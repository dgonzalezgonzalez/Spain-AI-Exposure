# Replication validation report

## Scope and outcome

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
