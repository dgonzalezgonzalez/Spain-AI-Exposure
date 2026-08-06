"""Recover the missing May 2024 SEPE CNO4-by-age cells.

SEPE omitted the age breakdown from its May 2024 occupation pages. The June
pages report the June level and its percentage change relative to May for each
CNO4, age band, and outcome. This module inverts those changes and uses the
observed May CNO4 total as an adding-up validation. When the rounded cell rates
and separately published total conflict, only cells with a unique rate-implied
integer are retained; every ambiguity remains missing.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal, ROUND_HALF_UP
import math
import os
from pathlib import Path
import re
import time
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from lxml import html as lxml_html
import numpy as np
import pandas as pd


SEPE_BASE = "https://www.sepe.es"
SEPE_RESULTS_ENDPOINT = (
    "https://www.sepe.es/HomeSepe/que-es-observatorio/"
    "informacion-mt-por-ocupacion/main/04/content/resultados"
)
AGE_BANDS = ("<18", "18-24", "25-29", "30-39", "40-44", ">44")
OUTCOMES = ("parados", "contratos")
ALGORITHM_VERSION = 1
USER_AGENT = "Mozilla/5.0 (compatible; academic-research-data-audit/1.0)"


def _request(url: str, data: dict[str, str] | None = None, retries: int = 4) -> bytes:
    encoded = urlencode(data).encode("utf-8") if data is not None else None
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, data=encoded, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=35) as response:
                return response.read()
        except Exception as error:  # Network failures are retained in the audit.
            last_error = error
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"SEPE request failed after {retries} attempts: {url}") from last_error


def _clean_text(values) -> str:
    return re.sub(r"\s+", " ", " ".join(values)).strip()


def _parse_spanish_integer(value: str) -> int:
    cleaned = re.sub(r"[^\d-]", "", str(value).replace(".", ""))
    if not cleaned:
        raise ValueError(f"Cannot parse integer: {value!r}")
    return int(cleaned)


def _parse_spanish_percent(value: str) -> Decimal | None:
    cleaned = str(value).strip().replace("%", "").replace(".", "").replace(",", ".")
    cleaned = re.sub(r"[^\d.\-]", "", cleaned)
    if cleaned in {"", "-", "."}:
        return None
    return Decimal(cleaned)


def _discover_june_url(cno4: str) -> str:
    listing = _request(
        SEPE_RESULTS_ENDPOINT,
        {
            "list-mode": "detail",
            "ocupacion-id": cno4,
            "year-busc": "2024",
            "month-busc": "06",
        },
    )
    document = lxml_html.fromstring(listing)
    links = document.xpath('//a[contains(@href, "_mensuales_2024_06_")]/@href')
    if len(links) != 1:
        raise ValueError(f"Expected one June 2024 report for CNO4 {cno4}; found {len(links)}")
    return urljoin(SEPE_BASE, links[0])


def _parse_june_age_cells(cno4: str, report_url: str) -> list[dict[str, object]]:
    document = lxml_html.fromstring(_request(report_url))
    rows: list[dict[str, object]] = []
    for table in document.xpath("//table"):
        caption = _clean_text(table.xpath(".//caption//text()")).lower()
        if "sexo y edad" not in caption:
            continue
        if caption.startswith("parados"):
            outcome = "parados"
        elif caption.startswith("contratos"):
            outcome = "contratos"
        else:
            continue

        in_age_section = False
        for tr in table.xpath(".//tr"):
            cells = [_clean_text(cell.xpath(".//text()")) for cell in tr.xpath("./th|./td")]
            if not cells:
                continue
            if cells[0] == "Por tramos de edad":
                in_age_section = True
                continue
            if not in_age_section or cells[0] not in AGE_BANDS or len(cells) < 3:
                continue
            rows.append(
                {
                    "cno4": cno4,
                    "outcome": outcome,
                    "age_band": cells[0],
                    "june_value": _parse_spanish_integer(cells[1]),
                    "june_monthly_change_pct": _parse_spanish_percent(cells[2]),
                    "source_url": report_url,
                }
            )
    return rows


def _fetch_cno4(cno4: str) -> tuple[str, list[dict[str, object]], str]:
    try:
        report_url = _discover_june_url(cno4)
        rows = _parse_june_age_cells(cno4, report_url)
        return cno4, rows, ""
    except Exception as error:
        return cno4, [], f"{type(error).__name__}: {error}"


def _rounded_rate(june_value: int, may_value: int) -> Decimal:
    if may_value == 0:
        return Decimal("0.00") if june_value == 0 else Decimal("Infinity")
    rate = Decimal(100) * (Decimal(june_value) / Decimal(may_value) - Decimal(1))
    return rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _candidate_values(june_value: int, published_rate: Decimal | None):
    if published_rate is None:
        return []
    if not isinstance(published_rate, Decimal):
        published_rate = Decimal(str(published_rate))
    if june_value == 0:
        if published_rate == Decimal("0"):
            return [0]
        if published_rate == Decimal("-100"):
            return None  # Any strictly positive May value reproduces -100 percent.
        return []

    lower_rate = published_rate - Decimal("0.005")
    upper_rate = published_rate + Decimal("0.005")
    lower_denominator = Decimal(1) + upper_rate / Decimal(100)
    upper_denominator = Decimal(1) + lower_rate / Decimal(100)
    if lower_denominator <= 0 or upper_denominator <= 0:
        return []

    lower_value = Decimal(june_value) / lower_denominator
    upper_value = Decimal(june_value) / upper_denominator
    start = max(1, math.floor(float(min(lower_value, upper_value))) - 2)
    stop = math.ceil(float(max(lower_value, upper_value))) + 2
    return [
        candidate
        for candidate in range(start, stop + 1)
        if _rounded_rate(june_value, candidate) == published_rate
    ]


def _solve_adding_up(candidate_lists, total: int, solution_cap: int = 5000):
    flexible = [index for index, values in enumerate(candidate_lists) if values is None]
    if len(flexible) > 1 or any(values == [] for values in candidate_lists):
        return [], False

    fixed_indices = [index for index in range(len(candidate_lists)) if index not in flexible]
    states: dict[int, list[tuple[int, ...]]] = {0: [tuple()]}
    truncated = False
    for index in fixed_indices:
        next_states: dict[int, list[tuple[int, ...]]] = {}
        for subtotal, combinations in states.items():
            for value in candidate_lists[index]:
                new_total = subtotal + value
                if new_total > total:
                    continue
                bucket = next_states.setdefault(new_total, [])
                for combination in combinations:
                    if len(bucket) < solution_cap:
                        bucket.append(combination + (value,))
                    else:
                        truncated = True
        states = next_states

    solutions: list[tuple[int, ...]] = []
    if flexible:
        flexible_index = flexible[0]
        for subtotal, combinations in states.items():
            residual = total - subtotal
            if residual <= 0:
                continue
            for combination in combinations:
                full = [None] * len(candidate_lists)
                full[flexible_index] = residual
                for index, value in zip(fixed_indices, combination):
                    full[index] = value
                solutions.append(tuple(full))
                if len(solutions) >= solution_cap:
                    truncated = True
                    return solutions, truncated
    else:
        solutions = states.get(total, [])
    return solutions, truncated


def _empty_audit_rows(
    cno4: str,
    may_totals: dict[tuple[str, str], float],
    error: str,
) -> list[dict[str, object]]:
    return [
        {
            "cno4": cno4,
            "outcome": outcome,
            "age_band": age_band,
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
        for age_band in AGE_BANDS
    ]


def _reconstruct_cno4(
    cno4: str,
    fetched_rows: list[dict[str, object]],
    may_totals: dict[tuple[str, str], float],
    fetch_error: str,
) -> list[dict[str, object]]:
    if fetch_error:
        return _empty_audit_rows(cno4, may_totals, fetch_error)

    fetched = {
        (str(row["outcome"]), str(row["age_band"])): row
        for row in fetched_rows
    }
    audit_rows: list[dict[str, object]] = []
    for outcome in OUTCOMES:
        total_value = may_totals.get((cno4, outcome), np.nan)
        outcome_rows = [fetched.get((outcome, age_band)) for age_band in AGE_BANDS]
        if pd.isna(total_value) or any(row is None for row in outcome_rows):
            error = "Missing May total or incomplete June age table"
            base = _empty_audit_rows(cno4, may_totals, error)
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
        solutions, truncated = _solve_adding_up(candidates, total)
        solution_count = len(solutions)

        for index, (age_band, row, values) in enumerate(zip(AGE_BANDS, outcome_rows, candidates)):
            recovered = np.nan
            status = "unresolved"
            if solutions:
                supported_values = {solution[index] for solution in solutions}
                globally_fixed = values is not None and len(values) == 1
                if len(supported_values) == 1 and (not truncated or globally_fixed):
                    recovered = float(next(iter(supported_values)))
                    status = (
                        "recovered_unique_adding_up"
                        if solution_count == 1 and not truncated
                        else "recovered_component_unique"
                    )
                else:
                    status = "ambiguous_adding_up"
            elif values == []:
                status = "no_rate_consistent_integer"
            elif values is None:
                status = "unidentified_minus_100_rate"
            elif len(values) == 1:
                # The rounded cell-level rate uniquely identifies May even
                # when the six implied cells do not match a separately
                # published total, typically because SEPE revised one series.
                recovered = float(values[0])
                status = "recovered_unique_rate_total_mismatch"
            else:
                status = "no_adding_up_solution"

            audit_rows.append(
                {
                    "cno4": cno4,
                    "outcome": outcome,
                    "age_band": age_band,
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


def _may_totals(raw: pd.DataFrame) -> dict[tuple[str, str], float]:
    mask = (
        raw["period"].eq("2024-05")
        & raw["dimension"].str.lower().eq("total")
        & raw["category"].str.lower().eq("total")
        & raw["gender"].str.lower().eq("total")
    )
    totals: dict[tuple[str, str], float] = {}
    for row in raw.loc[mask, ["cno4", *OUTCOMES]].itertuples(index=False):
        for outcome in OUTCOMES:
            value = getattr(row, outcome)
            if pd.notna(value):
                totals[(str(row.cno4).zfill(4), outcome)] = float(value)
    return totals


def reconstruct_may_2024_age_cells(
    raw: pd.DataFrame,
    cache_path: str | Path,
    refresh: bool = False,
    workers: int = 8,
) -> pd.DataFrame:
    """Return a 502 x 6 x 2 cell-level reconstruction audit."""
    cache_path = Path(cache_path)
    if cache_path.exists() and not refresh:
        cached = pd.read_csv(cache_path, dtype={"cno4": str})
        if (
            len(cached) == 502 * len(AGE_BANDS) * len(OUTCOMES)
            and set(cached.get("algorithm_version", [])) == {ALGORITHM_VERSION}
        ):
            cached["cno4"] = cached["cno4"].astype(str).str.zfill(4)
            return cached

    cno4_values = sorted(raw["cno4"].astype(str).str.zfill(4).unique())
    totals = _may_totals(raw)
    fetched: dict[str, tuple[list[dict[str, object]], str]] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_fetch_cno4, cno4): cno4 for cno4 in cno4_values}
        for completed, future in enumerate(as_completed(futures), start=1):
            cno4, rows, error = future.result()
            fetched[cno4] = (rows, error)
            if completed % 50 == 0 or completed == len(futures):
                print(f"Fetched June 2024 SEPE age tables: {completed}/{len(futures)}")

    audit_rows: list[dict[str, object]] = []
    for cno4 in cno4_values:
        rows, error = fetched.get(cno4, ([], "No fetch result"))
        audit_rows.extend(_reconstruct_cno4(cno4, rows, totals, error))

    audit = pd.DataFrame(audit_rows)
    audit["cno4"] = audit["cno4"].astype(str).str.zfill(4)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(cache_path, index=False)
    return audit


def append_reconstructed_age_rows(raw: pd.DataFrame, audit: pd.DataFrame) -> pd.DataFrame:
    """Append validated compact May age rows without changing the source CSV."""
    recovered = audit.pivot(
        index=["cno4", "age_band"],
        columns="outcome",
        values="recovered_may_value",
    ).reset_index()
    recovered = recovered.rename(columns={"age_band": "category"})

    metadata_mask = (
        raw["period"].eq("2024-05")
        & raw["dimension"].str.lower().eq("total")
        & raw["category"].str.lower().eq("total")
        & raw["gender"].str.lower().eq("total")
    )
    metadata = raw.loc[metadata_mask].drop_duplicates("cno4").copy()
    metadata = metadata.drop(
        columns=[
            "period",
            "dimension",
            "category",
            "gender",
            "source_url",
            "parados",
            "contratos",
            "personas",
        ],
        errors="ignore",
    )
    appended = recovered.merge(metadata, on="cno4", how="left", validate="many_to_one")
    appended["period"] = "2024-05"
    appended["dimension"] = "age"
    appended["gender"] = "Total"
    appended["source_url"] = "backcast://sepe/june-2024-monthly-change"
    appended["may2024_age_backcast"] = 1

    output = raw.copy()
    output["may2024_age_backcast"] = 0
    existing_age_may = (
        output["period"].eq("2024-05")
        & output["dimension"].str.lower().eq("age")
        & output["category"].isin(AGE_BANDS)
    )
    output = output.loc[~existing_age_may].copy()
    appended = appended.reindex(columns=output.columns)
    return pd.concat([output, appended], ignore_index=True)


def reconstruction_missingness(audit: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return original-age and final-three-group missingness summaries."""
    work = audit.copy()
    work["missing"] = work["recovered_may_value"].isna()
    total_cells = len(work)

    by_band_outcome = (
        work.groupby(["outcome", "age_band"], as_index=False)
        .agg(expected_cells=("missing", "size"), missing_cells=("missing", "sum"))
    )
    by_band_outcome["missing_pct_within_row"] = (
        100 * by_band_outcome["missing_cells"] / by_band_outcome["expected_cells"]
    )
    by_band_outcome["missing_pct_all_may_age_cells"] = (
        100 * by_band_outcome["missing_cells"] / total_cells
    )

    by_band = (
        work.groupby("age_band", as_index=False)
        .agg(expected_cells=("missing", "size"), missing_cells=("missing", "sum"))
    )
    by_band.insert(0, "outcome", "both outcomes")
    by_band["missing_pct_within_row"] = 100 * by_band["missing_cells"] / by_band["expected_cells"]
    by_band["missing_pct_all_may_age_cells"] = 100 * by_band["missing_cells"] / total_cells

    overall = pd.DataFrame(
        [{
            "outcome": "both outcomes",
            "age_band": "overall",
            "expected_cells": total_cells,
            "missing_cells": int(work["missing"].sum()),
            "missing_pct_within_row": 100 * work["missing"].mean(),
            "missing_pct_all_may_age_cells": 100 * work["missing"].mean(),
        }]
    )
    detailed = pd.concat([by_band_outcome, by_band, overall], ignore_index=True)

    age3_map = {
        "<18": "Under 30",
        "18-24": "Under 30",
        "25-29": "Under 30",
        "30-39": "Ages 30-39",
        "40-44": "Age 40 or older",
        ">44": "Age 40 or older",
    }
    work["age3"] = work["age_band"].map(age3_map)
    final_cells = (
        work.groupby(["cno4", "outcome", "age3"], as_index=False)
        .agg(missing=("missing", "max"))
    )
    final_total = len(final_cells)
    final_summary = (
        final_cells.groupby(["outcome", "age3"], as_index=False)
        .agg(expected_cells=("missing", "size"), missing_cells=("missing", "sum"))
    )
    final_summary["missing_pct_within_row"] = (
        100 * final_summary["missing_cells"] / final_summary["expected_cells"]
    )
    final_summary["missing_pct_all_final_age_cells"] = (
        100 * final_summary["missing_cells"] / final_total
    )
    return detailed, final_summary
