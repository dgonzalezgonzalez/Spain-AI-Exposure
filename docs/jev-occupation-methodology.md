# Jev occupation exposure and Messy Jobs tiers

## Specification

The project-local TypeSafe skill is installed at `.agents/skills/typesafe-ai/`
from [typesafe-ai/skills](https://github.com/typesafe-ai/skills/tree/main/skills/typesafe-ai).
It was read alongside the live [HTTP API](https://docs.typesafe.ai/api),
[Choice](https://docs.typesafe.ai/primitives/choice),
[confidence](https://docs.typesafe.ai/confidence), and
[model](https://docs.typesafe.ai/models) documentation on 20 September 2026.
The run pins `jev-1.13.0`; changing models requires changing that explicit constant.

The Anthropic source has 756 occupations, all with O*NET 30.3 descriptions.
The existing INE CNO-2011 parser supplies 502 Spanish occupations, their titles,
definitions, tasks, included examples and excluded occupations. This reuses the
same structured descriptions as the embedding pipeline, including its section
length limits and PDF extraction artifacts. No further text truncation is applied.
Descriptions remain in Spanish; Jev's documentation identifies English as its
strongest language. Domain-specific multilingual classification accuracy has not
been independently estimated.

### Exhaustive hierarchy

Jev permits at most 255 options per Choice, so one 756-option question is invalid.
The user explicitly approved exhaustive hierarchical classification in place of
the originally requested flat classification. For each Spanish occupation `s`:

1. Classify it over the 22 SOC major groups represented in the Anthropic source.
   Root options use the SOC group names.
2. Ask a conditional Choice for **every** group, including those with zero root
   probability. Each option contains the US occupation code, title and full
   O*NET description. The premise explicitly conditions on membership in that group.
3. Construct each leaf probability as
   `p(j | s) = p(group(j) | s) * p(j | group(j), s)`.

There is no beam search, nearest-neighbor shortlist, top-k restriction or pruning.
Independent questions share the same Spanish state and are batched within
conservative UTF-8 byte budgets (31,000 for state plus one question, 60,000 for a
whole request, including serialized request structure). These are deliberately
stricter than the documented 32k/64k token limits; oversized inputs fail before
the run spends tokens. All current inputs pass.

The resulting joint distribution covers all 756 occupations. It is a hierarchical
model specification, **not equivalent to a hypothetical flat Jev distribution**.
Broad SOC group assignment can influence matches at occupational boundaries.

- `observed_exposure_jev_nearest`: Anthropic exposure for the occupation with
  maximum **joint** probability across all groups. This need not belong to the
  most likely group. Ties use lexicographically smallest SOC code.
- `observed_exposure_jev_weighted`: sum of exposure times joint probability over
  every US occupation, including zero-probability options.

Jev's `confidence` is one statistic for an entire Choice; it is not a separate
weight for each category. The requested category-confidence weights are therefore
implemented using `probabilities`. Root and selected conditional confidence are
reported separately; their product is not called a global model confidence.
Individual occupation exposure values, unemployment, contracts and other
SEPE outcomes never enter the matching and tier prompts. The direct exposure
prompt uses two **published aggregate examples** as scale anchors, described below.

### Direct Jev observed exposure

This is a third, distinct imputation. Each Spanish occupation is judged from its
CNO title and structured description with a Jev **Score**, rather than a Noul.
The quantity is a degree of occupation-level exposure; a Noul would estimate
the probability of a binary proposition, which would not in general equal that
degree. Ten ordered levels anchor the 0–1 scale at 0/9, 1/9, ..., 9/9. Jev
returns a distribution over those levels. The reported
`observed_exposure_jev_direct` is its probability-weighted expected level
divided by 9, after bounded correction of API probability rounding. Jev's raw
0–9 score and confidence are retained for inspection. The raw ten-level
distribution is also stored per occupation.

The question quotes Anthropic's central definition from [the paper](https://www.anthropic.com/research/labor-market-impacts)
and operationalizes its [formal appendix](https://cdn.sanity.io/files/4zrzovbb/website/e5f77fc0e77c0185110b5e4b909602791ae76eae.pdf):
task coverage requires theoretical LLM feasibility (Eloundou beta at least 0.5)
and at least 100 work-related Claude.ai plus API uses in Anthropic's August and
November 2025 Economic Index samples. Covered tasks receive factor
`0.5 + 0.5 × (Claude work use × automation share + API use) / total work use`;
an occupation averages those factors by estimated task time share. The beta 0.5
case is fully eligible; it is not itself a 0.5 weight. Work-related and API
usage are distinct from merely possible or personal uses. The prompt also includes
the paper's published calibration examples: US Computer Programmers approximately
0.75, Data Entry Keyers approximately 0.67, and several zero-coverage jobs.
These illustrate scale; the Spanish estimates still come from separate Jev
judgments without supplying any US match, US occupation table, tier, or outcome.

Jev has no live task-level Claude.ai/API traffic counts or task-time fractions in
these requests. Thus this output **predicts** Anthropic-style observed exposure;
it is not a new measurement of actual Spanish Claude usage and cannot implement
the appendix formula exactly. The source's task usage threshold can create exact
zeros that a semantic model cannot verify. Score confidence measures distribution
concentration, not empirical accuracy. `jev_direct_review` marks confidence below
0.5 for human inspection; flagged rows are retained. The exact exposure and tier
questions sent to Jev appear alone in [the prompt appendix](jev-prompts-appendix.md).

The [Economic Index data explorer](https://www.anthropic.com/economic-index#data-explorer)
and cached June 2026 country release provide Spain/US **SOC major-group shares of
Claude usage**. They do not supply the occupation-by-task traffic counts, the
100-use threshold, automation mix and time weights used by the March 2026 measure;
they also cover a later period. Inserting those shares as if they were exposure
would misstate the target, so they are not passed to Jev.

An optional US benchmark sends the same Score question each of the 756 US O*NET
titles and descriptions while withholding their published exposure values, then
compares predictions with Anthropic's occupation file. Reported holdout metrics
exclude exact titles named as prompt anchors. This is a calibration diagnostic,
not a validation of Spanish truth: US and Spanish descriptions differ in
granularity and language, and the prompt still contains the named benchmarks.
With the pinned prompt/model, 751 non-anchor US rows have Spearman correlation
0.690 and mean absolute error 0.081 against Anthropic's values. Jev's mean
prediction is 0.054 higher. This upward bias matters for level comparisons;
the Spanish direct scores are uncalibrated model predictions, not measurements.

### API rounding

The live pilot showed Jev probabilities serialized to hundredths, sometimes
summing to 0.99 or 1.01 despite the documentation's sum-to-one contract. We require
every expected key, finite values in [0,1], a selected answer from the supplied options,
and valid confidence and usage. Hundredth-rounded vectors may deviate from one
by at most `min(0.05, 0.005 * category_count)`; other vectors have a `1e-5`
tolerance. Accepted vectors are divided by their sum **before** hierarchy
composition. We do not fill missing categories, smooth zeros, or normalize
arbitrary scores. Raw responses remain cached; the request audit retains all
pre-normalization sums. Therefore zero weights may reflect API quantization,
rather than exact zero underlying model probability.

The full run also exposed an API-selected label at probability 0.32 when another
option had 0.33. We use the probability argmax for our classifications, as requested,
and preserve this disagreement in the raw response and request audit. Output
columns count such disagreements; a disagreement in the root or winning conditional
question flags the match for review, and one in the tier question flags its tier.
Disagreements within unrelated conditional groups are counted but do not alone flag
the final match. API confidence is retained as returned rather than recalculated.

### Messy Jobs tiers

The rubric uses Luis Garicano's talk, **AI and Messy Jobs**, Markus Academy,
9 July 2026. The requested [YouTube video](https://www.youtube.com/watch?v=70IebKR2lK0)
was accessed through its English captions; those captions were retrieved and
read, with the user's screenshot and
[Princeton's official summary](https://bcf.princeton.edu/events/luis-garicano-on-ai-and-messy-jobs/)
as corroboration. The authors' [book website](https://messyjobs.ai/) was also
consulted. Caption text can contain transcription errors; the rubric paraphrases
the economic distinctions rather than reproducing those errors. The full video
and transcript are not republished in the repository.

Relevant passages:

- **12:48–17:47:** tier 1, separable outputs with clear inputs and verifiable
  results. Automation depends on technology, demand and regulation. Driving is an
  explicit example when other duties are absent; tier 1 is not digital-only.
- **17:51–22:27:** tier 2, task bundles held together by coordination, knowledge
  spillovers and joint measurement. Radiology and complex sales illustrate why
  automating one task does not classify the whole job as replaceable.
- **46:31–56:35:** tier 3, authority amid conflicting interests, private information,
  trust, accountability and legitimate decision-making. Pure scheduling or routine
  information exchange is not sufficient evidence of relational authority.
- **56:36–59:10:** organizational implementation requires understanding workflows,
  tools and stakeholder resistance; technical implementation alone is not the
  intended distinction.
- **1:00:58–1:02:35:** the three economies recap, including nurses and plumbers in
  the messy middle and authority, implementation and authenticity in tier 3.

The operational rubric is centralized in `src/jev_questions.py`. It is a research
operationalization, not an occupation mapping published or endorsed by Garicano.
Tier 1 denotes the algorithmic economy; tier 2 denotes strongly bundled jobs;
tier 3 denotes relational work whose central value lies in authority,
organizational change or human origin. Social contact, professional responsibility
or a managerial title alone does not force tier 3. Aggregate tier shares are not
imposed. Ambiguous, heterogeneous CNO groups retain all three probabilities.
`jev_tier` is their argmax, with smallest tier number breaking ties. Tiers are
categories; their numbers are not cardinal measures of displacement risk.

### Research review

`jev_match_review` and `jev_tier_review` flag a maximum probability below 0.6 or
a top-two gap below 0.15. These are transparent review heuristics, not calibrated
error guarantees; no flagged row is dropped. Spanish armed-forces occupations
are additionally flagged because the Anthropic catalogue has no military group.
Their assigned civil equivalents remain forced comparisons, not exact matches.
Do not interpret model confidence or the smoke-test checks as measured accuracy.

## Running

Install the project's existing requirements and set `TYPESAFE_API_KEY` in the
process environment, using a secret manager or an interactive prompt. No key
belongs in source, command examples, cache records, manifests or Git.

```powershell
python scripts/build_jev_occupation_exposure.py --dry-run
python scripts/build_jev_occupation_exposure.py --workers 4 --merge-sepe
python scripts/build_jev_occupation_exposure.py --workers 4 --merge-sepe --benchmark-us-direct
python scripts/build_jev_occupation_exposure.py --offline --merge-sepe
python scripts/build_jev_occupation_exposure.py --offline --from-snapshots --benchmark-us-direct
python scripts/validate_jev_outputs.py
```

An interrupted run resumes through request-content hashes. Model, state and
questions determine the cache key, so changed inputs or rubric invalidate the
relevant cached requests. A changed exposure value does not require reclassification
of nearest/weighted methods because it only affects deterministic calculation.
Offline mode normally requires the raw input sources and every cached API response.
`--from-snapshots` instead uses the tracked Spanish and US input snapshots, checked
against the previous manifest, and never downloads source files. The tracked
`jev_response_cache.zip` restores raw Jev responses into the ignored local cache
automatically, so a checkout can replay without an API key. Request hashes and
artifact SHA-256 sums expose changed inputs or responses. Missing or invalid
caches fail loudly. Add `--benchmark-us-direct` to reproduce an output directory
that contains the optional US benchmark.

Pilot examples must use a separate output directory:

```powershell
python scripts/build_jev_occupation_exposure.py --cno4 1211 2121 4301 7221 --output-dir data/cache/jev_pilot
python -m unittest discover -s tests -v
```

On the task host, `py -3` resolves to a missing interpreter. Execution used the
bundled Python 3.12 runtime with missing packages installed under the ignored
`.tmp_tests/jev_deps` directory. The pipeline itself has no host-specific paths.

## Outputs

`data/processed/jev/` contains intentionally versioned, compact research outputs:

- `occupation_estimates.csv`: one row per CNO4, both exposures, selected US match,
  direct exposure Score, maximum probability, margin, entropy, all tier probabilities, review flags,
  pinned model and rubric version. Load `cno4` as string to preserve leading zeros.
- `occupation_probabilities.csv.gz`: one row per CNO4, one probability column per
  US occupation; no category omitted. Columns join to `us_catalogue.csv` by SOC code.
- `spanish_inputs.csv`, `us_catalogue.csv`, `questions.json`: exact semantic inputs
  and rubric for inspection and reconstruction of every request.
- `direct_score_probabilities.csv`: all ten Score-level probabilities per CNO4.
- `request_audit.json`: request hashes, occupation, question IDs, resolved model,
  token use, cache status and unnormalized probability sums.
- `jev_response_cache.zip`: every **raw** successful Jev response used by the
  occupation outputs, content-addressed and included in Git for reproducibility.
- With `--benchmark-us-direct`, `us_direct_validation.csv`, its Score-level
  probabilities, request audit and summary compare predictions to US source values.
- `manifest.json`: source and artifact hashes, model, method, coverage, tier counts
  and merge validation. Token counts describe the successful cached responses;
  retries and diagnostic calls may add billable usage outside this manifest.

Working API response caches stay in ignored `data/cache/jev/`; their published
snapshot is the archive above. The optional SEPE merge is
written to ignored `data/processed/sepe_cno4_monthly_ai_exposure_jev.csv`. It
preserves the existing panel and embedding measures, checks every SEPE occupation
has exactly one classification, and preserves row count and order. An incomplete
merge cannot replace a previously complete output. No large panel is committed.

For analysis, either use that merged panel or join the occupation estimates on
four-character `cno4` with a many-to-one validation. Tier counts in the manifest
are occupation counts, not employment shares. Existing econometric scripts are
not automatically rerun or switched to a different exposure measure.
