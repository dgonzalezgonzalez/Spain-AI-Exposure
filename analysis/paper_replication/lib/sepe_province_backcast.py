"""Recover the missing May 2024 SEPE CNO4-by-province cells.

SEPE omitted the province breakdown from its May 2024 occupation pages. The
June pages report the June level and its percentage change relative to May for
each CNO4, province, and outcome. This module inverts those rounded changes and
uses the observed May CNO4 total as an adding-up validation. Only uniquely
identified integer counts are retained; ambiguous cells remain missing.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from lxml import html as lxml_html
import numpy as np
import pandas as pd

from .sepe_age_backcast import (
    OUTCOMES,
    _candidate_values,
    _clean_text,
    _discover_june_url,
    _may_totals,
    _parse_spanish_integer,
    _parse_spanish_percent,
    _request,
)


ALGORITHM_VERSION = 1


def _parse_june_province_cells(
    cno4: str,
    report_url: str,
    expected_provinces: set[str],
) -> list[dict[str, object]]:
    document = lxml_html.fromstring(_request(report_url))
    rows: list[dict[str, object]] = []
    for table in document.xpath("//table"):
        caption = _clean_text(table.xpath(".//caption//text()")).lower()
        if caption == "distribución geográfica de parados":
            outcome = "parados"
        elif caption == "distribución geográfica de contratos":
            outcome = "contratos"
        else:
            continue

        for tr in table.xpath(".//tr"):
            cells = [_clean_text(cell.xpath(".//text()")) for cell in tr.xpath("./th|./td")]
            if len(cells) < 3 or cells[0] not in expected_provinces:
                continue
            rows.append(
                {
                    "cno4": cno4,
                    "outcome": outcome,
                    "province": cells[0],
                    "june_value": _parse_spanish_integer(cells[1]),
                    "june_monthly_change_pct": _parse_spanish_percent(cells[2]),
                    "source_url": report_url,
                }
            )
    return rows


def _fetch_cno4(
    cno4: str,
    expected_provinces: set[str],
) -> tuple[str, list[dict[str, object]], str]:
    try:
        report_url = _discover_june_url(cno4)
        rows = _parse_june_province_cells(cno4, report_url, expected_provinces)
        return cno4, rows, ""
    except Exception as error:
        return cno4, [], f"{type(error).__name__}: {error}"


def _empty_rows(
    cno4: str,
    provinces: tuple[str, ...],
    may_totals: dict[tuple[str, str], float],
    error: str,
) -> list[dict[str, object]]:
    return [
        {
            "cno4": cno4,
            "outcome": outcome,
            "province": province,
            "june_value": np.nan,
            "june_monthly_change_pct": np.nan,
            "may_total": may_totals.get((cno4, outcome), np.nan),
            "candidate_count": 0,
            "recovered_may_value": np.nan,
            "status": "source_unavailable",
            "adding_up_solution_count": 0,
            "adding_up_solutions_truncated": False,
            "source_url": "",
            "error": error,
            "algorithm_version": ALGORITHM_VERSION,
        }
        for outcome in OUTCOMES
        for province in provinces
    ]


def _reconstruct_cno4(
    cno4: str,
    provinces: tuple[str, ...],
    fetched_rows: list[dict[str, object]],
    may_totals: dict[tuple[str, str], float],
    fetch_error: str,
) -> list[dict[str, object]]:
    if fetch_error:
        return _empty_rows(cno4, provinces, may_totals, fetch_error)

    fetched = {
        (str(row["outcome"]), str(row["province"])): row
        for row in fetched_rows
    }
    audit_rows: list[dict[str, object]] = []
    for outcome in OUTCOMES:
        total_value = may_totals.get((cno4, outcome), np.nan)
        outcome_rows = [fetched.get((outcome, province)) for province in provinces]
        if pd.isna(total_value) or any(row is None for row in outcome_rows):
            base = _empty_rows(
                cno4,
                provinces,
                may_totals,
                "Missing May total or incomplete June province table",
            )
            audit_rows.extend([row for row in base if row["outcome"] == outcome])
            continue

        total = int(round(float(total_value)))
        candidates = [
            _candidate_values(
                int(row["june_value"]),
                row["june_monthly_change_pct"],
            )
            for row in outcome_rows
        ]
        # Most province cells are uniquely identified by their rounded rate.
        # With 52 cells, a general combinatorial adding-up search is neither
        # transparent nor stable. We use the total to validate a complete set
        # of unique cells, or to recover one remaining residual cell. If two or
        # more cells are ambiguous, they remain missing.
        fixed_values = {
            index: values[0]
            for index, values in enumerate(candidates)
            if values is not None and len(values) == 1
        }
        unresolved_indices = [
            index for index in range(len(candidates)) if index not in fixed_values
        ]
        residual_total = total - sum(fixed_values.values())
        residual_recovery: dict[int, int] = {}
        adding_up_valid = not unresolved_indices and residual_total == 0
        if len(unresolved_indices) == 1 and residual_total >= 0:
            unresolved_index = unresolved_indices[0]
            values = candidates[unresolved_index]
            residual_is_valid = (
                (values is None and residual_total > 0)
                or (values is not None and residual_total in values)
            )
            if residual_is_valid:
                residual_recovery[unresolved_index] = residual_total
                adding_up_valid = True
        solution_count = int(adding_up_valid)
        truncated = False

        for index, (province, row, values) in enumerate(
            zip(provinces, outcome_rows, candidates)
        ):
            recovered = np.nan
            status = "unresolved"
            if index in residual_recovery:
                recovered = float(residual_recovery[index])
                status = "recovered_unique_adding_up"
            elif values is not None and len(values) == 1:
                recovered = float(values[0])
                status = (
                    "recovered_unique_adding_up"
                    if adding_up_valid
                    else "recovered_unique_rate_total_unresolved"
                )
            elif values == []:
                status = "no_rate_consistent_integer"
            elif values is None:
                status = "unidentified_minus_100_rate"
            else:
                status = "ambiguous_rounded_rate"

            audit_rows.append(
                {
                    "cno4": cno4,
                    "outcome": outcome,
                    "province": province,
                    "june_value": int(row["june_value"]),
                    "june_monthly_change_pct": float(row["june_monthly_change_pct"]),
                    "may_total": total,
                    "candidate_count": np.nan if values is None else len(values),
                    "recovered_may_value": recovered,
                    "status": status,
                    "adding_up_solution_count": solution_count,
                    "adding_up_solutions_truncated": truncated,
                    "source_url": row["source_url"],
                    "error": "",
                    "algorithm_version": ALGORITHM_VERSION,
                }
            )
    return audit_rows


def _expected_provinces(raw: pd.DataFrame) -> tuple[str, ...]:
    mask = raw["period"].eq("2024-06") & raw["dimension"].str.lower().eq("province")
    provinces = tuple(sorted(raw.loc[mask, "category"].dropna().astype(str).unique()))
    if len(provinces) != 52:
        raise ValueError(f"Expected 52 June 2024 provinces; found {len(provinces)}")
    return provinces


def reconstruct_may_2024_province_cells(
    raw: pd.DataFrame,
    cache_path: str | Path,
    refresh: bool = False,
    workers: int = 8,
) -> pd.DataFrame:
    """Return a 502 x 52 x 2 cell-level reconstruction audit."""
    cache_path = Path(cache_path)
    provinces = _expected_provinces(raw)
    expected_rows = 502 * len(provinces) * len(OUTCOMES)
    if cache_path.exists() and not refresh:
        cached = pd.read_csv(cache_path, dtype={"cno4": str})
        if (
            len(cached) == expected_rows
            and set(cached.get("algorithm_version", [])) == {ALGORITHM_VERSION}
        ):
            cached["cno4"] = cached["cno4"].astype(str).str.zfill(4)
            return cached

    cno4_values = sorted(raw["cno4"].astype(str).str.zfill(4).unique())
    totals = _may_totals(raw)
    expected_set = set(provinces)
    fetched: dict[str, tuple[list[dict[str, object]], str]] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_fetch_cno4, cno4, expected_set): cno4
            for cno4 in cno4_values
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            cno4, rows, error = future.result()
            fetched[cno4] = (rows, error)
            if completed % 50 == 0 or completed == len(futures):
                print(f"Fetched June 2024 SEPE province tables: {completed}/{len(futures)}")

    audit_rows: list[dict[str, object]] = []
    for cno4 in cno4_values:
        rows, error = fetched.get(cno4, ([], "No fetch result"))
        audit_rows.extend(
            _reconstruct_cno4(cno4, provinces, rows, totals, error)
        )

    audit = pd.DataFrame(audit_rows)
    audit["cno4"] = audit["cno4"].astype(str).str.zfill(4)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(cache_path, index=False)
    return audit


def append_reconstructed_province_rows(
    raw: pd.DataFrame,
    audit: pd.DataFrame,
) -> pd.DataFrame:
    """Append validated May province rows without overwriting the source CSV."""
    recovered = audit.pivot(
        index=["cno4", "province"],
        columns="outcome",
        values="recovered_may_value",
    ).reset_index()
    recovered = recovered.rename(columns={"province": "category"})

    metadata_mask = (
        raw["period"].eq("2024-05")
        & raw["dimension"].str.lower().eq("total")
        & raw["category"].str.lower().eq("total")
        & raw["gender"].str.lower().eq("total")
    )
    metadata = raw.loc[metadata_mask].drop_duplicates("cno4").copy()
    metadata = metadata.drop(
        columns=[
            "period", "dimension", "category", "gender", "source_url",
            "parados", "contratos", "personas",
        ],
        errors="ignore",
    )
    appended = recovered.merge(metadata, on="cno4", how="left", validate="many_to_one")
    appended["period"] = "2024-05"
    appended["dimension"] = "province"
    appended["gender"] = "Total"
    appended["source_url"] = "backcast://sepe/june-2024-province-monthly-change"
    appended["may2024_province_backcast"] = 1

    output = raw.copy()
    output["may2024_province_backcast"] = 0
    existing = output["period"].eq("2024-05") & output["dimension"].str.lower().eq("province")
    output = output.loc[~existing].copy()
    appended = appended.reindex(columns=output.columns)
    return pd.concat([output, appended], ignore_index=True)


def reconstruction_missingness(audit: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return province-by-outcome and overall May 2024 missingness summaries."""
    work = audit.copy()
    work["missing"] = work["recovered_may_value"].isna()
    by_province = (
        work.groupby(["province", "outcome"], as_index=False)
        .agg(expected_cells=("missing", "size"), missing_cells=("missing", "sum"))
    )
    by_province["missing_pct"] = (
        100 * by_province["missing_cells"] / by_province["expected_cells"]
    )
    overall = (
        work.groupby("outcome", as_index=False)
        .agg(expected_cells=("missing", "size"), missing_cells=("missing", "sum"))
    )
    combined = pd.DataFrame(
        [{
            "outcome": "all",
            "expected_cells": len(work),
            "missing_cells": int(work["missing"].sum()),
        }]
    )
    overall = pd.concat([overall, combined], ignore_index=True)
    overall["missing_pct"] = 100 * overall["missing_cells"] / overall["expected_cells"]
    return by_province, overall
