from __future__ import annotations

from pathlib import Path

import pandas as pd


BLS_CATEGORY_ORDER = {
    "Low": 1,
    "Moderate": 2,
    "High": 3,
    "Very high": 4,
}


def _soc6(series: pd.Series) -> pd.Series:
    return series.astype("string").str.replace(r"\D", "", regex=True).str.zfill(6)


def prepare_alternative_exposure_inputs(
    project_root: str | Path,
    audit_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Map BLS and capability-based US exposure measures to Spanish CNO4."""

    root = Path(project_root)
    raw_dir = root / "data" / "raw"
    audit_dir = Path(audit_dir) if audit_dir is not None else root / "intermediate"
    audit_dir.mkdir(parents=True, exist_ok=True)

    crosswalk = pd.read_csv(
        raw_dir / "spanish_occupation_matches_cosine_nearest.csv",
        dtype={"CNO4": str, "anthropic_occ_code": str},
    )
    crosswalk = crosswalk[["CNO4", "anthropic_occ_code", "anthropic_title"]].copy()
    crosswalk["cno4"] = crosswalk["CNO4"].str.zfill(4)
    crosswalk["soc6"] = _soc6(crosswalk["anthropic_occ_code"])
    crosswalk = crosswalk.drop(columns="CNO4")

    bls = pd.read_excel(
        raw_dir / "bls_ai_exposure_categories_2025_35.xlsx",
        sheet_name="AI Exposure Categories",
        skiprows=1,
        dtype=str,
    )
    bls["soc6"] = _soc6(bls["2025 National Employment Matrix code"])
    bls = bls.rename(
        columns={
            "2025 National Employment Matrix title": "bls_occupation_title",
            "Relative AI exposure": "bls_ai_category",
        }
    )[["soc6", "bls_occupation_title", "bls_ai_category"]].drop_duplicates("soc6")

    capability = pd.read_excel(
        raw_dir / "felten_raj_seamans_language_modeling_aioe.xlsx",
        sheet_name="LM AIOE",
        dtype={"SOC Code": str},
    )
    capability["soc6"] = _soc6(capability["SOC Code"])
    capability = capability.rename(
        columns={
            "Occupation Title": "frs_occupation_title",
            "Language Modeling AIOE": "frs_lm_aioe",
        }
    )[["soc6", "frs_occupation_title", "frs_lm_aioe"]].drop_duplicates("soc6")

    mapped = crosswalk.merge(bls, on="soc6", how="left", validate="many_to_one")
    mapped = mapped.merge(capability, on="soc6", how="left", validate="many_to_one")
    mapped["bls_ai_category_code"] = mapped["bls_ai_category"].map(BLS_CATEGORY_ORDER)
    mapped["frs_lm_aioe"] = pd.to_numeric(mapped["frs_lm_aioe"], errors="coerce")

    # Rank scaling makes the alternative slope interpretable as a change of ten
    # percentile points in the capability-based occupational exposure ranking.
    mapped["frs_lm_percentile"] = mapped["frs_lm_aioe"].rank(
        method="average", pct=True
    )
    mapped["frs_lm_percentile_10pp"] = mapped["frs_lm_percentile"] / 0.10

    mapped.to_csv(audit_dir / "alternative_exposure_cno4_crosswalk_v1.csv", index=False)

    validation = pd.DataFrame(
        [{
            "cno4_occupations": mapped["cno4"].nunique(),
            "bls_matched_cno4": mapped.loc[
                mapped["bls_ai_category"].notna(), "cno4"
            ].nunique(),
            "frs_lm_matched_cno4": mapped.loc[
                mapped["frs_lm_aioe"].notna(), "cno4"
            ].nunique(),
            "bls_low": int((mapped["bls_ai_category"] == "Low").sum()),
            "bls_moderate": int((mapped["bls_ai_category"] == "Moderate").sum()),
            "bls_high": int((mapped["bls_ai_category"] == "High").sum()),
            "bls_very_high": int((mapped["bls_ai_category"] == "Very high").sum()),
        }]
    )
    validation.to_csv(audit_dir / "alternative_exposure_validation_v1.csv", index=False)

    return mapped[
        [
            "cno4",
            "soc6",
            "bls_ai_category",
            "bls_ai_category_code",
            "frs_lm_aioe",
            "frs_lm_percentile",
            "frs_lm_percentile_10pp",
        ]
    ]
