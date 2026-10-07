# Data dictionary and analysis conventions

All comma-separated files use UTF-8 unless the original INE CSV has its documented Spanish export encoding. Occupation codes are identifiers, not numbers: retain leading zeros, especially military CNO4 codes. Blank cells and pandas/R missing values represent unavailable information. A recorded zero count is a genuine zero, never a missing value.

## SEPE source snapshot

`data/input/sepe_cno4_monthly_ai_exposure.csv.gz` decompresses to the author-assembled SEPE aggregate snapshot. Its observation unit is **occupation × month × separately published dimension/category**. The source reports age, gender, and province separately; they do not provide a joint age-by-gender-by-province cross-tabulation. Do not add rows across dimensions.

| Variable | Definition and unit |
|---|---|
| `cno4` | Four-digit CNO-2011 occupation identifier, string |
| `occupation_title` | Provider occupation label |
| `period` | Calendar month, `YYYY-MM` |
| `dimension`, `category`, `gender` | Source tabulation and subgroup; `total`/`Total` denotes the occupation total |
| `source_url` | Original public SEPE report URL |
| `parados` | Registered unemployed workers at month end; persons, stock |
| `contratos` | Newly registered contracts during the month; contracts, flow |
| `personas` | Persons associated with contracts where available; not the contract count |
| `observed_exposure_cosine_nearest` | Time-invariant occupation exposure, fraction in [0,1] |
| `observed_exposure_cosine_weighted` | Assignment-weighted alternative exposure, fraction in [0,1]; an inherited spelling variant is recognized |

The inherited raw archive may contain fields beyond those used in the manuscript. They do not enter the retained estimation or publication output. Preparation selects the required analysis variables and produces separate panels rather than treating all source rows as independent total observations.

## Prepared analysis panels

Created under `output/work/data/prepared/` by `01_Preparation_v1.py`:

- `est_total_cno4.csv`: one row per CNO4-month, 502 occupations × 63 months = 31,626 rows.
- `est_age3_cno4.csv`: one row per CNO4-month-age group: under 30, ages 30–39, ages 40+. A group aggregate remains missing when an underlying required cell is unresolved.
- `est_gender_cno4.csv`: CNO4-month-sex panel.
- `est_province_cno4.csv`: CNO4-month-province panel; geography compares Madrid and Barcelona jointly against the rest of Spain, with province-by-CNO4 units.
- `est_total_cno4_jev.csv`: total panel with the independently replayed Jev occupation measures and tiers.
- `cosine_occupation_exposure.csv` and `jev_occupation_estimates.csv`: reconstructed occupation measures, checked against the frozen archive.

| Variable | Definition |
|---|---|
| `unit` | Panel-unit identifier; CNO4 alone for total data, combined with subgroup for disaggregated data |
| `cno2`, `cno1d` | First two/one digits of CNO4; broad occupation families |
| `ym_stata` | Stata monthly date: months since January 1960 |
| `ym_index` | Dense calendar-month index used by R |
| `event_time_nov2022` | Months relative to November 2022, including source January 2021 at −22 |
| `ln_parados`, `ln_contratos` | Natural logs; undefined at zero and excluded from corresponding baseline regressions |
| `ln_parados_p1`, `ln_contratos_p1` | Natural log of count plus one, retaining zero cells |
| `contratos_12m`, `ln_contratos_12m` | Current plus preceding 11 monthly contract flows and its log; first available December 2021 |
| `exposure_nearest`, `exposure_weighted` | Source occupation exposure fractions |
| `exposure_10pp`, `exposure_weighted_10pp` | Exposure divided by 0.10; regression coefficients therefore correspond to 10 percentage points |
| `post_nov2022` | November 2022 or later indicator |
| `treat_high`, `treat_zero`, `sdid_donor`, `binary_sample` | Treatment/sample flags using cutoff 0.1169; consult the relevant estimator for strict versus weak inequalities |
| `may2024_age_backcast`, `may2024_province_backcast` | Reconstruction source flags where applicable |
| `feminization_2017_2019` | Female share of employment by CNO2, averaged over pre-pandemic EPA quarters |
| `feminization_three_group` | Below p25, p25–p75, or above p75 of the retained feminization measure |
| `bls_ai_category`, `bls_ai_category_code` | Low, moderate, high, very high; ordinal coding 1–4, not a cardinal exposure fraction |
| `frs_lm_aioe`, `frs_lm_percentile`, `frs_lm_percentile_10pp` | Original language-modeling capability score, within-source percentile, percentile divided by 0.10 |

Estimator do-files generate numeric IDs and fixed-effect identifiers from these string keys. Their event-study window is −21 through +40, omitting October 2022 (−1). The static comparisons use adjustment months 0–24 and later months 25–40, with pre-treatment months as the reference. No-2021 variants start in January 2022. Fixed effects, clustering, sample sizes, and pre-trend windows are printed in the corresponding tables.

There are two zero-unemployment cells and 342 zero-contract cells in the complete total panel. Baseline logs omit these observations; log-plus-one robustness retains them. Further estimator balancing or sample restrictions can reduce the sample size beyond these zero exclusions.

## May 2024 missing subgroup cells

The two backcast files retain the occupation/category identifiers, reconstructed counts, reported June counts and percentage changes, and reconstruction/audit status. A rounded growth rate can imply several possible May integers. The reconstruction retains only an unambiguous feasible integer (or a value consistent with the documented provider totals); ambiguous cases remain missing. `code/lib/sepe_age_backcast.py` and `sepe_province_backcast.py` preserve the reconstruction rules and diagnostics. Full audit files are written under `output/work/intermediate/`; these are not new estimated paper results.

