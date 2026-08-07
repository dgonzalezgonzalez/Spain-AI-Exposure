from __future__ import annotations

import argparse
import logging
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOGGER = logging.getLogger(__name__)

INDEX_URL = (
    "https://www.sepe.es/HomeSepe/que-es-el-sepe/estadisticas/empleo/"
    "estadisticas-nuevas.html"
)
DEFAULT_OUTPUT_PATH = Path("data/sepe_demandas_ocupacion_long.parquet")
DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_TMP_DIR = Path("data/tmp/blocks")
RAW_DATASET_KEY_COLUMNS = ["fecha", "codigo_ocupacion", "sexo", "ambito"]
RAW_DATASET_SORT_COLUMNS = ["fecha", "codigo_ocupacion", "ambito"]
FINAL_DATASET_KEY_COLUMNS = ["anio", "mes", "codigo_ocupacion", "sexo"]
FINAL_DATASET_SORT_COLUMNS = ["anio", "mes", "codigo_ocupacion"]
FINAL_VALUE_COLUMN = "total de parados registrados"
FINAL_EXPORT_START_YEAR = 2011
# Aunque el scraper puede descargar historico anterior, no exportamos datos antes de
# 2011 porque la clasificacion CNO utilizada en esos anios no es directamente comparable.

MONTH_TO_NUMBER = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
TARGET_TOKENS = (
    "demandas de empleo pendientes",
    "subgrupo principal de ocupacion",
    "ambos sexos",
)
METRIC_NAMES = {
    2: "total",
    3: "parados",
    4: "no_parados_total",
    5: "no_parados_con_disponibilidad_limitada",
    6: "no_parados_con_relacion_laboral",
    7: "no_parados_teass",
    8: "ocupados",
    9: "demandan_empleos_especificos",
    10: "otros_no_ocupados",
}


@dataclass(frozen=True)
class MonthlyWorkbook:
    year: int
    month: int
    month_slug: str
    month_page_url: str
    workbook_url: str

    @property
    def period(self) -> pd.Timestamp:
        return pd.Timestamp(year=self.year, month=self.month, day=1)

    @property
    def period_key(self) -> str:
        return self.period.strftime("%Y-%m")


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s | %(message)s")


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def slugify_text(value: object) -> str:
    text = normalize_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def build_session() -> requests.Session:
    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            )
        }
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch_html(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=60)
    response.raise_for_status()
    return response.text


def discover_month_pages(session: requests.Session) -> list[tuple[int, str, str]]:
    html = fetch_html(session, INDEX_URL)
    soup = BeautifulSoup(html, "lxml")
    discovered: dict[tuple[int, str], str] = {}

    for anchor in soup.select("a[href]"):
        href = urljoin(INDEX_URL, anchor["href"])
        match = re.search(r"/estadisticas-nuevas/(\d{4})/([a-z-]+)\.html$", href, re.I)
        if not match:
            continue
        year = int(match.group(1))
        month_slug = match.group(2).lower()
        if month_slug not in MONTH_TO_NUMBER:
            continue
        discovered[(year, month_slug)] = href

    if discovered:
        return sorted(
            ((year, month_slug, href) for (year, month_slug), href in discovered.items()),
            key=lambda item: (item[0], MONTH_TO_NUMBER[item[1]]),
        )

    LOGGER.warning(
        "No se encontraron meses en el indice principal; se probara la ruta de reserva."
    )
    fallback: list[tuple[int, str, str]] = []
    for year in range(2005, pd.Timestamp.utcnow().year + 1):
        for month_slug in MONTH_TO_NUMBER:
            candidate = (
                "https://www.sepe.es/HomeSepe/que-es-el-sepe/estadisticas/empleo/"
                f"estadisticas-nuevas/{year}/{month_slug}.html"
            )
            response = session.get(candidate, timeout=30)
            if response.status_code == 200 and "Libro completo" in response.text:
                fallback.append((year, month_slug, candidate))
    return fallback


