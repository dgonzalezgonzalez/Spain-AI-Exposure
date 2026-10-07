# Replication-package maintenance

This branch is the frozen replication release for `docs/paper/`. The entry point
is `master.py`; active programs live in `code/`. Inputs are versioned under
`data/input/`, independent paper targets under `docs/reference/`. Never replace
reference files with generated results.

Keep changes limited to retained manuscript results. Update `docs/output_map.csv`
and `docs/paper_outputs.json` when the manuscript changes. Replace input hashes
only for intentional, documented source revisions. Do not add credentials,
private identifiers, proprietary executables, or generated runtime caches.

Use Python 3, four-space indentation, snake_case, and pathlib. Preserve estimator
specifications, fixed seeds, and publication repetition counts unless the user
explicitly requests methodological changes. Keep exploratory code on branches.

Run `python -m unittest discover -s tests -v` for relevant changes. Compare
numerical results and figures before releases; record actual checks, software,
timings, and discrepancies in `docs/validation_report.md`. Do not claim untested
platform coverage. Runtime files belong in ignored `data/work/`,
`output/tables/` and `output/figures/`, and `dist/`. Preserve recovery tags when replacing releases.
