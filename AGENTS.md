# Replication-package maintenance

This branch is the frozen replication release for `paper/`. The analysis entry point
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
platform coverage. Retained publication outputs are versioned in `output/tables/`
and `output/figures/`. Runtime caches and logs belong in ignored `data/work/`,
`logs/`, and `dist/`. Preserve recovery tags when replacing releases.

## Required repository structure

- `master.py`: one entry point for the retained analysis, runnable from the root
  or another working directory without editing machine-specific paths.
- `code/`: active preparation, estimation, rendering, acquisition, and packaging
  programs; `code/vendor/` contains frozen dependencies with their notices.
- `data/input/`: documented, checksummed inputs needed for the offline frozen run.
- `output/tables/`: the retained publication tables, versioned as LaTeX files.
- `output/figures/`: the retained publication figure panels, versioned as PNGs.
- `paper/`: current manuscript source, appendices, bibliography, and `main.pdf`.
  Root `main.tex` is a small compilation entry point that inputs `paper/main.tex`.
- `docs/`: data/code provenance, codebook, output map, software notices, actual
  validation evidence, and independent comparison targets in `docs/reference/`.
- `tests/`: focused regression tests. Intermediate data and rendering caches go
  in ignored `data/work/`; reports and compilation files go in ignored `logs/`;
  release archives go in ignored `dist/`.

Keep `output/` limited to `tables/` and `figures/`. Include actual publication
assets in Git and the release ZIP, not only empty directory placeholders. Do not
add historical drafts, unused analysis, installed environments, or caches to the
active package. Preserve useful historical work in Git history/recovery tags.

## Replication documentation and checks

Maintain the README sections for the paper overview, data availability and
provenance, software requirements, computational resources/runtime, program
descriptions, execution instructions, output-to-program mapping, and references.
Document data access restrictions and reuse terms separately from the MIT
author-code license. Record exact data vintages, hashes, package versions, seeds,
bootstrap/placebo counts, and any proprietary software required. Do not claim
fresh installations or platforms were tested without evidence.

Keep analysis offline and portable using the frozen inputs. Provide cached or
resumable optional acquisition separately. The master must export only mapped
publication assets and compare numbers and figure pixels with independent targets;
never substitute target files for computed results. Regenerate affected outputs
after substantive changes, run relevant tests, record checks and discrepancies,
and rebuild the release ZIP. Path/packaging changes need routing, integrity, and
archive checks; they do not require rerunning expensive estimators.

Compile the manuscript after source/path/output changes and update `paper/main.pdf`
only after successful compilation. Keep all figures, tables, bibliography entries,
citations, cross-references, and appendix inputs resolvable from root `main.tex`.
Do not silently rewrite manuscript wording or methodological specifications. The
SDID table's retained manuscript wording is in `paper/sdid_estimates_manuscript.tex`;
its documented discrepancy with the generated table remains deliberate until the
authors authorize a wording change.

## Mirror manuscript files in Prism

When manuscript or publication outputs change, synchronize the manuscript subset
of the repository with Prism: root `main.tex`, `paper/`, `output/tables/`, and
`output/figures/`. Use the same relative paths and file contents in both places.
Prism does not need analysis code, datasets, environments, historical drafts, or
independent validation targets. Never reintroduce `uploads/` paths into active TeX.

If Prism is not accessible, ask the user to open the correct project in a Codex
browser tab (or another browser available to the agent). Continue independent local
work while waiting. Do not claim Prism was updated when only Git changed, and do
not send messages or invitations to collaborators without explicit authorization.

Before synchronizing, inspect the latest Prism sources and the Git working tree
for co-author edits; reconcile changes rather than overwriting unseen work. Before
cleanup, export the complete Prism project ZIP and current PDF to a dated local
backup outside the active project; verify ZIP integrity and record its location
and hashes. Trace active TeX dependencies before identifying unused files.

Upload/update the retained files and paths first. Compile successfully in Prism,
inspect the PDF, and compare the exported project files with Git. Only then remove
backed-up, unused drafts and duplicate assets, subject to the browser tool's
confirmation rules for deletion. Preserve project ownership and collaborator access.
Keep only the mirrored manuscript subset in the active Prism project. Record the
project link, sync date, file comparison, compilation result, and any unresolved
differences in `docs/`; keep full backups and scratch logs outside the release ZIP.

When publishing, verify that remote Git contains the actual tables, figures,
manuscript sources, and current PDF, then publish the updated ZIP with its SHA-256
checksum. Confirm the browser visibly shows the synchronized, compiling project.