def extract_excel_url(month_page_url: str, html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    for row in soup.select("tr"):
        row_text = normalize_text(row.get_text(" ", strip=True)).lower()
        if "libro completo" not in row_text:
            continue
        for anchor in row.select("a[href]"):
            href = anchor.get("href", "")
            if re.search(r"\.xls[x]?$", href, re.I):
                return urljoin(month_page_url, href)

    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if not re.search(r"\.xls[x]?$", href, re.I):
            continue
        nearby_text = normalize_text(anchor.parent.get_text(" ", strip=True)).lower()
        if "libro completo" in nearby_text:
            return urljoin(month_page_url, href)

    excel_links = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if re.search(r"\.xls[x]?$", href, re.I):
            excel_links.append(urljoin(month_page_url, href))

    if len(excel_links) == 1:
        return excel_links[0]

    raise ValueError(f"No se encontro un enlace Excel 'Libro completo' en {month_page_url}")


def discover_workbooks(
    session: requests.Session,
    start_year: int | None = None,
    end_year: int | None = None,
) -> list[MonthlyWorkbook]:
    pages = discover_month_pages(session)
    workbooks: list[MonthlyWorkbook] = []

    for year, month_slug, page_url in pages:
        month_number = MONTH_TO_NUMBER[month_slug]
        if start_year is not None and year < start_year:
            continue
        if end_year is not None and year > end_year:
            continue

        html = fetch_html(session, page_url)
        try:
            workbook_url = extract_excel_url(page_url, html)
        except ValueError:
            LOGGER.warning("Se omite %s porque no hay Excel disponible.", page_url)
            continue

        workbooks.append(
            MonthlyWorkbook(
                year=year,
                month=month_number,
                month_slug=month_slug,
                month_page_url=page_url,
                workbook_url=workbook_url,
            )
        )

    return workbooks


def workbook_filename(item: MonthlyWorkbook) -> str:
    parsed = urlparse(item.workbook_url)
    filename = Path(parsed.path).name
    if not filename:
        suffix = ".xlsx" if parsed.path.lower().endswith(".xlsx") else ".xls"
        filename = f"{item.year}_{item.month:02d}_sepe{suffix}"
    return filename


def download_workbook(
    session: requests.Session,
    item: MonthlyWorkbook,
    raw_dir: Path,
    force_download: bool = False,
) -> Path:
    target_dir = raw_dir / str(item.year) / f"{item.month:02d}_{item.month_slug}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / workbook_filename(item)

    if target_path.exists() and not force_download:
        LOGGER.info("Reutilizando %s", target_path)
        return target_path

    LOGGER.info("Descargando %s", item.workbook_url)
    response = session.get(item.workbook_url, timeout=120)
    response.raise_for_status()
    target_path.write_bytes(response.content)
    return target_path


def read_excel_preview(path: Path, sheet_name: str, nrows: int = 20) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet_name, header=None, nrows=nrows)


def find_target_sheet(path: Path) -> str:
    workbook = pd.ExcelFile(path)

    if "Indice" in workbook.sheet_names:
        try:
            index_df = pd.read_excel(path, sheet_name="Indice", header=None)
            for cell in index_df.fillna("").astype(str).to_numpy().ravel():
                normalized = normalize_text(cell).lower()
                if all(token in normalized for token in TARGET_TOKENS):
                    match = re.match(r"^(\d+(?:\.\d+)*)", normalize_text(cell))
                    if match and match.group(1) in workbook.sheet_names:
                        return match.group(1)
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("No se pudo resolver la hoja a partir del indice: %s", exc)

    best_sheet: str | None = None
    best_score = -1
    for sheet_name in workbook.sheet_names:
        preview = read_excel_preview(path, sheet_name=sheet_name)
        preview_text = normalize_text(
            " ".join(preview.fillna("").astype(str).to_numpy().ravel())
        ).lower()
        score = sum(token in preview_text for token in TARGET_TOKENS)
        if "hombres" in preview_text or "mujeres" in preview_text:
            score -= 1
        if score > best_score:
            best_score = score
            best_sheet = sheet_name

    if best_sheet is None or best_score <= 0:
        raise ValueError(f"No se pudo identificar la hoja objetivo en {path}")

    return best_sheet


def detect_header_row(sheet_df: pd.DataFrame) -> int:
    for idx in range(1, len(sheet_df)):
        previous_values = [
            normalize_text(value).lower() for value in sheet_df.iloc[idx - 1].tolist()
        ]
        current_values = [
            normalize_text(value).lower() for value in sheet_df.iloc[idx].tolist()
        ]
        joined = " | ".join(value for value in previous_values + current_values if value)
        if (
            "parados" in joined
            and "ocupados" in joined
            and "demandan empleos" in joined
            and "otros no ocupados" in joined
        ):
            return idx
    raise ValueError("No se encontro la fila de cabecera de metricas.")


