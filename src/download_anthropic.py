from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile
import requests
import pandas as pd

from .config import ANTHROPIC_ECON_INDEX_RELEASE_URL, ANTHROPIC_JOB_EXPOSURE_URL, PipelineConfig


REQUIRED_COLUMNS = {"occ_code", "title", "observed_exposure"}
ECON_INDEX_CLAUDE_AI_MEMBER = "aei_claude_ai_2026-06-26.csv"
COUNTRY_JOB_USAGE_COLUMNS = {
    "date_start",
    "date_end",
    "geo_id",
    "geo_level",
    "category_name",
    "hierarchy_level",
    "metric_id",
    "value",
    "node_name",
    "node_external_id",
}


def download_anthropic_job_exposure(config: PipelineConfig, refresh: bool = False) -> Path:
    config.ensure_dirs()
    target = config.raw_dir / "anthropic" / "job_exposure.csv"
    if target.exists() and not refresh:
        return target

    response = requests.get(ANTHROPIC_JOB_EXPOSURE_URL, timeout=60)
    response.raise_for_status()
    target.write_bytes(response.content)
    return target


def load_anthropic_job_exposure(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"occ_code": "string", "title": "string"})
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Anthropic job exposure file missing columns: {sorted(missing)}")

    df = df.copy()
    df["occ_code"] = df["occ_code"].astype("string").str.strip()
    df["title"] = df["title"].astype("string").str.strip()
    df["observed_exposure"] = pd.to_numeric(df["observed_exposure"], errors="coerce")
    df = df.dropna(subset=["occ_code", "title", "observed_exposure"])
    return df


def download_anthropic_economic_index_release(config: PipelineConfig, refresh: bool = False) -> Path:
    config.ensure_dirs()
    target = config.raw_dir / "anthropic" / "release-2026-06-26.zip"
    if target.exists() and not refresh:
        return target

    response = requests.get(ANTHROPIC_ECON_INDEX_RELEASE_URL, timeout=120)
    response.raise_for_status()
    target.write_bytes(response.content)
    return target


def load_country_job_usage(zip_path: Path, date_start: str | None = None) -> pd.DataFrame:
    """Compare Spanish usage with the published global aggregate, not country means."""
    with ZipFile(zip_path) as archive:
        with archive.open(ECON_INDEX_CLAUDE_AI_MEMBER) as source:
            df = pd.read_csv(source, dtype={"geo_id": "string", "node_external_id": "string"})

    missing = COUNTRY_JOB_USAGE_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Anthropic Economic Index file missing columns: {sorted(missing)}")

    sub = df[
        (
            ((df["geo_id"] == "ESP") & (df["geo_level"] == "country"))
            | ((df["geo_id"] == "GLOBAL") & (df["geo_level"] == "global"))
        )
        & (df["category_name"] == "soc_occupation")
        & (df["hierarchy_level"] == 1)
        & (df["metric_id"] == "pct")
    ].copy()
    if sub.empty:
        raise ValueError("No Spain/global SOC major-group usage rows found.")

    if date_start is None:
        date_start = str(sub["date_start"].max())
    sub = sub[sub["date_start"] == date_start].copy()

    if sub.duplicated(["node_external_id", "geo_id"]).any():
        raise ValueError(f"Duplicate SOC major-group usage rows on {date_start}.")
    pivot = sub.pivot(
        index=["node_external_id", "node_name", "date_start", "date_end"],
        columns="geo_id",
        values="value",
    ).reset_index()
    pivot.columns.name = None
    required_geos = {"ESP", "GLOBAL"}
    if not required_geos.issubset(pivot.columns):
        raise ValueError(f"Missing geography values for {sorted(required_geos.difference(pivot.columns))} on {date_start}.")
    if pivot[["ESP", "GLOBAL"]].isna().any().any():
        raise ValueError(f"Missing Spain/global values for one or more SOC major groups on {date_start}.")

    out = pivot.rename(
        columns={
            "node_external_id": "soc_major_group",
            "node_name": "job_group",
            "ESP": "spain_usage_pct",
            "GLOBAL": "global_usage_pct",
        }
    ).copy()
    out["spain_minus_global_pct"] = out["spain_usage_pct"] - out["global_usage_pct"]
    out["spain_usage_pct"] = out["spain_usage_pct"].round(2)
    out["global_usage_pct"] = out["global_usage_pct"].round(2)
    out["spain_minus_global_pct"] = out["spain_minus_global_pct"].round(2)
    return out[
        [
            "soc_major_group",
            "job_group",
            "date_start",
            "date_end",
            "spain_usage_pct",
            "global_usage_pct",
            "spain_minus_global_pct",
        ]
    ].sort_values(
        ["spain_usage_pct", "soc_major_group"],
        ascending=[False, True],
        kind="stable",
    ).reset_index(drop=True)
