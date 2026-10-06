# Spain/global Claude usage validation

Section 2.2.3 in the Prism project `Spain-AI-exposure` now compares Spain with
the global usage distribution. Anthropic's observed exposure measure uses
Claude usage mapped to the US O*NET taxonomy; the taxonomy does not make the
usage sample specific to the US labor market. The introductory phrase
"measure developed by Anthropic for US occupations" was also changed to
"measure developed by Anthropic for O*NET occupations". Other references to
US labor-market studies and US occupational classifications were preserved.

## Source and construction

- Source: Anthropic Economic Index release of 26 June 2026,
  `aei_claude_ai_2026-06-26.csv`.
- Window: 1 May 2026 (inclusive) to 1 June 2026 (exclusive).
- Spanish rows: `geo_id == "ESP"`, `geo_level == "country"`.
- Global rows: `geo_id == "GLOBAL"`, `geo_level == "global"`.
- Both: `category_name == "soc_occupation"`, `hierarchy_level == 1`,
  `metric_id == "pct"`.
- The global average is Anthropic's pooled worldwide usage aggregate, not an
  unweighted average of country percentages. Published percentages are used
  without renormalization. Missing groups raise an error in the shared parser.

[Anthropic's release documentation](https://huggingface.co/datasets/Anthropic/EconomicIndex/blob/main/release_2026_06_26/data_documentation.md)
defines the global geography, occupational categories, and percentage metric.
[Massenkoff and McCrory (2026)](https://www.anthropic.com/research/labor-market-impacts)
describe the observed exposure methodology and its O*NET task inputs.

## Reproduction and checks

The two figure cells in `analysis/paper_replication/02_Descriptives_v1.ipynb`
produce the paper's figures and comparison CSV, retaining their original
layout. Figure 1 orders groups by descending Spanish usage, with the largest
share at the top and a stable SOC-code tie-break; global bars remain paired
with the same groups. Both cells were rerun against cached inputs. The histogram's 502
Spanish occupation scores and bin counts were verified against the staged
replication data and are unchanged; only its O*NET label and filename changed.

The operational `scripts/build_claude_country_job_usage_figure.py` uses the same
global parser and retains its existing mirrored-bar layout. Run:

```powershell
py -3.12 scripts/build_claude_country_job_usage_figure.py --date-start 2026-05-01
py -3.12 -m unittest discover -s tests -p "test_anthropic_country_usage.py" -v
py -3.12 -m unittest discover -s tests -p "test_paper_outputs_manifest.py" -v
```

The notebook and shared parser were checked to agree for every one of the 22
major groups. Computer and mathematical occupations account for 23.92% of
Spanish usage and 23.80% of global usage. Regression tests distinguish global
rows from US rows and reject missing global groups.

`analysis/paper_replication/validation_prism.tex` records the corrected Prism
section. The two regenerated PNGs are in `figuresNtables/` and uploaded to the
Prism project's `uploads/prism-uploads/` folder.
