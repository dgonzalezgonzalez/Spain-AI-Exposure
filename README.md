# Data and Code for: AI Exposure and Registered Unemployment in Spain: Early Evidence from Occupation-Level Administrative Data

Diego González-González (Loyola University), Nicolás González-Pampillón (Institut d'Economia de Barcelona), Héctor Jiménez Portilla (Comisión Nacional de los Mercados y la Competencia), and Javier Vázquez-Grenno (Universitat de Barcelona and Institut d'Economia de Barcelona).

## Overview

This package reproduces the empirical results retained in the manuscript snapshot of 7 October 2026: **87 assets, comprising 26 LaTeX tables and 61 figure panels**, plus standalone sample and calibration statistics. The main sample covers 502 Spanish four-digit occupations over January 2021–March 2026. Registered unemployment is a monthly stock; registered contracts are a monthly flow.

After installing dependencies, run `python master.py`. It prepares the panels, replays frozen cosine and Jev calculations, estimates every retained specification, renders the publication assets, computes in-text statistics, and compares results with independently downloaded paper assets. The complete map is [docs/output_map.csv](docs/output_map.csv).

```text
master.py                 Single entry point
requirements*.txt         Python dependencies and version locks
renv.lock                 R dependencies and source commit pins
code/                     Numbered analysis programs and reusable helpers
code/acquisition/         Optional public SEPE retrieval and parsing
code/vendor/              Frozen Stata dependencies and software notices
data/input/               Frozen source and author-constructed inputs
docs/                     Codebook, provenance, output map, validation report
docs/paper/               Authoritative manuscript LaTeX snapshots
output/reference/         Assets downloaded from the manuscript
output/generated/         Newly computed publication assets
output/work/              Intermediate data, estimates, audits, and logs
tests/                    Parser, probability, and replication regressions
```

Reference assets are comparison targets, never estimator inputs. The manuscript snapshots preserve the original upload paths for inspection; they are not a standalone typesetting project.

## Data Availability and Provenance Statements

### Statement about rights

The package contains public aggregate tabulations, public survey weighting records, published occupational measures, and author-created crosswalks and model outputs. It contains no administrative microdata, personal identifiers, private API credentials, or licensed Stata binaries. Provider data retain their original reuse conditions and must be attributed. [docs/data_sources.md](docs/data_sources.md) supplies source links, versions, citations, transformations, and reuse information. Third-party software notices are under `code/vendor/licenses/`.

Author-written code and package documentation are released under the [MIT License](LICENSE). Source datasets, manuscript materials, and third-party software retain their separate terms; the MIT license does not replace those conditions. Cite the authors and preserve source notices when reusing the materials.

### Availability and provenance

All 23 inputs needed for the frozen analysis are included in `data/input/`. Running the analysis requires no network access, restricted-data application, model server, or API key. Dependency installation requires internet access or an existing package cache. File hashes identify the exact snapshots in [docs/input_manifest.json](docs/input_manifest.json); the Economic Index member hash is in [docs/archive_members.json](docs/archive_members.json).

Original download dates were not consistently recorded in the inherited archive; unverified dates are not supplied. Provider versions, release identifiers, report URLs, and hashes identify the source materials used here. The adoption-timing CSV was reconstructed from the paper's published percentages and linked primary sources because its original source CSV was absent.

### Dataset list

