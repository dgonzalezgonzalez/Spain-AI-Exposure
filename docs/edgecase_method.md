# Complete TEV-reviewed occupational crosswalk

This experimental branch starts from the frozen cosine-nearest crosswalk and replaces the Jev screen and separate cloud verifier with local TEV. Each occupation receives a fixed top-24 cosine shortlist. Matching, baseline mismatch and heterogeneity are grouped in one request; tier and direct exposure are grouped separately using semantic evidence only. There are two requests per occupation and no second matching pass.

The original `wrong_match >= 0.5` gate is retained. TEV flags 166 of 502 baseline matches. Flagged occupations use the already acquired shortlist argmax; unflagged occupations initially retain baseline. Heterogeneity is diagnostic and does not change the gate. Raw weighted exposure is conditional on the shortlist, not a full-catalogue probability average. Screening sees the same shortlist schema, an additional difference from the original workflow.

The Codex assistant inspected all 502 resulting crosswalks against the frozen Spanish definitions/tasks/examples/exclusions and actual available US descriptions. The new review records 56 explicit corrections and reasoned retention notes for every other code. No old override list was applied automatically. This is assistant-led source inspection, not independent human adjudication or accuracy ground truth. See `manual_edgecases.md` and the complete frozen `data/input/tev/author_review.json`.

Final exposure covers all 502 occupations; 123 final codes differ from the baseline. Published Anthropic exposure values are joined after selecting codes. The review does not change raw model responses, probabilities or the separate nearest/weighted measures. Matching and review choices do not use exposure magnitudes or econometric results.

Catalogue gaps and mixed occupation groups remain material. Some retained mappings are qualified or severely limited proxies, including raw-hide tanning, paper/pulp manufacture, electrical/electronic assembly and wild fishing. The complete review documents these rather than inventing categories or occupation shares. No missing value is converted to zero; valid published zero exposures remain zero.

Original Jev/GPT-OSS archives, source code and independent manuscript targets remain unchanged for comparison. The original method used 216 flagged occupations, a separate 30-candidate GPT-OSS verifier and 13 author corrections. Differences in correction counts are not accuracy statistics. Changes in results combine model, shortlist, screening/verification architecture and review differences.

Estimator specifications, fixed seeds, 500 SDID placebos and 1,000 continuous-DiD bootstraps are retained. Legacy `jev` variable/filename identifiers only preserve estimator interfaces. Model-dependent estimates must be independently checked, with differences from Jev reported honestly; the original publication targets must never be replaced with generated TEV outputs.