def parse_metric_names(sheet_df: pd.DataFrame, header_row: int) -> dict[int, str]:
    metrics: dict[int, str] = {}
    upper_row = sheet_df.iloc[header_row - 1] if header_row > 0 else pd.Series(dtype=object)
    lower_row = sheet_df.iloc[header_row]

    for col_idx in range(2, min(len(lower_row), 11)):
        upper = normalize_text(upper_row.iloc[col_idx] if col_idx < len(upper_row) else "")
        lower = normalize_text(lower_row.iloc[col_idx])
        if col_idx in METRIC_NAMES:
            metrics[col_idx] = METRIC_NAMES[col_idx]
            continue
        lower_slug = slugify_text(lower)
        if upper.lower() == "no parados":
            metrics[col_idx] = f"no_parados_{lower_slug}"
        else:
            metrics[col_idx] = lower_slug
    return metrics


def coerce_int(value: object) -> int:
    if pd.isna(value):
        return 0
    if isinstance(value, str):
        text = value.strip().replace(".", "").replace(",", "")
        if text in {"", "-", "--"}:
            return 0
        return int(float(text))
    return int(value)


def extract_numeric_code(label: str) -> tuple[str, str] | None:
    match = re.match(r"^(\d{2})\s+(.+)$", label)
    if not match:
        return None
    return match.group(1), match.group(2).strip()


def is_export_eligible_workbook(item: MonthlyWorkbook) -> bool:
    return item.year >= FINAL_EXPORT_START_YEAR


def sort_raw_dataset(dataset: pd.DataFrame) -> pd.DataFrame:
    return dataset.sort_values(RAW_DATASET_SORT_COLUMNS).reset_index(drop=True)


def sort_final_dataset(dataset: pd.DataFrame) -> pd.DataFrame:
    return dataset.sort_values(FINAL_DATASET_SORT_COLUMNS).reset_index(drop=True)


def write_raw_dataset(dataset: pd.DataFrame, output_path: Path) -> pd.DataFrame:
    ordered = sort_raw_dataset(dataset)
    ordered.to_parquet(output_path, index=False)
    return ordered


def export_final_dataset(dataset: pd.DataFrame) -> pd.DataFrame:
    exported = dataset.copy()
    if "fecha" in exported.columns:
        exported["fecha"] = pd.to_datetime(exported["fecha"])

    exported = exported[
        (exported["anio"] >= FINAL_EXPORT_START_YEAR) & (exported["ambito"].astype(str) == "parados")
    ].copy()
    exported = exported.drop(columns=["fecha", "ambito"])
    exported = exported.rename(columns={"valor": FINAL_VALUE_COLUMN})

    exported["anio"] = exported["anio"].astype("int16")
    exported["mes"] = exported["mes"].astype("int8")
    exported["codigo_ocupacion"] = exported["codigo_ocupacion"].astype("string")
    exported["subgrupo_ocupacion"] = exported["subgrupo_ocupacion"].astype("string")
    exported["sexo"] = exported["sexo"].astype("category")
    exported[FINAL_VALUE_COLUMN] = exported[FINAL_VALUE_COLUMN].astype("int64")
    exported["archivo_origen"] = exported["archivo_origen"].astype("string")
    exported["hoja_origen"] = exported["hoja_origen"].astype("string")
    return sort_final_dataset(exported)


def write_final_dataset(dataset: pd.DataFrame, output_path: Path) -> pd.DataFrame:
    exported = export_final_dataset(dataset)
    exported.to_parquet(output_path, index=False)
    return exported


def read_dataset(path: Path) -> pd.DataFrame:
    dataset = pd.read_parquet(path)
    if "fecha" in dataset.columns:
        dataset["fecha"] = pd.to_datetime(dataset["fecha"])
    return dataset


def read_existing_periods(path: Path) -> set[pd.Timestamp]:
    if not path.exists():
        return set()
    dataset = pd.read_parquet(path)
    if "fecha" in dataset.columns:
        return {
            pd.Timestamp(value).normalize()
            for value in pd.to_datetime(dataset["fecha"]).dropna().unique().tolist()
        }
    if {"anio", "mes"}.issubset(dataset.columns):
        periods = pd.to_datetime(
            {
                "year": dataset["anio"].astype(int),
                "month": dataset["mes"].astype(int),
                "day": 1,
            }
        )
        return {pd.Timestamp(value).normalize() for value in periods.dropna().unique().tolist()}
    raise ValueError(f"No se pudieron inferir periodos desde {path}")


