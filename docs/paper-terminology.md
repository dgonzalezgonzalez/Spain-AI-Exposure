# Paper terminology and OB1 correction

The Prism paper uses **U.S.**, **DiD**, **CDiD** (continuous
difference-in-differences), and **SDiD** (synthetic difference-in-differences).
The first main-text uses introduce the full method names and acronyms. TWFE,
ATT, and OLS also receive definitions at their first uses. Full country names,
software/package names, filenames, citation keys, cross-reference labels, and
verbatim replication prompts retain their original spelling.

OB1 compares the Spanish CNO4 mapping with Anthropic's original occupational
observed-exposure ranking based on global Claude usage under the U.S. O*NET
taxonomy. Its caption and original-ranking column now say "global average";
the notes explain the distinction between the data's geography and taxonomy.
No occupation codes, rankings, or exposure values change. The four English
occupation translations already present in Prism are now in the notebook's
translation dictionary, so rerunning it preserves the coauthors' corrections.

## Sources and rendering

- `02_Descriptives_v1.ipynb`: OB1 generator rerun on the cached original
  Anthropic and Spanish mapped exposure data. All 20 rows' codes and scores
  were checked against the live Prism table.
- `lib/report_outputs.py` and `05_Output_tuning_v1.ipynb`: the production
  LaTeX writers call `lib/terminology.py`, and affected display templates use
  the canonical acronyms. This prevents future table generation from restoring
  inconsistent captions or notes.
- `scripts/build_paper_tables.py`: snapshot-based table captions and SDiD
  row label corrected. Statistical inputs and data keys are unchanged.
- `prism_terminology.patch`: the narrow main.tex edits to the current live
  coauthored paper; that full draft is maintained in Prism.
- `prism_generator_terminology.patch`: source-only changes against the supplied
  `last_scripts_code_only.zip`, including its newer `refinement_outputs.py`
  and `report_outputs.py`. Apply from the unpacked archive root with
  `git apply --unidiff-zero /path/to/prism_generator_terminology.patch`. It also adds the
  shared terminology formatter and corrects that archive's OB1 generator.

Several live imported tables contain specifications newer than this
repository's cached statistical outputs. Their numerical bodies were frozen
from the live paper and rerendered through the production terminology
formatter, rather than rerunning estimation with older inputs. Five changed
imported tables matched the resulting rendered sources exactly: alternative
exposure validation, CDiD alternatives, SDiD estimates, SDiD donor weights,
and SDiD weight diagnostics. Tracked older table snapshots were rerendered
through the same formatter without replacing their statistical contents.

To rerender a frozen table using this shared source formatter:

```powershell
py -3.12 scripts/normalize_paper_table_terminology.py input/table.tex --output-dir rendered
```

Validation: seven affected unit tests passed; the OB1 notebook cell was
executed; all changed live table numerical tokens were unchanged; main.tex
numbers, citations, paths, and references were preserved; Prism compiled and
the rendered OB1 was visually checked.
