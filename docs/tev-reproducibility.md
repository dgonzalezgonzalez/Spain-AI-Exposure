# Local TEV experiment

The frozen input snapshots are `data/processed/jev/spanish_inputs.csv` (502
CNO4 occupations) and `us_catalogue.csv` (756 O*NET occupations). Jev outputs
are retained separately; TEV does not inherit their probabilities.

## Runtime

Use Ollama 0.35.1 and the exact TEV weights recorded in `runtime.json`.
Start `scripts/start_tev_ollama.ps1`, then create the local model alias:

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11435'
ollama create tev-occupation-reproducible:4b -f config/tev-reproducible.Modelfile
py -3 scripts/audit_tev_repeatability.py
py -3 scripts/build_tev_occupation_exposure.py
py -3 scripts/run_occupation_paper_checks.py --model-family tev
```

The isolated server uses Vulkan on the Intel Iris Xe, one request at a time,
all model layers on GPU, F16 KV cache, and flash attention disabled. Each
uncached request resets the model to remove dependence on earlier prompt prefixes. Model
context, batch size, CPU threads, seed, temperature, and other generation
parameters are pinned in the Modelfile. The `/v1/systemone` endpoint ignores
request-level generation options: it reports candidate probabilities computed
from logits. Sampled tokens do not enter those reported probabilities.

Fresh warm and cold-reload probes must agree bit for bit. The initial Q8 KV
cache/flash-attention configuration failed a cold-reload check and was rejected.
The F16 configuration passed the small stored finite probe, but the larger
production-batch audit recorded differing fresh answers. It is not validated
as deterministic. This is evidence on the
recorded machine and software, not a guarantee of arbitrary future hardware or
driver behavior, nor a proof about infinitely many fresh calls.

Exact repeated analysis uses the cache:

```powershell
py -3 scripts/build_tev_occupation_exposure.py --offline
```

Every request records its ordered candidate schema, occupation state, pinned
runtime, raw response, and checksum. Cache identity includes candidate order.
Only complete validated responses are saved. Interrupted runs resume from
those responses; offline cache misses fail instead of invoking inference.
The response archive and probability tables preserve the original experiment.
Thus subsequent cached runs reproduce the frozen judgments without asking the
model to recompute them.

## Measures and checks

TEV's Choice primitive admits fewer categories than the O*NET catalogue.
An exhaustive SOC-prefix hierarchy evaluates every branch without pruning;
products of conditional probabilities give probabilities for all 756 leaves.
Nearest exposure takes the global highest-probability leaf. Weighted exposure
averages all O*NET exposures by those probabilities. Direct exposure is the
expected ten-level Score divided by nine. Tiers select the highest-probability
of the three original Garicano definitions; ties choose the lowest number.

The paper currently uses the frozen Jev classifications. The local GPU pilot
was too slow to meet the two-hour budget; no complete TEV occupation results
are claimed. The reset-before-request configuration requires a fresh audit
before any future production run.

Exposure checks change only treatment. Tier checks jointly estimate tier 1
and tier 2 indicators against the omitted tier 3. The coauthor Stata
programs retain the adjustment/later periods, fixed effects, clustering, and
event windows. Preferred specifications include CNO1-by-year-month fixed effects.
The tier table has one panel with four coefficients and six columns.
Estimator outputs are frozen alongside input and source checksums.

`scripts/build_model_appendices.py --model-family tev` requires complete results, creates separate O.D. and
O.E. fragments, and an internal `shareout_tev_results.tex`. In Prism, insert the
O.D. fragment before the new O.E. section, then insert the O.E. fragment before
Occupational Feminization. The manuscript's automatic appendix numbering moves
Feminization to O.F. Add `\usepackage{fvextra}` for the verbatim prompts.
Upload the fragments' figures and tables under `uploads/figuresNtables`.
Internal combined shareout TeX/PDF files must remain uncommitted.