## Frozen cosine mapping

`cosine_embeddings.npz` contains float64 arrays `us` (756 × 2,560), `spanish` (502 × 2,560), and matching identifier arrays `us_codes` and `cno4`. They are the original `qwen3-embedding:4b` vectors, extracted from the author's content-addressed embedding cache, without retraining or rounding.

Nearest mapping selects the highest cosine similarity US occupation for each Spanish occupation. Weighted mapping assigns each US occupation to its nearest Spanish occupation, then averages the assigned US scores using cosine similarity weights. Spanish occupations without assigned US occupations fall back to their nearest match. The audited `0011` military-officer correction selects SOC `33-1012` in both measures. `spanish_occupation_matches_cosine_nearest.csv` records the matching codes, labels, texts, exposure, and similarity; external measures use this fixed crosswalk.

## Jev archive

| File | Observation unit / contents |
|---|---|
| `spanish_inputs.csv` | 502 occupations: CNO4, title, structured Spanish definition/tasks/examples/exclusions |
| `us_catalogue.csv` | 756 US occupations: SOC code, title, O*NET 30.3 description, Anthropic exposure |
| `questions.json` | Exact hierarchical matching, direct-score, and tier questions |
| `jev_response_cache.zip` | Raw JSON responses keyed by SHA-256 of exact request payloads |
| `request_audit.json` | Request-to-occupation mapping, model, question IDs, probability sums, usage and review diagnostics |
| `occupation_probabilities.csv.gz` | One CNO4 row with joint probabilities over all 756 US occupations |
| `direct_score_probabilities.csv` | Probabilities over ten direct exposure-score levels |
| `occupation_estimates.csv` | Three occupation exposures, matched SOC, tier and review/confidence diagnostics |
| `manifest.json` | Original model/rubric/source/artifact metadata for the author run |

Joint probabilities equal the SOC-major-group probability times conditional occupation probability; every branch is evaluated. Nearest exposure uses the global maximum joint probability, with lexicographic SOC tie-breaking. Weighted exposure sums probability × Anthropic exposure across all US occupations. Direct exposure is the expected score over levels 0–9 divided by nine; it predicts the source construct without supplying actual task-level Spanish Claude traffic.

`jev_tier` selects the most likely of three task-bundling categories, with smallest-number tie-breaking: 232 occupations in tier 1, 207 in tier 2, 63 in tier 3. Normalization corrects bounded API rounding; invalid distributions fail. Confidence/review flags describe model uncertainty and do not change estimation weights or drop observations. The original manifest also records an ancillary US direct-score benchmark; that benchmark is not a retained paper result and its separate diagnostic files are not included. The response archive is preserved intact.

## Other source files

INE CSVs preserve their provider's labels for sex, period, unit and occupation; the scripts select the required categories and convert reported thousands of persons where appropriate. BLS and AIOE workbooks preserve source sheet structure. The Economic Index archive is filtered by geographic identifier, occupation-category hierarchy, metric and month; global means pooled worldwide usage rather than an equal-country average. Adoption percentages describe different surveyed populations and are not directly comparable levels.

## Results and validation

Estimator CSVs under `output/work/intermediate/` contain specification, outcome, event time or phase, estimates, standard errors, intervals, observations and diagnostic tests. Table/figure notes define their scale. Tables are generated from those estimates; stored reference tables never supply coefficients. `output/intext_statistics.json` includes the sample facts and partial-equilibrium calibration, computed using unrounded preferred coefficients, with explicit checks at the manuscript's displayed precision.

## EPA unemployment source check

`epa_unemployment_microdata_weights.csv.gz` holds 143,554 public survey records classified as unemployed, with columns `quarter` (2021Q1–2026Q1), `AOI` (05/06) and `FACTOREL` (persons represented by the record). No record identifier is retained. Sum weights by quarter; compare with the arithmetic mean of three monthly SEPE totals. Plot at the first day of each quarter. This reproduces the archived survey-weight vintage; it must not be substituted with the latest revised aggregate table.

The retained dynamic continuous-DiD figure uses family shares among all positive-exposure occupations in each retained family (218 occupations across five families). The updated phase table uses shares among outcome-complete occupations (218 for unemployment, 205 for contracts). The historical figure and table therefore use different aggregation weights for contracts. Both are reproduced explicitly: `contdid_figure_event_*` feeds the figure; `contdid_event_*` and its covariance matrix feed phase tables. Confidence bands use the corresponding weighted influence-function covariance. The replication package reproduces this manuscript distinction rather than altering either result.

## SDID adjustment conventions

The baseline phase fits first residualize outcomes on CNO1-by-month cells using the full estimation sample and then hold that adjustment fixed during placebo inference. The strict exposure-above-0.2 versus zero-exposure fits retain the original branch's native projected covariate adjustment: family-by-month coefficients are fitted to donor outcomes with unit/time effects and refitted within each placebo assignment. Full-post path/event figures retain their original native projected adjustment. These different conventions are intentional reproductions of the source programs.

The manuscript SDID table note states that all columns use fixed full-sample residualization. That wording does not describe the strict columns' original projected-adjustment program. At the author's request, the archived manuscript note is preserved; the generated table and this codebook state the implemented distinction. No manuscript coefficients, standard errors, or significance stars are changed.
