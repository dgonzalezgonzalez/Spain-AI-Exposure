# SEPE Supplementary Data

`sepe_provider_missing_breakdowns.csv` is the normalized, versioned extract from
`ocup prov año 22.xlsx`, supplied directly by the SEPE Observatorio in July 2026.
The original 24.8 MB workbook remains under `data/raw/sepe/supplemental/` and is
excluded from Git with the rest of `data/raw/`.

SEPE explained that omitted categories and workbook cells marked with a hyphen
represent zero observations. The extract restores gender, age, and province
breakdowns for the three September 2022 reports that the public site exposed as
totals only: CNO4 `2220`, `2230`, and `2323`.

Regenerate the extract with:

```powershell
py -3 scripts/build_sepe_provider_supplement.py data/raw/sepe/supplemental/ocup_prov_2022.xlsx
```

The main SEPE build automatically loads this file, adds only wholly absent
dimensions, and checks their `contratos` and `parados` sums against each report's
published total. Existing observed breakdowns are never overwritten.