def latest_period(periods: set[pd.Timestamp]) -> pd.Timestamp | None:
    return max(periods) if periods else None


def transform_sheet(path: Path, item: MonthlyWorkbook, sheet_name: str) -> pd.DataFrame:
    sheet_df = pd.read_excel(path, sheet_name=sheet_name, header=None)
    header_row = detect_header_row(sheet_df)
    metric_names = parse_metric_names(sheet_df, header_row)

    records: list[dict[str, object]] = []
    for _, row in sheet_df.iloc[header_row + 1 :].iterrows():
        raw_label = normalize_text(row.iloc[1] if len(row) > 1 else "")
        if not raw_label:
            continue
        if "total grupo de ocupacion" in raw_label.lower():
            continue

        parsed = extract_numeric_code(raw_label)
        if parsed is None:
            continue

        codigo_ocupacion, subgrupo_ocupacion = parsed
        raw_values = [row.iloc[col_idx] if col_idx < len(row) else None for col_idx in metric_names]
        if all(pd.isna(value) or normalize_text(value) in {"", "-", "--"} for value in raw_values):
            continue

        for col_idx, metric_name in metric_names.items():
            records.append(
                {
                    "fecha": item.period,
                    "anio": item.year,
                    "mes": item.month,
                    "codigo_ocupacion": codigo_ocupacion,
                    "subgrupo_ocupacion": subgrupo_ocupacion,
                    "sexo": "ambos_sexos",
                    "ambito": metric_name,
                    "valor": coerce_int(row.iloc[col_idx] if col_idx < len(row) else 0),
                    "archivo_origen": path.as_posix(),
                    "hoja_origen": sheet_name,
                }
            )

    if not records:
        raise ValueError(f"No se generaron registros para {path} hoja {sheet_name}")

    result = pd.DataFrame.from_records(records)
    result["fecha"] = pd.to_datetime(result["fecha"])
    result["anio"] = result["anio"].astype("int16")
    result["mes"] = result["mes"].astype("int8")
    result["codigo_ocupacion"] = result["codigo_ocupacion"].astype("string")
    result["subgrupo_ocupacion"] = result["subgrupo_ocupacion"].astype("string")
    result["sexo"] = result["sexo"].astype("category")
    result["ambito"] = result["ambito"].astype("category")
    result["valor"] = result["valor"].astype("int64")
    result["archivo_origen"] = result["archivo_origen"].astype("string")
    result["hoja_origen"] = result["hoja_origen"].astype("string")
    return sort_raw_dataset(result)


def process_workbook(path: Path, item: MonthlyWorkbook) -> pd.DataFrame:
    sheet_name = find_target_sheet(path)
    LOGGER.info("Extrayendo hoja %s de %s", sheet_name, path.name)
    return transform_sheet(path, item, sheet_name)


def download_and_process_workbook(
    item: MonthlyWorkbook,
    raw_dir: Path,
    force_download: bool = False,
) -> pd.DataFrame:
    session = build_session()
    workbook_path = download_workbook(
        session=session,
        item=item,
        raw_dir=raw_dir,
        force_download=force_download,
    )
    return process_workbook(workbook_path, item)


def process_workbooks(
    workbooks: Sequence[MonthlyWorkbook],
    raw_dir: Path,
    force_download: bool = False,
    workers: int | None = None,
) -> pd.DataFrame:
    if not workbooks:
        raise ValueError("No hay libros para procesar.")

    worker_count = workers or min(8, max(2, (os.cpu_count() or 4)))
    LOGGER.info("Procesando %s libros con %s workers.", len(workbooks), worker_count)
    frames: list[pd.DataFrame] = []

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_map = {
            executor.submit(
                download_and_process_workbook,
                item=item,
                raw_dir=raw_dir,
                force_download=force_download,
            ): item
            for item in workbooks
        }
        for future in as_completed(future_map):
            item = future_map[future]
            try:
                frames.append(future.result())
            except Exception as exc:
                raise RuntimeError(
                    f"Fallo procesando {item.year}-{item.month:02d} ({item.workbook_url}): {exc}"
                ) from exc

    dataset = pd.concat(frames, ignore_index=True)
    return sort_raw_dataset(dataset)


def combine_raw_datasets(existing: pd.DataFrame | None, new_data: pd.DataFrame) -> pd.DataFrame:
    frames = [frame for frame in [existing, new_data] if frame is not None and not frame.empty]
    combined = pd.concat(frames, ignore_index=True)
    combined["fecha"] = pd.to_datetime(combined["fecha"])
    combined = combined.drop_duplicates(subset=RAW_DATASET_KEY_COLUMNS, keep="last")
    return sort_raw_dataset(combined)


