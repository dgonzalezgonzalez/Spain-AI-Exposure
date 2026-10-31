# Local TEV replication protocol

This experimental branch starts at main commit `c855fd9`. It preserves the
release structure and econometric specifications. Original Jev inputs and
independent manuscript comparison targets remain unchanged. TEV outputs live
in `data/input/tev/`; working responses and logs live in ignored `data/work/`.
Legacy `jev` identifiers in filenames and estimator columns are compatibility
names, not claims that TEV outputs came from Jev.

## Software and hardware

Fresh inference requires Ollama **0.40.13** and `tev1:4b-q4_K_M`, a 2.8 GB
download. The validated tier pilot used an Intel i7-1165G7, 16 GB RAM, Windows
x64, CPU-only inference, approximately 3.9 GB loaded model memory. Its 23-second
median tier latency does not estimate the full 756-category matching runtime.
Python, Stata, R, and TeX requirements otherwise follow the release README.
No TypeSafe or cloud inference credentials are used by TEV acquisition.

```powershell
ollama pull tev1:4b-q4_K_M
ollama create tev-replication:4b-q4-cpu4 -f code/acquisition/tev.Modelfile
python code/acquisition/run_tev.py --audit --limit 1
python code/acquisition/run_tev.py
```

The acquisition program starts and terminates its own hidden Ollama server on
port 11436; an occupied port fails without touching the other server. Version,
full weight digests, executable and CPU backend binary hashes, environment,
context, batch size and thread count are pinned in
`code/acquisition/tev-runtime.json`. Context is 8192, batch 128, four CPU
threads, zero GPU layers, F16 KV cache, flash attention disabled, no cloud,
one API request at a time. Each uncached request unloads the model first.
Generation settings are also pinned, but System One scores candidate logits;
temperature zero and a seed alone cannot guarantee identical probabilities.
Production-shape cold repeatability probes must pass before acquisition.

Repeatability is an empirical property of the pinned setup and tested requests,
not a guarantee for every possible input or future environment. Exact published
replication uses the archived responses. Fresh inference after binary or weight
changes needs a separate audit and new provenance rather than silently reusing
the experiment's identity.

## One occupation workflow

The workflow visits each of the 502 occupations once and caches every validated
response immediately. An interruption resumes at request granularity. Completed
occupation records are also checkpointed. Tier and direct exposure questions
share only semantic occupation evidence, excluding proposed matches and realized
exposure values. The original direct-exposure rubric and its reference examples
are unchanged. Screening receives the original proposed baseline match.

At the author's request, the faster experiment restricts each occupation to its
24 highest cosine-ranked US candidates (stable ordering from the frozen embedding
vectors). This fits one Choice question. Its probabilities are conditional on the
shortlist, and the weighted exposure averages those 24 candidates rather than all
756 occupations. Excluded categories are recorded as outside the support, not
independently estimated zero-probability matches. The highest-probability match
is also a shortlist selection. This is an intentional methodological difference
from the Jev release, and the paper must label it explicitly.

All 502 occupations require exactly two requests: tier/direct exposure over
semantic evidence, followed by matching and the original two mismatch/heterogeneity
questions over semantic evidence plus the proposed baseline match. No model answer
is exposed to another question. The schema includes descriptions of all 24
candidates without truncation; the largest request is 16,345 UTF-8 bytes (CNO 6110),
below both the conservative byte budget and the API limit. Requests remain
sequential under the pinned CPU runtime.

The `wrong_match >= 0.5` gate is unchanged. If flagged, the occupation uses the
same already-computed shortlist match for the corrected crosswalk; otherwise it
retains the baseline match. No extra GPT-OSS request or second TEV matching pass
is needed. This replaces both the Jev screen and the main release's GPT-OSS
verifier with local decisions. The gate and match questions share a request, so
the screen also sees the shortlist schema. TEV does not generate free-text
rationales: limitations and residual mismatches require the separate review.

The complete resulting crosswalk must be reviewed anew. No original manual
override is applied automatically. `author_review.json` must enumerate all
reviewed occupation codes and explicit corrected codes with duty-based reasons;
the analysis refuses incomplete review. All 502 occupations retain coverage,
including documented proxies where no exact US equivalent exists.

## Frozen replay and analysis

After acquisition, review, and input-manifest updates:

```powershell
python master.py
python code/build_paper.py
python code/build_archive.py
```

The master replays the raw TEV archive offline and checks the reconstructed
occupation estimates against the frozen TEV tables. It reruns preparation,
descriptives, TWFE, SDID (500 placebo replications), TEV exposure and tier DiD,
edge-case regressions, tier mediation, ContDID (1000 bootstraps), rendering, and
in-text statistics. Seeds and estimator specifications are retained. Independent
Jev references remain comparison evidence: model-dependent changes must be
reported as differences and independently checked, rather than forced to match
Jev or replaced with generated reference files.

The TEV manuscript belongs to this branch. The existing Prism publication
project remains the Jev version; it must not be overwritten by this experiment.

## Completed acquisition and review, 31 October 2026

The production acquisition completed 502 occupations and 1,004 unique requests in 44,245.422 seconds (12.29 hours). The exact raw-response archive passes CRC and every request/runtime/content identity check. All source and artifact hashes pass. The 502-by-756 matrix sums to one within 1e-10; only each frozen 24-code shortlist is supported. All ten-level score distributions sum to one. Full offline replay reproduces all 502 estimate records within absolute tolerance 1e-12 and makes no live inference request.

All 502 crosswalks were inspected by the Codex assistant, including unflagged cases. The frozen review has 56 explicit duty-based corrections and per-code retention/proxy notes. This is not independent human adjudication. TEV flags 166 baseline matches; 123 reviewed final codes differ from baseline. See `manual_edgecases.md` and `tev_comparison.md`. All retained econometric stages have completed at production counts. The 88 publication assets pass the branch checks: unchanged assets compare with independent Jev targets; changed model results pass independent coefficient and rank-correlation calculations. The separate manuscript uses actual new coefficients and tier paths. Detailed checks and the bounded SDID reference discrepancy are in validation_report.md.
