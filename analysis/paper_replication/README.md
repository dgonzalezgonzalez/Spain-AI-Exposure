# V1 Paper Replication Package

This directory contains the latest paper-analysis package received from Nico in
the WhatsApp group "The X-files". It is the current analysis/manuscript
version, not a separate project.

## Production Order

Run the package through the repository entry point:

```powershell
py -3 main.py --analysis-only --run-paper-replication `
  --stata-exe "C:\Program Files\StataNow19\StataMP-64.exe" `
  --rscript "C:\Users\dgonzalez\AppData\Local\Programs\R\R-4.5.2\bin\Rscript.exe"
```

The wrapper stages the existing SEPE monthly output, EPA 65134, Anthropic
occupation data, and small paper inputs into the ignored `runtime/` directory.
It then runs:

1. `01_Preparation_v1.ipynb`: audited age/province backcasts and estimation panels.
2. `02_Descriptives_v1.ipynb`: descriptive figures and validation tables.
3. `03_Estimates_TWFE_SDID_HonestDID_v1.do`: Stata estimates and diagnostics.
4. `04_Estimates_contDID_v1.R`: continuous-treatment alternatives.
5. `05_Output_tuning_v1.ipynb`: publication figures, tables, and validation.

The preparation stage also merges the frozen Jev occupation estimates into
`est_total_cno4_jev.csv`. The estimates stage runs the baseline models and then
a focused Jev O.D. pass. The tuning stage writes the baseline-plus-three-Jev
robustness table, six event-study panels, and an occupation-level Spearman
correlation heatmap. The BLS AI exposure workbook
(`data_sources/bls_ai_exposure_categories_2025_35.xlsx`) and the LM AIOE
workbook are bundled as paper inputs. The BLS file is the 2025--35
[Employment Projections release](https://www.bls.gov/emp/publications/ai-exposure-categories.htm).
If it is unavailable in another checkout, its row and column are left blank
and identified as pending; the matrix updates when the workbook is restored
or placed in `data/raw/`.

Use `--replication-step prepare` or another named step for partial runs. The
default `500` SDID and `1000` ContDID repetitions are production settings;
smoke tests should pass smaller values explicitly.

## Tracked Artifacts

`estimates_results_report_v1.tex` is the current empirical-results manuscript,
and `descriptive.tex` is its descriptive validation companion. The frozen
publication figures and table fragments are under `figuresNtables/`. Raw data,
prepared panels, logs, and estimator intermediates stay in the ignored runtime
because the ZIP contained more than 1 GB of generated/source data.