def combine_final_datasets(existing: pd.DataFrame | None, new_data: pd.DataFrame) -> pd.DataFrame:
    frames = [frame for frame in [existing, new_data] if frame is not None and not frame.empty]
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=FINAL_DATASET_KEY_COLUMNS, keep="last")
    return sort_final_dataset(combined)


def split_workbooks_into_blocks(
    workbooks: Sequence[MonthlyWorkbook],
    block_years: int,
) -> list[tuple[int, int, list[MonthlyWorkbook]]]:
    years = sorted({item.year for item in workbooks})
    blocks: list[tuple[int, int, list[MonthlyWorkbook]]] = []

    for index in range(0, len(years), block_years):
        block_year_list = years[index : index + block_years]
        block_start = block_year_list[0]
        block_end = block_year_list[-1]
        block_items = [item for item in workbooks if block_start <= item.year <= block_end]
        blocks.append((block_start, block_end, block_items))

    return blocks


def block_output_path(tmp_dir: Path, prefix: str, block_start: int, block_end: int) -> Path:
    return tmp_dir / f"{prefix}_{block_start}_{block_end}.parquet"


def block_file_is_complete(path: Path, workbooks: Sequence[MonthlyWorkbook]) -> bool:
    if not path.exists():
        return False

    expected_periods = {item.period.normalize() for item in workbooks}
    saved_periods = read_existing_periods(path)
    return expected_periods.issubset(saved_periods)


def build_blocks_dataframe(
    workbooks: Sequence[MonthlyWorkbook],
    raw_dir: Path,
    tmp_dir: Path,
    force_download: bool = False,
    workers: int | None = None,
    block_years: int = 5,
    temp_prefix: str = "sepe_demandas_ocupacion",
) -> pd.DataFrame:
    if not workbooks:
        raise ValueError("No hay libros para construir bloques.")

    tmp_dir.mkdir(parents=True, exist_ok=True)
    block_paths: list[Path] = []

    for block_start, block_end, block_items in split_workbooks_into_blocks(workbooks, block_years):
        path = block_output_path(tmp_dir, temp_prefix, block_start, block_end)
        if block_file_is_complete(path, block_items):
            LOGGER.info("Reutilizando bloque %s", path)
        else:
            LOGGER.info(
                "Procesando bloque %s-%s con %s meses.",
                block_start,
                block_end,
                len(block_items),
            )
            block_df = process_workbooks(
                workbooks=block_items,
                raw_dir=raw_dir,
                force_download=force_download,
                workers=workers,
            )
            write_raw_dataset(block_df, path)
        block_paths.append(path)

    frames = [read_dataset(path) for path in block_paths]
    combined = pd.concat(frames, ignore_index=True)
    return sort_raw_dataset(combined)


def log_publication_status(
    available_workbooks: Sequence[MonthlyWorkbook],
    existing_periods: set[pd.Timestamp],
) -> list[MonthlyWorkbook]:
    LOGGER.info("Comprobando si el SEPE ha publicado nuevos datos o faltan meses locales.")

    available_periods = {item.period.normalize() for item in available_workbooks}
    latest_remote = latest_period(available_periods)
    latest_local = latest_period(existing_periods)

    if latest_remote is not None:
        LOGGER.info("Ultimo mes publicado por el SEPE: %s", latest_remote.strftime("%Y-%m"))
    if latest_local is not None:
        LOGGER.info("Ultimo mes presente en el parquet: %s", latest_local.strftime("%Y-%m"))

    missing = [
        item for item in available_workbooks if item.period.normalize() not in existing_periods
    ]
    if missing:
        LOGGER.info("Se han detectado %s meses pendientes de incorporar.", len(missing))
    else:
        LOGGER.info("El parquet ya esta al dia con los meses publicados por el SEPE.")
    return missing