| Dataset | Included files | Source and use |
|---|---|---|
| SEPE aggregate occupation statistics | `sepe_cno4_monthly_ai_exposure.csv.gz` | [Monthly occupation reports](https://www.sepe.es/HomeSepe/que-es-observatorio/informacion-mt-por-ocupacion.html), January 2021–March 2026; total and separately published subgroup tabulations |
| INE classification and EPA statistics | `cno11_notas.pdf`, `ine_epa_ocupados_65134.csv`, `epa_unemployment_microdata_weights.csv.gz` | CNO-2011 definitions, sex-by-occupation employment, and public survey weights for the unemployment source check |
| Anthropic occupational exposure and geographic usage | `anthropic_job_exposure_onet.csv`, `release-2026-06-26.zip` | [Labor market impacts](https://www.anthropic.com/research/labor-market-impacts); June 2026 Economic Index release, selecting May 2026 Spain and pooled worldwide usage |
| External occupational exposure | `bls_ai_exposure_categories_2025_35.xlsx`, `felten_raj_seamans_language_modeling_aioe.xlsx` | BLS categories and Felten–Raj–Seamans language-modeling AIOE |
| Spanish AI-adoption percentages | `spain_ai_adoption_timing_sources.csv` | Published ONTSI, Banco de España, and Funcas aggregate observations; source links and plotting-date conventions in the CSV |
| Semantic mapping and labels | `cosine_embeddings.npz`, `spanish_occupation_matches_cosine_nearest.csv`, `cno4_english_titles.csv` | Author constructions using `qwen3-embedding:4b`; exact vectors permit offline replay |
| May 2024 reconstructions | `sepe_cno4_age_may2024_backcast_from_june.csv`, `sepe_cno4_province_may2024_backcast_from_june.csv.gz` | Author calculations from published June-over-May changes; ambiguous cells remain missing |
| Jev scores, tier assignments, and provenance | Nine files in `data/input/jev/` | Exact Spanish/O*NET inputs, questions, raw responses, probability vectors, estimates, audit, and original manifest for `jev-1.13.0` |

The analysis starts from the assembled SEPE aggregate-data snapshot, which preserves report URLs. Full original HTML caches are not shipped. `code/acquisition/refresh_sepe.py` preserves retrieval and parsing for independent source checks; current provider pages may differ from the frozen archive. Refreshes never silently replace paper inputs. Data definitions and missing-value conventions are in [docs/codebook.md](docs/codebook.md).

## Computational requirements

### Software requirements

- **Python 3.12**: direct dependencies in `requirements.txt`, complete tested environment in `requirements-lock.txt`. Jupyter is unnecessary.
- **Licensed StataNow 19 MP / Stata 19**: verified on Windows. Do-files specify language version 17, but other versions/platforms have not been independently verified. Bundled `reghdfe` 6.13.1, `ftools` 2.50.0, `sdid`, `sdid_event`, and their dependencies are selected through a package-local ado path. Do not update these before replication. Exact files are identified in `docs/stata_manifest.json`; the SDID header is incomplete, so hashes are authoritative.
- **R 4.5.2**: versions in `renv.lock`, including exact commits for `contdid`, `BMisc`, and `ptetools`. `code/setup.R` restores packages into `.r_libs/`. Installing archived compiled packages on Windows requires [Rtools45](https://cran.r-project.org/bin/windows/Rtools/rtools45/rtools.html); Linux/macOS require R package build tools.

No GPU, Ollama installation, TypeSafe account, or API key is needed. Archived Jev responses are replayed without live calls; new model responses need not reproduce those probability vectors.

### Controlled randomness

Stata uses seed `20260728`, reset within estimators, and **500 SDID placebo replications**. R uses seed `20260728` and **1,000 bootstrap repetitions**; the no-2021 appendix run resets the same seed. Embeddings and Jev responses are frozen. Changing repetition counts is for development and changes inference.

### Memory, runtime, and storage

The verification host is Windows x64, Intel Core i7-1165G7 (4 cores, 8 logical processors), 16 GB RAM. Plan for at least 16 GB RAM and 10 GB free disk space, plus software and R build tools. The SEPE input decompresses to approximately 452 MB. Province estimation and SDID dominate runtime. Actual timings and verification limits are in [docs/validation_report.md](docs/validation_report.md). The master writes environment information and stage timings to `output/run_environment.json`; individual reruns have separate timing files.

## Description of programs/code

| Program | Purpose |
|---|---|
| `master.py` | Input checks, staging, all estimation/rendering, in-text statistics, paper comparisons |
| `code/01_Preparation_v1.py` | Backcasts, total/age/gender/province panels, feminization, external measures, transformations |
| `code/lib/cosine_replay.py`, `code/lib/jev_replay.py` | Rebuild occupation measures from archived vectors/responses and check frozen scores |
| `code/02_Descriptives_v1.py` | Summary statistics, distributions, rankings, adoption timing, worldwide usage and EPA comparisons |
| `code/03_Estimates.do` | TWFE, binary treatment, heterogeneity and cross-group tests, geography, feminization, retained robustness |
| `code/03_SDID.do` | Adjusted SDID paths, events, weights, phase effects, strict exposure-above-0.2 versus zero robustness |
| `code/03_Jev.do`, `code/lib/job_tiers.do` | Three Jev measures and joint tier regressions |
| `code/job_tier_mediation.do` | Exposure gradients with and without tier-by-month effects |
| `code/04_Estimates_contDID_v1.R` | Stratified, control-adjusted, unconditional continuous DiD and no-2021 diagnostics |
| `code/05_Output_tuning_v1.py`, `code/lib/` | Publication rendering, diagnostics, terminology, and calibration |
| `code/setup.R` | R dependency installation/restoration before analysis |
| `code/acquisition/refresh_sepe.py` | Optional resumable public-report retrieval; outside the default frozen run |

Intermediate estimates and integrity audits under `output/work/` support the retained results. Only the 87 mapped publication assets are exported to `output/generated/`. Logs remain under `output/work/logs/`.

## Instructions to Replicators

1. Clone or extract the complete package. Preserve its directory structure. Spaces and accented characters in directory paths are supported.
2. Install Python 3.12, R 4.5.2 and required package build tools, and licensed Stata.
3. Create a Python environment and install locked dependencies. Windows example:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   python -m pip install -r requirements-lock.txt
   ```

   On macOS/Linux, activate with `source .venv/bin/activate`.

4. Restore R dependencies:

   ```text
   Rscript --vanilla code/setup.R
   ```

5. Run everything from the package root:

   ```text
   python master.py
   ```

   Executables can be specified with `--stata-exe` and `--rscript`, or environment variables `STATA_EXE` and `R_SCRIPT`. Standard Windows locations are detected. Example:

   ```powershell
   python master.py --stata-exe "C:\Program Files\StataNow19\StataMP-64.exe" --rscript "C:\Program Files\R\R-4.5.2\bin\Rscript.exe"
   ```

6. Inspect `output/validation.json`, `output/intext_statistics.json`, timings, and logs. Missing assets, differing printed numeric cells/significance stars, or differing figure pixels fail validation. Identical figure pixels pass despite PNG metadata differences. A maximum one-level RGB difference with mean normalized error at most 1e-8 is accepted for floating-point antialiasing; larger differences require visual review and resolution. Reviewed release comparisons are documented in `docs/validation_report.md`.

For a fresh run, use a new clone/extraction without `output/work/` or `output/generated/`; the master creates them. Paths resolve relative to the master file, so invocation from another working directory also works. To rerun one stage, use `--step` with `prepare`, `descriptives`, `estimates`, `sdid`, `jev`, `mediation`, `contdid`, `tuning`, `statistics`, or `validate`, after its predecessor inputs exist. `python master.py --check-inputs` verifies/stages all inputs without estimation. Run tests with `python -m unittest discover -s tests -v`.

Never replace `output/reference/` with regenerated files. Shortened bootstrap/placebo runs are not publication verification.

## List of tables and programs

[docs/output_map.csv](docs/output_map.csv) and [docs/paper_outputs.json](docs/paper_outputs.json) map every asset to its figure/table number, label, source-document line, estimation program, and rendering program. Multiple panels share a figure number.

| Results | Programs |
|---|---|
| Main figures and Tables 1–3 | Preparation, descriptives, TWFE, rendering |
| Appendices A–B: support, pre-trends, age tests and subgroup paths | TWFE, continuous-DiD support, rendering |
| Online Appendices A–C: EPA, rankings, binary treatment | Descriptives, TWFE, rendering |
| Online Appendix D: robustness, external measures, Jev | TWFE, Jev, rendering |
| Online Appendices E–F: feminization, geography | Preparation, TWFE, rendering |
| Online Appendix G: continuous and synthetic DiD | R, SDID, rendering |
| Online Appendix H: tiers and conditioning on tier dynamics | Jev, mediation, rendering |
| Online Appendix I: aggregate calibration | `code/lib/intext_statistics.py`, through the master |

The calibration uses unrounded coefficients and reproduces **1.42%, 2.01%, and 1.64%** at the manuscript's precision. It is an illustrative partial-equilibrium calculation, not an identified aggregate causal effect. Sample counts, zero cells, and tier counts are checked explicitly. Other estimates discussed in the prose appear in the mapped tables; outside-study facts are source citations rather than estimates from this package.

## References

Complete dataset and software references, URLs, release identifiers, and reuse notices are supplied in [docs/data_sources.md](docs/data_sources.md) and `code/vendor/licenses/`. Cite this paper when using its constructed measures, classifications, or code. The supplied archive identifies the exact source versions; live upstream releases may have changed.
