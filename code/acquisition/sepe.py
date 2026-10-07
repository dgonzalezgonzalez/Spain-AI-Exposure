from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SEPE_OCCUPATION_PAGE_URL = "https://www.sepe.es/HomeSepe/que-es-observatorio/informacion-mt-por-ocupacion.html"


SEPE_RESULTS_ENDPOINT = (
    "https://www.sepe.es/HomeSepe/que-es-observatorio/"
    "informacion-mt-por-ocupacion/main/04/content/resultados"
)


MONTH_NAME_TO_NUMBER = {
    "enero": "01",
    "febrero": "02",
    "marzo": "03",
    "abril": "04",
    "mayo": "05",
    "junio": "06",
    "julio": "07",
    "agosto": "08",
    "septiembre": "09",
    "octubre": "10",
    "noviembre": "11",
    "diciembre": "12",
}


@dataclass(frozen=True)
class SepeReportLink:
    cno4: str
    occupation_title: str
    period: str
    url: str


def sepe_long_to_compact_wide(long: pd.DataFrame) -> pd.DataFrame:
    index_columns = ["period", "cno4", "occupation_title", "dimension", "category", "gender", "source_url"]
    df = long.copy()
    df["cno4"] = df["cno4"].astype(str).str.zfill(4)
    total_source = df[df["category"] == "Total"].copy()
    total_source = total_source.sort_values(["measure", "dimension"]).drop_duplicates(
        subset=["period", "cno4", "measure"], keep="first"
    )
    total_source["dimension"] = "total"
    total_source["category"] = "Total"
    total_source["gender"] = "Total"
    detail = df[(df["dimension"] != "total") & (df["category"] != "Total")].copy()
    compact_long = pd.concat([detail, total_source], ignore_index=True)
    wide = (
        compact_long.pivot_table(
            index=index_columns,
            columns="measure",
            values="value",
            aggfunc="first",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    for column in ["contratos", "parados", "personas"]:
        if column not in wide.columns:
            wide[column] = pd.NA
    columns = [*index_columns, "contratos", "parados", "personas"]
    return wide[columns].sort_values(["cno4", "period", "dimension", "category", "gender"]).reset_index(drop=True)


def make_sepe_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def discover_sepe_report_links(
    session: requests.Session,
    occupations: pd.DataFrame,
    delay_seconds: float = 0.25,
    max_reports: int | None = None,
) -> list[SepeReportLink]:
    links: list[SepeReportLink] = []
    for _, occupation in occupations.iterrows():
        cno4 = str(occupation["CNO4"])
        page = 1
        while True:
            html = _fetch_detail_page(session, cno4, page)
            page_links = parse_report_links_from_listing(html, cno4)
            links.extend(page_links)
            if max_reports is not None and len(links) >= max_reports:
                return links[:max_reports]
            if not _listing_has_page(html, page + 1):
                break
            page += 1
            if delay_seconds:
                time.sleep(delay_seconds)
        if delay_seconds:
            time.sleep(delay_seconds)
    return links


def parse_report_links_from_listing(html: str, cno4: str) -> list[SepeReportLink]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[SepeReportLink] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        if "informacion-mercado-trabajo-por-ocupacion" not in href or "_mensuales_" not in href:
            continue
        row = anchor.find_parent("tr")
        if row is None:
            continue
        cells = [normalize_text(cell.get_text(" ", strip=True)) for cell in row.find_all("td")]
        if len(cells) < 2:
            continue
        month = MONTH_NAME_TO_NUMBER.get(cells[0].lower())
        year = re.search(r"\d{4}", cells[1])
        if not month or not year:
            continue
        title = _title_from_listing(soup, cno4)
        links.append(
            SepeReportLink(
                cno4=cno4,
                occupation_title=title,
                period=f"{year.group(0)}-{month}",
                url=urljoin(SEPE_OCCUPATION_PAGE_URL, href),
            )
        )
    return links


def _listing_has_page(html: str, page: int) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a"):
        if normalize_text(anchor.get_text(" ", strip=True)) == str(page):
            href = str(anchor.get("href", ""))
            if "page-pr=" in href:
                return True
    return False


def parse_sepe_report_html(html: str, source_url: str = "") -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    cno4, title, period = _report_identity(soup, source_url)
    rows: list[dict[str, object]] = []

    for measure, value in _parse_banner_totals(soup).items():
        rows.append(_row(cno4, title, period, measure, "total", "Total", value, source_url))

    for table in soup.find_all("table"):
        caption = normalize_text(table.find("caption").get_text(" ", strip=True) if table.find("caption") else "")
        caption_l = caption.lower()
        if caption_l == "parados según sexo y edad":
            rows.extend(_parse_gender_age_table(table, cno4, title, period, "parados", source_url))
        elif caption_l == "contratos según sexo y edad":
            rows.extend(_parse_gender_age_table(table, cno4, title, period, "contratos", source_url))
        elif caption_l == "distribución geográfica de parados":
            rows.extend(_parse_province_table(table, cno4, title, period, "parados", source_url))
        elif caption_l == "distribución geográfica de contratos":
            rows.extend(_parse_province_table(table, cno4, title, period, "contratos", source_url))
        elif caption_l == "movilidad geográfica de la contratación":
            rows.extend(_parse_mobility_total_table(table, cno4, title, period, source_url))

    rows.extend(_parse_mobility_gender_script(soup, cno4, title, period, source_url))
    return rows


def _fetch_detail_page(session: requests.Session, cno4: str, page: int) -> str:
    if page == 1:
        response = session.post(
            SEPE_RESULTS_ENDPOINT,
            data={"list-mode": "detail", "ocupacion-id": cno4, "year-busc": "", "month-busc": ""},
            timeout=(10, 25),
        )
    else:
        response = session.get(
            SEPE_RESULTS_ENDPOINT,
            params={"list-mode": "detail", "ocupacion-id": cno4, "page-pr": page},
            timeout=(10, 25),
        )
    response.raise_for_status()
    return response.text


def fetch_cached_report(session: requests.Session, raw_dir: Path, link: SepeReportLink, refresh: bool = False) -> str:
    path = raw_dir / "reports" / f"{link.cno4}_{link.period}.html"
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    response = session.get(link.url, timeout=(10, 25))
    response.raise_for_status()
    path.write_text(response.text, encoding="utf-8")
    return response.text


def _parse_gender_age_table(
    table,
    cno4: str,
    title: str,
    period: str,
    measure: str,
    source_url: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    section = ""
    for tr in table.find_all("tr"):
        cells = [normalize_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["td", "th"])]
        if not cells:
            continue
        first = cells[0].lower()
        if first == "por sexo":
            section = "gender"
            continue
        if first == "por tramos de edad":
            section = "age"
            continue
        if first in {"", "total", "variación (1)", "mensual"} and len(cells) < 2:
            continue
        value = parse_number(cells[1] if len(cells) > 1 else "")
        if value is None:
            continue
        if section == "gender":
            rows.append(_row(cno4, title, period, measure, "gender", cells[0], value, source_url, gender=cells[0]))
        elif section == "age":
            rows.append(_row(cno4, title, period, measure, "age", cells[0], value, source_url))
    return rows


def _parse_province_table(
    table,
    cno4: str,
    title: str,
    period: str,
    measure: str,
    source_url: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for tr in table.find_all("tr"):
        cells = [normalize_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["td", "th"])]
        if len(cells) < 2 or cells[0].lower() in {"", "provincia"}:
            continue
        value = parse_number(cells[1])
        if value is not None:
            rows.append(_row(cno4, title, period, measure, "province", cells[0], value, source_url))
    total = sum(float(row["value"]) for row in rows)
    rows.append(_row(cno4, title, period, measure, "province", "Total", total, source_url))
    return rows


def _parse_mobility_total_table(table, cno4: str, title: str, period: str, source_url: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for tr in table.find_all("tr"):
        cells = [normalize_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        label = cells[0]
        if label.lower().startswith("nº de contratos que permanecen"):
            category = "Permanecen"
        elif label.lower().startswith("nº de contratos que se mueven"):
            category = "Se mueven"
        else:
            continue
        value = parse_number(cells[1])
        if value is not None:
            rows.append(_row(cno4, title, period, "contratos", "geographic_mobility", category, value, source_url))
    if rows:
        rows.append(
            _row(
                cno4,
                title,
                period,
                "contratos",
                "geographic_mobility",
                "Total",
                sum(float(row["value"]) for row in rows),
                source_url,
            )
        )
    return rows


def _parse_mobility_gender_script(soup, cno4: str, title: str, period: str, source_url: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for script in soup.find_all("script"):
        text = script.get_text("\n")
        if "drawStuffMovilidad" not in text:
            continue
        genders = re.findall(r"addColumn\('number', '([^']+)'\)", text)
        for match in re.finditer(r"addRow\(\['([^']+)'\s*,\s*([^\]]+)\]\)", text):
            category = normalize_text(match.group(1))
            values = [parse_number(value) for value in match.group(2).split(",")]
            for gender, value in zip(genders, values):
                if value is not None:
                    rows.append(
                        _row(
                            cno4,
                            title,
                            period,
                            "contratos",
                            "geographic_mobility",
                            category,
                            value,
                            source_url,
                            gender=gender,
                        )
                    )
        break
    return rows


def _parse_banner_totals(soup) -> dict[str, float]:
    totals: dict[str, float] = {}
    for title in soup.find_all("h4", class_="se-databanner--title"):
        title_text = normalize_text(title.get_text(" ", strip=True)).lower()
        banner = title.find_parent(class_="se-databanner")
        if banner is None:
            continue
        figures = banner.find_all("p", class_="se-databanner--figure")
        if "parados" in title_text:
            value = _first_banner_figure_value(figures)
            if value is not None:
                totals["parados"] = value
        elif "contratos" in title_text:
            for figure in figures:
                figure_text = normalize_text(figure.get_text(" ", strip=True)).lower()
                digit = figure.find(class_="se-databanner--digit")
                value = parse_number(digit.get_text(" ", strip=True) if digit else "")
                if value is None:
                    continue
                if "personas" in figure_text:
                    totals["personas"] = value
                elif "contratos" in figure_text:
                    totals["contratos"] = value
    return totals


def _first_banner_figure_value(figures) -> float | None:
    for figure in figures:
        digit = figure.find(class_="se-databanner--digit")
        value = parse_number(digit.get_text(" ", strip=True) if digit else "")
        if value is not None:
            return value
    return None


def _report_identity(soup, source_url: str) -> tuple[str, str, str]:
    heading = ""
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = normalize_text(tag.get_text(" ", strip=True))
        if text.startswith("CNO-"):
            heading = text
            break
    match = re.search(r"CNO-(\d{4}):\s+(.+?)\s+([A-Za-zÁÉÍÓÚáéíóúñ]+)\s+(\d{4})$", heading)
    if match:
        cno4, title, month_name, year = match.groups()
        month = MONTH_NAME_TO_NUMBER[month_name.lower()]
        return cno4, title, f"{year}-{month}"
    url_match = re.search(r"_mensuales_(\d{4})_(\d{2})_(\d{4})-", source_url)
    if url_match:
        year, month, cno4 = url_match.groups()
        return cno4, "", f"{year}-{month}"
    raise ValueError("Could not parse SEPE report identity.")


def _title_from_listing(soup, cno4: str) -> str:
    heading = soup.find("h3")
    text = normalize_text(heading.get_text(" ", strip=True) if heading else "")
    match = re.search(rf"CNO-{re.escape(cno4)}:\s+(.+)$", text)
    return match.group(1) if match else ""


def _row(
    cno4: str,
    title: str,
    period: str,
    measure: str,
    dimension: str,
    category: str,
    value: float,
    source_url: str,
    gender: str = "Total",
) -> dict[str, object]:
    return {
        "period": period,
        "cno4": str(cno4).zfill(4),
        "occupation_title": title,
        "measure": measure,
        "dimension": dimension,
        "category": category,
        "gender": gender,
        "value": value,
        "source_url": source_url,
    }


def parse_number(text: str) -> float | None:
    cleaned = normalize_text(str(text)).replace("%", "").replace(".", "").replace(",", ".")
    cleaned = re.sub(r"[^\d.\-]", "", cleaned)
    if cleaned in {"", "-", "."}:
        return None
    return float(cleaned)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()