def sync_dataset(
    output_path: Path | str = DEFAULT_OUTPUT_PATH,
    raw_dir: Path | str = DEFAULT_RAW_DIR,
    tmp_dir: Path | str = DEFAULT_TMP_DIR,
    start_year: int | None = None,
    end_year: int | None = None,
    force_download: bool = False,
    workers: int | None = None,
    block_years: int = 5,
    rebuild_full: bool = False,
) -> pd.DataFrame:
    output_path = Path(output_path)
    raw_dir = Path(raw_dir)
    tmp_dir = Path(tmp_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    session = build_session()
    available_workbooks = discover_workbooks(
        session=session,
        start_year=start_year,
        end_year=end_year,
    )
    if not available_workbooks:
        raise RuntimeError("No se localizaron libros Excel para descargar.")

    if rebuild_full or not output_path.exists():
        LOGGER.info("Se construira el historico por bloques y se unira automaticamente.")
        eligible_workbooks = [item for item in available_workbooks if is_export_eligible_workbook(item)]
        dataset = build_blocks_dataframe(
            workbooks=eligible_workbooks,
            raw_dir=raw_dir,
            tmp_dir=tmp_dir,
            force_download=force_download,
            workers=workers,
            block_years=block_years,
            temp_prefix="sepe_demandas_ocupacion",
        )
        dataset = write_final_dataset(dataset, output_path)
        LOGGER.info("Dataset guardado en %s con %s filas", output_path, len(dataset))
        return dataset

    existing_periods = read_existing_periods(output_path)
    eligible_workbooks = [item for item in available_workbooks if is_export_eligible_workbook(item)]
    missing_workbooks = log_publication_status(eligible_workbooks, existing_periods)
    if not missing_workbooks:
        return read_dataset(output_path)

    existing_dataset = read_dataset(output_path)
    if len(missing_workbooks) > block_years * 12:
        LOGGER.info(
            "La puesta al dia es grande; se procesara automaticamente por bloques temporales."
        )
        new_data = build_blocks_dataframe(
            workbooks=missing_workbooks,
            raw_dir=raw_dir,
            tmp_dir=tmp_dir,
            force_download=force_download,
            workers=workers,
            block_years=block_years,
            temp_prefix="sepe_demandas_ocupacion_pendiente",
        )
    else:
        LOGGER.info("Se incorporaran los meses nuevos directamente al parquet.")
        new_data = process_workbooks(
            workbooks=missing_workbooks,
            raw_dir=raw_dir,
            force_download=force_download,
            workers=workers,
        )

    exported_new_data = export_final_dataset(new_data)
    updated_dataset = combine_final_datasets(existing_dataset, exported_new_data)
    updated_dataset = sort_final_dataset(updated_dataset)
    updated_dataset.to_parquet(output_path, index=False)
    LOGGER.info("Dataset actualizado en %s con %s filas", output_path, len(updated_dataset))
    return updated_dataset


def build_dataset(
    output_path: Path | str = DEFAULT_OUTPUT_PATH,
    raw_dir: Path | str = DEFAULT_RAW_DIR,
    start_year: int | None = None,
    end_year: int | None = None,
    force_download: bool = False,
    workers: int | None = None,
) -> pd.DataFrame:
    return sync_dataset(
        output_path=output_path,
        raw_dir=raw_dir,
        start_year=start_year,
        end_year=end_year,
        force_download=force_download,
        workers=workers,
        rebuild_full=True,
    )


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Descarga y transforma estadisticas de demandas de empleo del SEPE."
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Ruta del parquet de salida.",
    )
    parser.add_argument(
        "--raw-dir",
        default=str(DEFAULT_RAW_DIR),
        help="Directorio donde se guardan los Excel descargados.",
    )
    parser.add_argument(
        "--tmp-dir",
        default=str(DEFAULT_TMP_DIR),
        help="Directorio para bloques parquet temporales.",
    )
    parser.add_argument("--start-year", type=int, default=None, help="Ano minimo a procesar.")
    parser.add_argument("--end-year", type=int, default=None, help="Ano maximo a procesar.")
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Vuelve a descargar los Excel aunque ya existan en disco.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Numero de workers paralelos para descargar y transformar libros.",
    )
    parser.add_argument(
        "--block-years",
        type=int,
        default=5,
        help="Tamano de los bloques de anos para reconstrucciones largas.",
    )
    parser.add_argument(
        "--rebuild-full",
        action="store_true",
        help="Reconstruye el historico completo por bloques, ignorando el parquet actual.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Activa logs detallados.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    configure_logging(verbose=args.verbose)
    sync_dataset(
        output_path=args.output,
        raw_dir=args.raw_dir,
        tmp_dir=args.tmp_dir,
        start_year=args.start_year,
        end_year=args.end_year,
        force_download=args.force_download,
        workers=args.workers,
        block_years=args.block_years,
        rebuild_full=args.rebuild_full,
    )


if __name__ == "__main__":
    main()
