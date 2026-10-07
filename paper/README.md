# Manuscript

`main.tex` contains the paper and online appendix; the Jev and task-bundling
sections are separate appendix inputs. `references.bib` is the bibliography and
`main.pdf` is the latest verified compiled paper.

Compile **root `main.tex` from the repository root**, rather than entering this
folder. The root entry point declares the document class and inputs `paper/main.tex`; all output and bibliography
paths resolve from that root. With a TeX distribution providing pdfLaTeX and BibTeX:

```sh
python code/build_paper.py
```

The helper resolves paths from the repository, runs BibTeX and enough LaTeX passes
to stabilize references, checks unresolved citations/labels, and copies the PDF
to `paper/main.pdf`. Build files and logs stay under ignored `logs/`. The analysis
runner is independent of TeX; rebuilding the paper does not rerun estimators.

The manuscript references retained outputs in `output/tables/` and
`output/figures/`. One deliberate editorial exception is
`sdid_estimates_manuscript.tex`, which preserves the authors' existing SDID table
wording. Its estimates match the generated SDID table. The methodology wording
discrepancy is documented in `../docs/validation_report.md` and `../docs/codebook.md`;
do not silently replace it with the generated table's revised note.

The active Prism project mirrors root `main.tex`, this folder, and the two output
folders. See `../docs/prism_sync.md` for its link and verification record. Full
historical Prism exports remain in dated local backups outside the repository.
For future synchronization, follow `AGENTS.md`: inspect co-author edits, back up
before cleanup, update matching paths, compile, export, and compare file hashes.
