# Source cell 2

from pathlib import Path
import os
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path.cwd().resolve()
while PROJECT_ROOT != PROJECT_ROOT.parent and not (PROJECT_ROOT / "data").is_dir():
    PROJECT_ROOT = PROJECT_ROOT.parent
if not (PROJECT_ROOT / "data").is_dir():
    raise FileNotFoundError("Run this notebook from the replication-package folder.")

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PREPARED_DIR = PROJECT_ROOT / "data" / "prepared"
INTERMEDIATE_DIR = PROJECT_ROOT / "intermediate"
FINAL_DIR = PROJECT_ROOT / "rendered"
LOGS_DIR = PROJECT_ROOT / "logs"

for directory in [PREPARED_DIR, INTERMEDIATE_DIR, FINAL_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

HIGH_CUTOFF = 0.1169
EVENT_PERIOD = pd.Timestamp("2022-11-01")
EVENT_MIN, EVENT_MAX = -21, 40

INPUT_DIR = PREPARED_DIR
TABLES_DIR = INTERMEDIATE_DIR
PROCESSED_DIR = RAW_DIR

print("Replication root:", PROJECT_ROOT)
print("Prepared inputs:", PREPARED_DIR)
print("Intermediate audits:", INTERMEDIATE_DIR)


# Source cell 4
RAW_SEPE = RAW_DIR / "sepe_cno4_monthly_ai_exposure.csv"
raw = pd.read_csv(RAW_SEPE, dtype=str)
raw.columns = [column.lower() for column in raw.columns]

numeric_columns = [
    "parados", "contratos", "observed_exposure_cosine_nearest",
    "observed_exposure_cosine_weight", "observed_exposure_cosine_weighted",
    ]
for column in numeric_columns:
    if column in raw:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")

raw["cno4"] = raw["cno4"].astype(str).str.strip().str.zfill(4)

from lib.sepe_age_backcast import (
    append_reconstructed_age_rows,
    reconstruct_may_2024_age_cells,
    reconstruction_missingness,
)

AGE_BACKCAST_CACHE = RAW_DIR / "sepe_cno4_age_may2024_backcast_from_june.csv"
refresh_age_backcast = os.getenv("REFRESH_SEPE_MAY2024_AGE", "0") == "1"
age_backcast_audit = reconstruct_may_2024_age_cells(
    raw,
    AGE_BACKCAST_CACHE,
    refresh=refresh_age_backcast,
    workers=8,
)
age_missingness, age3_missingness = reconstruction_missingness(age_backcast_audit)
age_backcast_audit.to_csv(
    TABLES_DIR / "sepe_may2024_age_backcast_cell_audit_v1.csv", index=False
)
age_missingness.to_csv(
    TABLES_DIR / "sepe_may2024_age_backcast_missingness_v1.csv", index=False
)
age3_missingness.to_csv(
    TABLES_DIR / "sepe_may2024_age3_backcast_missingness_v1.csv", index=False
)
raw = append_reconstructed_age_rows(raw, age_backcast_audit)

print(age_missingness)
print(age3_missingness)

from lib.sepe_province_backcast import (
    append_reconstructed_province_rows,
    reconstruct_may_2024_province_cells,
    reconstruction_missingness as province_reconstruction_missingness,
)

PROVINCE_BACKCAST_CACHE = RAW_DIR / "sepe_cno4_province_may2024_backcast_from_june.csv"
refresh_province_backcast = os.getenv("REFRESH_SEPE_MAY2024_PROVINCE", "0") == "1"
province_backcast_audit = reconstruct_may_2024_province_cells(
    raw,
    PROVINCE_BACKCAST_CACHE,
    refresh=refresh_province_backcast,
    workers=8,
)
province_missingness, province_missingness_overall = province_reconstruction_missingness(
    province_backcast_audit
)
province_backcast_audit.to_csv(
    TABLES_DIR / "sepe_may2024_province_backcast_cell_audit_v1.csv", index=False
)
province_missingness.to_csv(
    TABLES_DIR / "sepe_may2024_province_backcast_missingness_v1.csv", index=False
)
province_missingness_overall.to_csv(
    TABLES_DIR / "sepe_may2024_province_backcast_missingness_overall_v1.csv", index=False
)
raw = append_reconstructed_province_rows(raw, province_backcast_audit)
print(province_missingness_overall)

raw["cno4"] = raw["cno4"].astype(str).str.strip().str.zfill(4)
raw = raw[raw["cno4"].str.fullmatch(r"\d{4}", na=False)].copy()
raw["period"] = raw["period"].astype(str).str.strip()
raw["period_date"] = pd.to_datetime(raw["period"] + "-01", errors="coerce")
raw["ym_stata"] = (raw["period_date"].dt.year - 1960) * 12 + raw["period_date"].dt.month - 1
raw["ym_index"] = raw["period_date"].rank(method="dense").astype("Int64")
raw["cno2"] = raw["cno4"].str[:2]
raw["cno1d"] = raw["cno4"].str[:1]

raw = raw.sort_values(["dimension", "category", "gender", "cno4", "period_date"]).copy()
rolling_keys = ["dimension", "category", "gender", "cno4"]
raw["contratos_12m"] = (
    raw.groupby(rolling_keys, dropna=False)["contratos"]
    .transform(lambda values: values.rolling(12, min_periods=12).sum())
)
raw["ln_contratos_12m"] = np.where(
    raw["contratos_12m"] > 0, np.log(raw["contratos_12m"]), np.nan
)

raw["exposure_nearest"] = raw["observed_exposure_cosine_nearest"]
weighted_source = (
    "observed_exposure_cosine_weighted"
    if "observed_exposure_cosine_weighted" in raw
    else "observed_exposure_cosine_weight"
)
raw["exposure_weighted"] = raw[weighted_source]

for source, target in [
    ("exposure_nearest", "exposure_10pp"),
    ("exposure_weighted", "exposure_weighted_10pp"),
]:
    raw[target] = raw[source] / 0.10

# Keep the Spanish occupational match fixed while changing the US exposure
# concept. BLS supplies four exposure categories; Felten--Raj--Seamans supply
# a capability-based language-model score, scaled below by percentile rank.
from lib.alternative_exposure import prepare_alternative_exposure_inputs

alternative_exposure = prepare_alternative_exposure_inputs(
    PROJECT_ROOT, audit_dir=INTERMEDIATE_DIR
)
raw = raw.merge(alternative_exposure, on="cno4", how="left", validate="many_to_one")

raw["ln_parados"] = np.where(raw["parados"] > 0, np.log(raw["parados"]), np.nan)
raw["ln_contratos"] = np.where(raw["contratos"] > 0, np.log(raw["contratos"]), np.nan)
raw["ln_parados_p1"] = np.log(raw["parados"].fillna(0) + 1)
raw["ln_contratos_p1"] = np.log(raw["contratos"].fillna(0) + 1)
raw["parados_contratos"] = np.where(
    raw["contratos"] > 0, raw["parados"] / raw["contratos"], np.nan
)

event_month_stata = (2022 - 1960) * 12 + 11 - 1
raw["event_time_nov2022"] = raw["ym_stata"] - event_month_stata
raw["post_nov2022"] = (raw["period_date"] >= EVENT_PERIOD).astype(int)

total_mask = (
    raw["dimension"].str.lower().eq("total")
    & raw["category"].str.lower().eq("total")
    & raw["gender"].str.lower().eq("total")
)
occupation_exposure = (
    raw.loc[total_mask, ["cno4", "exposure_nearest"]]
    .drop_duplicates("cno4")
    .sort_values("cno4")
)
positive_exposure = occupation_exposure.loc[
    occupation_exposure["exposure_nearest"] > 0, "exposure_nearest"
]
q75_all = occupation_exposure["exposure_nearest"].quantile(0.75)
q75_positive = positive_exposure.quantile(0.75)

raw["treat_high"] = (raw["exposure_nearest"] > HIGH_CUTOFF).astype(int)
raw["treat_zero"] = (raw["exposure_nearest"] == 0).astype(int)
raw["sdid_donor"] = (raw["exposure_nearest"] <= HIGH_CUTOFF).astype(int)
raw["binary_sample"] = 1
raw["did_post"] = raw["treat_high"] * raw["post_nov2022"]

base_columns = [
    "period", "ym_stata", "ym_index", "event_time_nov2022",
    "cno4", "cno2", "cno1d", "parados", "contratos", "contratos_12m",
    "ln_parados", "ln_contratos", "ln_contratos_12m",
    "ln_parados_p1", "ln_contratos_p1",
    "parados_contratos", "exposure_nearest", "exposure_10pp",
    "exposure_weighted", "exposure_weighted_10pp",
    "bls_ai_category", "bls_ai_category_code",
    "frs_lm_aioe", "frs_lm_percentile", "frs_lm_percentile_10pp",
    "post_nov2022", "treat_high", "treat_zero", "sdid_donor",
    "binary_sample", "did_post",
]

def write_panel(frame, filename, unit_columns, extra_columns=None):
    extra_columns = extra_columns or []
    alternative_columns = [
        "bls_ai_category", "bls_ai_category_code", "frs_lm_aioe",
        "frs_lm_percentile", "frs_lm_percentile_10pp",
    ]
    missing_alternatives = [
        column for column in alternative_columns if column not in frame.columns
    ]
    if missing_alternatives:
        frame = frame.merge(
            alternative_exposure[["cno4"] + missing_alternatives],
            on="cno4",
            how="left",
            validate="many_to_one",
        )
    output = frame[base_columns + extra_columns].copy()
    output["unit"] = frame[unit_columns].astype(str).agg("__".join, axis=1)
    output = output[["unit"] + base_columns + extra_columns]
    path = INPUT_DIR / filename
    output.to_csv(path, index=False)
    return {
        "file": filename,
        "rows": len(output),
        "units": output["unit"].nunique(),
        "periods": output["period"].nunique(),
    }

created = []
total = raw.loc[total_mask].copy()
created.append(write_panel(total, "est_total_cno4.csv", ["cno4"]))

province = raw.loc[raw["dimension"].str.lower().eq("province")].copy()
province["province"] = province["category"]
created.append(
    write_panel(
        province, "est_province_cno4.csv", ["province", "cno4"],
        ["province", "may2024_province_backcast"]
    )
)

age_map = {
    "<18": "<18 to 29",
    "18-24": "<18 to 29",
    "25-29": "<18 to 29",
    "30-39": "30-39",
    "40-44": "40 to >44",
    ">44": "40 to >44",
}
age = raw.loc[
    raw["dimension"].str.lower().eq("age") & raw["category"].isin(age_map)
].copy()
age["age3"] = age["category"].map(age_map)
age_group_columns = [
    "age3", "period", "ym_stata", "ym_index", "event_time_nov2022",
    "cno4", "cno2", "cno1d",
]
first_columns = [
    "exposure_nearest", "exposure_10pp", "exposure_weighted",
    "exposure_weighted_10pp", "post_nov2022",
    "treat_high", "treat_zero", "sdid_donor", "binary_sample", "did_post",
]
age_agg = (
    age.groupby(age_group_columns, as_index=False)
    .agg({
        "parados": lambda values: values.sum(min_count=len(values)),
        "contratos": lambda values: values.sum(min_count=len(values)),
        "may2024_age_backcast": "max",
        **{column: "first" for column in first_columns},
    })
)
age_agg["ln_parados"] = np.where(age_agg["parados"] > 0, np.log(age_agg["parados"]), np.nan)
age_agg["ln_contratos"] = np.where(age_agg["contratos"] > 0, np.log(age_agg["contratos"]), np.nan)
age_agg = age_agg.sort_values(["age3", "cno4", "ym_stata"]).copy()
age_agg["contratos_12m"] = (
    age_agg.groupby(["age3", "cno4"])["contratos"]
    .transform(lambda values: values.rolling(12, min_periods=12).sum())
)
age_agg["ln_contratos_12m"] = np.where(
    age_agg["contratos_12m"] > 0, np.log(age_agg["contratos_12m"]), np.nan
)
age_agg["ln_parados_p1"] = np.log(age_agg["parados"].fillna(0) + 1)
age_agg["ln_contratos_p1"] = np.log(age_agg["contratos"].fillna(0) + 1)
age_agg["parados_contratos"] = np.where(
    age_agg["contratos"] > 0,
    age_agg["parados"] / age_agg["contratos"],
    np.nan,
)
created.append(
    write_panel(
        age_agg,
        "est_age3_cno4.csv",
        ["age3", "cno4"],
        ["age3", "may2024_age_backcast"],
    )
)

gender = raw.loc[raw["dimension"].str.lower().eq("gender")].copy()
created.append(
    write_panel(gender, "est_gender_cno4.csv", ["gender", "cno4"], ["gender"])
)

# Construct the predetermined EPA feminization index for CNO4 occupations
# occupation-by-gender and composition panels used in the new subsection.
from lib.feminization import prepare_gender_composition_inputs
feminization_input_summary = prepare_gender_composition_inputs(
    PROJECT_ROOT, input_dir=PREPARED_DIR, audit_dir=INTERMEDIATE_DIR
)
print(feminization_input_summary)

manifest = pd.DataFrame(created)
manifest["sdid_cutoff_fixed"] = HIGH_CUTOFF
manifest["empirical_q75_full_distribution"] = q75_all
manifest["empirical_q75_positive_distribution"] = q75_positive
manifest.to_csv(INPUT_DIR / "estimation_input_manifest_v1.csv", index=False)

assert occupation_exposure["cno4"].nunique() == 502
assert total["period"].nunique() == 63

cutoff_audit = pd.DataFrame([{
    "occupations": len(occupation_exposure),
    "zero_exposure_occupations": int((occupation_exposure["exposure_nearest"] == 0).sum()),
    "positive_exposure_occupations": int((occupation_exposure["exposure_nearest"] > 0).sum()),
    "treated_above_0_1169": int((occupation_exposure["exposure_nearest"] > HIGH_CUTOFF).sum()),
    "donors_at_or_below_0_1169": int((occupation_exposure["exposure_nearest"] <= HIGH_CUTOFF).sum()),
    "fixed_cutoff": HIGH_CUTOFF,
    "q75_full_distribution": q75_all,
    "q75_positive_distribution": q75_positive,
}])
cutoff_audit.to_csv(TABLES_DIR / "treatment_cutoff_audit_v1.csv", index=False)

alternative_audit = (
    total[[
        "cno4", "exposure_nearest", "bls_ai_category_code",
        "frs_lm_aioe", "frs_lm_percentile",
    ]]
    .drop_duplicates("cno4")
)
alternative_summary = pd.DataFrame([{
    "bls_matched_cno4": int(alternative_audit["bls_ai_category_code"].notna().sum()),
    "frs_lm_matched_cno4": int(alternative_audit["frs_lm_aioe"].notna().sum()),
    "nearest_bls_spearman": alternative_audit[
        ["exposure_nearest", "bls_ai_category_code"]
    ].corr(method="spearman").iloc[0, 1],
    "nearest_frs_lm_spearman": alternative_audit[
        ["exposure_nearest", "frs_lm_percentile"]
    ].corr(method="spearman").iloc[0, 1],
}])
alternative_summary.to_csv(
    TABLES_DIR / "alternative_exposure_comparison_v1.csv", index=False
)

print(manifest)
print(cutoff_audit)
print(alternative_summary)


# Source cell 6

required = [
    "est_total_cno4.csv",
    "est_province_cno4.csv",
    "est_age3_cno4.csv",
    "est_gender_cno4.csv",
    "est_feminization_cno4.csv",
    "estimation_input_manifest_v1.csv",
]
missing = [name for name in required if not (PREPARED_DIR / name).exists()]
if missing:
    raise FileNotFoundError(f"Preparation did not create: {missing}")

prepared_manifest = []
for path in sorted(PREPARED_DIR.glob("*.csv")):
    prepared_manifest.append({
        "file": path.name,
        "bytes": path.stat().st_size,
        "location": str(path.relative_to(PROJECT_ROOT)),
    })
pd.DataFrame(prepared_manifest).to_csv(
    INTERMEDIATE_DIR / "prepared_file_manifest_v1.csv", index=False
)
print(f"Preparation complete: {len(prepared_manifest)} prepared files.")
print("Next: run 02_Descriptives_v1.ipynb.")
