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
6. `06_Calibration_aggregate_results.py`: micro calibration that applies the estimated TWFE unemployment gradients to each CNO4 occupation's observed AI exposure and aggregates the implied unemployment gap to the national monthly level.

Use `--replication-step prepare` or another named step for partial runs. The
default `500` SDID and `1000` ContDID repetitions are production settings;
smoke tests should pass smaller values explicitly. The calibration step assumes
that the prepared panel from step 1 and the TWFE coefficient CSVs from step 3
already exist in `runtime/`.

## Tracked Artifacts

`estimates_results_report_v1.tex` is the current empirical-results manuscript,
and `descriptive.tex` is its descriptive validation companion. The frozen
publication figures and table fragments are under `figuresNtables/`. Raw data,
prepared panels, logs, and estimator intermediates stay in the ignored runtime
because the ZIP contained more than 1 GB of generated/source data.
