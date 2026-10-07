# Source cell 1
from pathlib import Path
from urllib.request import urlretrieve

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path.cwd()
while PROJECT_ROOT != PROJECT_ROOT.parent and not (PROJECT_ROOT / "data").is_dir():
    PROJECT_ROOT = PROJECT_ROOT.parent
if not (PROJECT_ROOT / "data").is_dir():
    raise FileNotFoundError("Could not locate the package directory containing data/.")
RAW_DIR = PROJECT_ROOT / "data" / "raw"
TABLES_DIR = PROJECT_ROOT / "uploads" / "figuresNtables"
FIGURES_DIR = PROJECT_ROOT / "uploads" / "figuresNtables"

SEPE_PATH = RAW_DIR / "sepe_cno4_monthly_ai_exposure.csv"
EPA_PATH = RAW_DIR / "epa_unemployment_microdata_weights.csv"


TABLES_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

SEPE_PATH, EPA_PATH


# Source cell 3
if not EPA_PATH.exists():
    raise FileNotFoundError("Frozen EPA unemployment weights are missing.")

print(f"EPA file: {EPA_PATH}")
print(f"SEPE file: {SEPE_PATH}")


# Source cell 4
def parse_spanish_number(value):
    """Parse INE/Spanish numeric strings such as '2.708,6' into floats."""
    if pd.isna(value):
        return np.nan
    text = str(value).strip()
    if text == "":
        return np.nan
    return float(text.replace(".", "").replace(",", "."))


def quarter_to_timestamp(q):
    """Convert strings like '2026T1' to quarter-end pandas timestamps."""
    year = int(str(q)[:4])
    quarter = int(str(q).split("T")[1])
    month = quarter * 3
    return pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)


def load_epa_unemployed(path=EPA_PATH):
    # Exact public survey-weight vintage underlying the manuscript check.
    weights = pd.read_csv(path, dtype={"quarter": "string", "AOI": "string"})
    if not weights["AOI"].str.zfill(2).isin(["05", "06"]).all():
        raise ValueError("EPA extract contains non-unemployment classifications.")
    epa = weights.groupby("quarter", as_index=False)["FACTOREL"].sum()
    epa = epa.rename(columns={"FACTOREL": "epa_unemployed_persons"})
    epa["epa_unemployed_thousands"] = epa["epa_unemployed_persons"] / 1000
    epa["quarter"] = epa["quarter"].str.replace("Q", "T")
    epa["date"] = epa["quarter"].map(quarter_to_timestamp)
    return epa.sort_values("date")


def load_sepe_registered_unemployed_quarterly(path=SEPE_PATH):
    usecols = ["period", "cno4", "dimension", "category", "gender", "parados"]
    chunks = []
    for chunk in pd.read_csv(path, usecols=usecols, dtype={"cno4": "string"}, chunksize=500_000):
        keep = (
            chunk["dimension"].eq("total")
            & chunk["category"].eq("Total")
            & chunk["gender"].eq("Total")
            & chunk["cno4"].str.len().eq(4)
        )
        sub = chunk.loc[keep, ["period", "cno4", "parados"]].copy()
        if not sub.empty:
            chunks.append(sub)
    sepe = pd.concat(chunks, ignore_index=True)
    sepe["parados"] = pd.to_numeric(sepe["parados"], errors="coerce")
    monthly = sepe.groupby("period", as_index=False)["parados"].sum()
    monthly["date"] = pd.to_datetime(monthly["period"] + "-01")

    quarterly = monthly.set_index("date")["parados"].resample("QE").mean().reset_index()
    quarterly["quarter"] = quarterly["date"].dt.year.astype(str) + "T" + quarterly["date"].dt.quarter.astype(str)
    quarterly = quarterly.rename(columns={"parados": "sepe_registered_unemployed_persons"})
    quarterly["sepe_registered_unemployed_millions"] = quarterly["sepe_registered_unemployed_persons"] / 1_000_000
    return quarterly[["quarter", "date", "sepe_registered_unemployed_persons", "sepe_registered_unemployed_millions"]]


epa_q = load_epa_unemployed()
sepe_q = load_sepe_registered_unemployed_quarterly()

validation = sepe_q.merge(epa_q, on=["quarter", "date"], how="inner")
validation["epa_unemployed_millions"] = validation["epa_unemployed_persons"] / 1_000_000
validation["sepe_minus_epa_millions"] = validation["sepe_registered_unemployed_millions"] - validation["epa_unemployed_millions"]
validation["sepe_to_epa_ratio"] = validation["sepe_registered_unemployed_persons"] / validation["epa_unemployed_persons"]

validation.head()


# Source cell 5
table_path = TABLES_DIR / "table_epa_vs_sepe_unemployment_quarterly.csv"
validation.to_csv(table_path, index=False)

summary = validation[["epa_unemployed_millions", "sepe_registered_unemployed_millions", "sepe_minus_epa_millions", "sepe_to_epa_ratio"]].describe()
corr = validation["epa_unemployed_millions"].corr(validation["sepe_registered_unemployed_millions"])

print(f"Saved table: {table_path}")
print(f"Correlation between EPA and SEPE series: {corr:.3f}")
summary


# Source cell 7
# Publication style approved for the manuscript; source values are unchanged.
with plt.rc_context({"font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.axisbelow": True}):
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    x = validation["date"].dt.to_period("Q").dt.to_timestamp()
    ax.plot(x, validation["epa_unemployed_millions"], color="#08519C",
            linewidth=1.5, label="EPA unemployed")
    ax.plot(x, validation["sepe_registered_unemployed_millions"], color="#56B4E9",
            linewidth=1.5, label="SEPE registered unemployed")
    ax.set_ylabel("Millions of persons")
    ax.set_xlabel("")
    ax.grid(axis="y", color="#9AA4AD", alpha=0.22, linewidth=0.7)
    ax.legend(frameon=False, loc="upper right", fontsize=8)
    fig.tight_layout()
    figure_path = FIGURES_DIR / "epa_vs_sepe_unemployment_quarterly.png"
    fig.savefig(figure_path, dpi=320, bbox_inches="tight")
    plt.close(fig)
print(f"Saved figure: {figure_path}")


# Source cell 9
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path.cwd()
while PROJECT_ROOT != PROJECT_ROOT.parent and not (PROJECT_ROOT / "data").is_dir():
    PROJECT_ROOT = PROJECT_ROOT.parent
if not (PROJECT_ROOT / "data").is_dir():
    raise FileNotFoundError("Could not locate the package directory containing data/.")
CSV_PATH = PROJECT_ROOT / "data" / "raw" / "anthropic_job_exposure_onet.csv"

df = pd.read_csv(CSV_PATH)

unique_titles = df["title"].nunique(dropna=True)
unique_codes = df["occ_code"].nunique(dropna=True)

print(f"Rows in file: {len(df)}")
print(f"Unique occupations by title: {unique_titles}")
print(f"Unique occupations by OCC code: {unique_codes}")

df[["occ_code", "title"]].drop_duplicates().head()


# Source cell 11
from pathlib import Path

PROJECT_ROOT = Path.cwd()
while PROJECT_ROOT != PROJECT_ROOT.parent and not (PROJECT_ROOT / "data").is_dir():
    PROJECT_ROOT = PROJECT_ROOT.parent
if not (PROJECT_ROOT / "data").is_dir():
    raise FileNotFoundError("Could not locate the package directory containing data/.")
FIGURES_DIR = PROJECT_ROOT / "uploads" / "figuresNtables"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

FIGURE_PATH = FIGURES_DIR / "figure_ai_exposure_distribution_onet_vs_spain.png"

US_PATH = PROJECT_ROOT / "data" / "raw" / "anthropic_job_exposure_onet.csv"
SPAIN_PATH = PROJECT_ROOT / "data" / "raw" / "sepe_cno4_monthly_ai_exposure.csv"
us = pd.read_csv(US_PATH)
spain = pd.read_csv(SPAIN_PATH, dtype={"cno4": str})
us_series = pd.to_numeric(us["observed_exposure"], errors="coerce").dropna()
spain_series = (
    spain[["cno4", "observed_exposure_cosine_nearest"]]
    .drop_duplicates("cno4")["observed_exposure_cosine_nearest"]
    .pipe(pd.to_numeric, errors="coerce")
    .dropna()
)
bins = np.linspace(0, 1, 31)

fig, ax = plt.subplots(figsize=(8.0, 4.8))

# Compute histogram counts manually
us_counts, bin_edges = np.histogram(us_series, bins=bins)
spain_counts, _ = np.histogram(spain_series, bins=bins)

bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
bin_width = bin_edges[1] - bin_edges[0]

# Draw bars: US (wider, blue) then Spain (narrower, red) on top
ax.bar(
    bin_centers,
    us_counts,
    width=bin_width * 0.7,
    alpha=0.65,
    label="O*NET occupations",
    color="#2166ac",
)
ax.bar(
    bin_centers,
    spain_counts,
    width=bin_width * 0.5,
    alpha=0.80,
    label="Spain mapped occupations",
    color="#b2182b",
)

ax.set_xlabel("AI exposure")
ax.set_ylabel("Count")
ax.set_xlim(0, 1)
ax.legend(frameon=False, loc="upper right")
ax.grid(axis="y", alpha=0.25)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
fig.tight_layout()
fig.savefig(FIGURE_PATH, dpi=220, bbox_inches="tight")
plt.close("all")

print(f"Figure saved to: {FIGURE_PATH}")


# Source cell 13
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path.cwd()
while PROJECT_ROOT != PROJECT_ROOT.parent and not (PROJECT_ROOT / "data").is_dir():
    PROJECT_ROOT = PROJECT_ROOT.parent
if not (PROJECT_ROOT / "data").is_dir():
    raise FileNotFoundError("Could not locate the package directory containing data/.")
RAW_DIR = PROJECT_ROOT / "data" / "raw"
TABLES_DIR = PROJECT_ROOT / "uploads" / "figuresNtables"
TABLES_DIR.mkdir(parents=True, exist_ok=True)

US_PATH = RAW_DIR / "anthropic_job_exposure_onet.csv"
SPAIN_PATH = RAW_DIR / "sepe_cno4_monthly_ai_exposure.csv"
OUTPUT_PATH = TABLES_DIR / "table_top_bottom_exposure_appendix.tex"


def escape_latex(text):
    if pd.isna(text):
        return ""
    text = str(text)
    return text.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("#", r"\#")


SPANISH_TO_ENGLISH = {
    "Programadores informáticos": "Computer programmers",
    "Grabadores de datos": "Data entry clerks",
    "Agentes y representantes comerciales": "Sales agents and commercial representatives",
    "Analistas financieros": "Financial analysts",
    "Analistas y diseñadores de software y multimedia no clasificados bajo otros epígrafes": "Software and multimedia analysts and designers",
    "Empleados de oficina de servicios estadísticos, financieros y bancarios": "Statistical, financial, and banking office clerks",
    "Especialistas en bases de datos y en redes informáticas no clasificados bajo otros epígrafes": "Database and network specialists",
    "Técnicos de la web": "Web technicians",
    "Técnicos en asistencia al usuario de tecnologías de la información": "IT user-support technicians",
    "Profesionales de relaciones públicas": "Public relations professionals",
    "Oficiales de las fuerzas armadas": "Military officers",
    "Suboficiales de las fuerzas armadas": "Non-commissioned military officers",
    "Tropa y marinería de las fuerzas armadas": "Military enlisted personnel",
    "Miembros del poder ejecutivo (nacional, autonómico y local) y del poder legislativo": "Members of the executive and legislative branches",
    "Personal directivo de la administración pública": "Public administration executive staff",
    "Directores de recursos humanos": "Human resources directors",
    "Directores de producción de explotaciones agrarias": "Agricultural production directors",
}


def translate_occupation(text):
    if pd.isna(text):
        return ""
    text = str(text)
    return SPANISH_TO_ENGLISH.get(text, text)


def make_combined_table_tex(spain_df, us_df, top_n=10, bottom_n=10):
    spain_top = spain_df.nlargest(top_n, "exposure").copy().sort_values("exposure", ascending=False)
    spain_bottom = spain_df.nsmallest(bottom_n, "exposure").copy().sort_values("exposure", ascending=True)

    us_top = us_df.nlargest(top_n, "exposure").copy().sort_values("exposure", ascending=False)
    us_bottom = us_df.nsmallest(bottom_n, "exposure").copy().sort_values("exposure", ascending=True)

    top_rows = []
    for (_, spain_row), (_, us_row) in zip(spain_top.iterrows(), us_top.iterrows()):
        spain_title = translate_occupation(spain_row["occupation_description"])
        us_title = translate_occupation(us_row["occupation_description"])
        row = (
            f"{escape_latex(spain_row['code'])} & {escape_latex(spain_title)} & {spain_row['exposure']:.3f} & "
            f"{escape_latex(us_row['code'])} & {escape_latex(us_title)} & {us_row['exposure']:.3f} \\\\"
        )
        top_rows.append(row)

    bottom_rows = []
    for (_, spain_row), (_, us_row) in zip(spain_bottom.iterrows(), us_bottom.iterrows()):
        spain_title = translate_occupation(spain_row["occupation_description"])
        us_title = translate_occupation(us_row["occupation_description"])
        row = (
            f"{escape_latex(spain_row['code'])} & {escape_latex(spain_title)} & {spain_row['exposure']:.3f} & "
            f"{escape_latex(us_row['code'])} & {escape_latex(us_title)} & {us_row['exposure']:.3f} \\\\"
        )
        bottom_rows.append(row)

    top_panel = "\n".join(top_rows)
    bottom_panel = "\n".join(bottom_rows)

    template = r"""\begin{{table}}[H]
\centering
\caption{{Top and bottom {top_n} AI-exposure occupations in Spain and the global average}}
\label{{tab:top_bottom_exposure_comparison}}

\footnotesize

\begin{{adjustbox}}{{max width=\linewidth}}
\begin{{tabular}}{{
  l
  >{{\raggedright\arraybackslash}}p{{4.8cm}}
  r
  l
  >{{\raggedright\arraybackslash}}p{{7.0cm}}
  r
}}
\toprule
\multicolumn{{3}}{{c}}{{Spain (CNO4)}} &
\multicolumn{{3}}{{c}}{{Global average (O*NET)}} \\
\cmidrule(lr){{1-3}}
\cmidrule(lr){{4-6}}
Code & Occupation & Exposure &
Code & Occupation & Exposure \\
\midrule

\multicolumn{{6}}{{c}}{{\textbf{{Panel A. Top {top_n} occupations}}}} \\
\midrule

{top_panel}
\midrule
\multicolumn{{6}}{{c}}{{\textbf{{Panel B. Bottom {bottom_n} occupations}}}} \\
\midrule

{bottom_panel}
\bottomrule
\end{{tabular}}
\end{{adjustbox}}

\vspace{{0.25cm}}

\begin{{minipage}}{{1\linewidth}}
\footnotesize
\textit{{Notes:}} The table reports the ten occupations with the highest and lowest AI exposure after mapping the Anthropic AI exposure measure to Spanish CNO4d occupations. U.S. occupations correspond to the original Anthropic ranking.

\smallskip

\textit{{Source:}} Own calculations based on SEPE, O*NET, and \citet{{anthropic_2026_labor_market}}.
\end{{minipage}}

\end{{table}}
"""

    return template.format(
        top_n=top_n,
        bottom_n=bottom_n,
        top_panel=top_panel,
        bottom_panel=bottom_panel,
    )


us_df = pd.read_csv(US_PATH)
us_df = us_df[["occ_code", "title", "observed_exposure"]].dropna(subset=["observed_exposure"]).copy()
us_df["exposure"] = pd.to_numeric(us_df["observed_exposure"], errors="coerce")
us_df = us_df.dropna(subset=["exposure"]).rename(columns={"occ_code": "code", "title": "occupation_description"})

spain_df = pd.read_csv(
    SPAIN_PATH,
    usecols=["cno4", "occupation_title", "dimension", "category", "gender", "observed_exposure_cosine_nearest"],
    dtype={"cno4": "string"},
)
spain_keep = (
    spain_df["dimension"].eq("total")
    & spain_df["category"].eq("Total")
    & spain_df["gender"].eq("Total")
)
spain_df = spain_df.loc[spain_keep, ["cno4", "occupation_title", "observed_exposure_cosine_nearest"]].copy()
spain_df["exposure"] = pd.to_numeric(spain_df["observed_exposure_cosine_nearest"], errors="coerce")
spain_df = spain_df.dropna(subset=["exposure"]).rename(columns={"cno4": "code", "occupation_title": "occupation_description"})
spain_df = spain_df.groupby(["code", "occupation_description"], as_index=False)["exposure"].mean()

combined_tex = make_combined_table_tex(spain_df, us_df)

OUTPUT_PATH.write_text(combined_tex, encoding="utf-8")

print(f"Saved combined LaTeX table to: {OUTPUT_PATH}")
print("\n--- Preview ---")
print(combined_tex[:1500])


# Source cell 15
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path.cwd()
while PROJECT_ROOT != PROJECT_ROOT.parent and not (PROJECT_ROOT / "data").is_dir():
    PROJECT_ROOT = PROJECT_ROOT.parent
if not (PROJECT_ROOT / "data").is_dir():
    raise FileNotFoundError("Could not locate the package directory containing data/.")
RAW_DIR = PROJECT_ROOT / "data" / "raw"
TABLES_DIR = PROJECT_ROOT / "uploads" / "figuresNtables"
TABLES_DIR.mkdir(parents=True, exist_ok=True)

SEPE_PATH = RAW_DIR / "sepe_cno4_monthly_ai_exposure.csv"
OUTPUT_PATH = TABLES_DIR / "summary_statistics.tex"

sepe = pd.read_csv(
    SEPE_PATH,
    dtype={"cno4": "string"},
)

keep = (
    sepe["dimension"].eq("total")
    & sepe["category"].eq("Total")
    & sepe["gender"].eq("Total")
)
sepe = sepe.loc[keep].copy()

numeric_cols = [
    "parados",
    "contratos",
    "observed_exposure_cosine_nearest",
    "observed_exposure_cosine_weighted",
    ]
for col in numeric_cols:
    sepe[col] = pd.to_numeric(sepe[col], errors="coerce")

sepe["log_parados"] = np.where(sepe["parados"] > 0, np.log(sepe["parados"]), np.nan)
sepe["log_contratos"] = np.where(sepe["contratos"] > 0, np.log(sepe["contratos"]), np.nan)

rows = [
    ("Registered unemployed (in levels)", "parados", False),
    ("New registered contracts (in levels)", "contratos", False),
    ("Registered unemployed (in logs)", "log_parados", False),
    ("New registered contracts (in logs)", "log_contratos", False),
    ("AI exposure index", None, True),  # Section header
    ("AI index - cosine similarity", "observed_exposure_cosine_nearest", False),
    ("AI index - cosine-weighted", "observed_exposure_cosine_weighted", False),
]

def format_number(val, digits=3):
    """Format number with thousands separator."""
    if np.isnan(val):
        return "0.000"
    return f"{val:,.{digits}f}"

def format_obs_count(val):
    """Format observation count with thousands separator."""
    return f"{val:,}"

summary_lines = []

# Add "Outcomes" header row first
summary_lines.append("\\textbf{Outcomes} & & & & & \\\\\n")

# Add outcomes variables
for label in ["Registered unemployed (in levels)", "New registered contracts (in levels)",
              "Registered unemployed (in logs)", "New registered contracts (in logs)"]:
    col = {"Registered unemployed (in levels)": "parados",
           "New registered contracts (in levels)": "contratos",
           "Registered unemployed (in logs)": "log_parados",
           "New registered contracts (in logs)": "log_contratos"}[label]

    series = sepe[col]
    mean = series.mean(skipna=True)
    sd = series.std(skipna=True, ddof=1)
    mn = series.min(skipna=True)
    mx = series.max(skipna=True)
    nobs = int(series.count())

    digits = 0 if "in levels" in label else 3
    summary_lines.append(
        f"\\hspace{{0.3cm}} {label} & {format_number(mean, digits)} & {format_number(sd, digits)} & {format_number(mn, digits)} & {format_number(mx, digits)} & {format_obs_count(nobs)} \\\\\n"
    )

# Add "AI exposure index" header row
summary_lines.append("\\textbf{AI exposure index} & & & & & \\\\\n")

# Add AI exposure variables
for label, col in [("AI index - cosine similarity", "observed_exposure_cosine_nearest"),
                   ("AI index - cosine-weighted", "observed_exposure_cosine_weighted")]:
    series = sepe[col]
    mean = series.mean(skipna=True)
    sd = series.std(skipna=True, ddof=1)
    mn = series.min(skipna=True)
    mx = series.max(skipna=True)
    nobs = int(series.count())

    summary_lines.append(
        f"\\hspace{{0.3cm}} {label} & {format_number(mean)} & {format_number(sd)} & {format_number(mn)} & {format_number(mx)} & {format_obs_count(nobs)} \\\\\n"
    )

body = "".join(summary_lines)

tex = r"""\begin{table}[H]
\centering
\begin{threeparttable}
\caption{Summary statistics for SEPE occupation-level variables and AI exposure indices}
\label{tab:summary_statistics}
\footnotesize
\begin{tabular}{lrrrrr}
\toprule
 & Mean & SD & Min & Max & Obs. \\
\midrule
{body}\bottomrule
\end{tabular}
\begin{tablenotes}[flushleft]
\footnotesize
\item \emph{Notes:} Labor-market data come from SEPE. The occupation-level AI exposure measures map Anthropic/O*NET occupations to four-digit occupations in the Spanish National Classification of Occupations 2011 (CNO-11).
\end{tablenotes}
\end{threeparttable}
\end{table}
"""

OUTPUT_PATH.write_text(tex.replace("{body}", body), encoding="utf-8")

print(f"Saved summary statistics table to: {OUTPUT_PATH}")
print("\n--- Preview ---")
print(tex.replace("{body}", body))


# Source cell 17
# Package installation is handled outside the reproducibility script.


# Source cell 18
from pathlib import Path
import re

import pandas as pd

# Robust import for PdfReader: prefer `pypdf`, fallback to `PyPDF2`.
try:
    from pypdf import PdfReader
except Exception:
    try:
        from PyPDF2 import PdfReader
    except Exception:
        raise ImportError("PdfReader not found. Install 'pypdf' or 'PyPDF2'.")

PROJECT_ROOT = Path.cwd()
while PROJECT_ROOT != PROJECT_ROOT.parent and not (PROJECT_ROOT / "data").is_dir():
    PROJECT_ROOT = PROJECT_ROOT.parent
if not (PROJECT_ROOT / "data").is_dir():
    raise FileNotFoundError("Could not locate the package directory containing data/.")

SEPE_PATH = PROJECT_ROOT / "data" / "raw" / "sepe_cno4_monthly_ai_exposure.csv"
PDF_PATH = PROJECT_ROOT / "data" / "raw" / "cno11_notas.pdf"
OUT_PATH = PROJECT_ROOT / "uploads" / "figuresNtables" / "table_cno4_pdf_vs_sepe_codes.csv"

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# 1. Read CNO4 codes from SEPE, preserving leading zeros.
sepe_codes = {}

for chunk in pd.read_csv(
    SEPE_PATH,
    usecols=["cno4", "occupation_title"],
    dtype={"cno4": "string"},
    chunksize=500_000,
):
    chunk["cno4"] = chunk["cno4"].str.zfill(4)

    for code, title in (
        chunk[["cno4", "occupation_title"]]
        .dropna()
        .drop_duplicates()
        .itertuples(index=False)
    ):
        sepe_codes.setdefault(code, title)

sepe_df = (
    pd.DataFrame(
        [{"cno4": code, "sepe_title": title} for code, title in sepe_codes.items()]
    )
    .sort_values("cno4")
    .reset_index(drop=True)
)

# 2. Extract CNO4 codes from the official CNO-11 PDF.
reader = PdfReader(str(PDF_PATH))
pdf_rows = []

for page_num, page in enumerate(reader.pages, start=1):
    text = page.extract_text() or ""

    for line in text.splitlines():
        line = line.strip()
        match = re.match(r"^(\d{4})\s+(.+)", line)

        if match:
            pdf_rows.append(
                {
                    "cno4": match.group(1),
                    "pdf_title_line": match.group(2).strip(),
                    "pdf_page": page_num,
                }
            )

pdf_df = (
    pd.DataFrame(pdf_rows)
    .drop_duplicates(subset=["cno4"])
    .sort_values("cno4")
    .reset_index(drop=True)
)

# 3. Compare both sources.
comparison = pdf_df.merge(sepe_df, on="cno4", how="outer", indicator=True)
comparison["in_pdf"] = comparison["_merge"].isin(["both", "left_only"])
comparison["in_sepe"] = comparison["_merge"].isin(["both", "right_only"])
comparison = comparison.drop(columns=["_merge"])

missing_from_sepe = comparison.loc[
    comparison["in_pdf"] & ~comparison["in_sepe"],
    ["cno4", "pdf_title_line", "pdf_page"],
]

missing_from_pdf = comparison.loc[
    comparison["in_sepe"] & ~comparison["in_pdf"],
    ["cno4", "sepe_title"],
]

comparison.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")

print(f"CNO4 codes in SEPE CSV: {sepe_df['cno4'].nunique()}")
print(f"CNO4 codes in CNO-11 PDF: {pdf_df['cno4'].nunique()}")
print(f"Missing from SEPE CSV: {len(missing_from_sepe)}")
print(f"Missing from CNO-11 PDF: {len(missing_from_pdf)}")
print(f"Saved comparison table to: {OUT_PATH}")

missing_from_sepe
missing_from_pdf


# Source cell 20
from pathlib import Path
import urllib.request

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path.cwd()
while PROJECT_ROOT != PROJECT_ROOT.parent and not (PROJECT_ROOT / "data").is_dir():
    PROJECT_ROOT = PROJECT_ROOT.parent
if not (PROJECT_ROOT / "data").is_dir():
    raise FileNotFoundError("Could not locate the package directory containing data/.")
RAW_DIR = PROJECT_ROOT / "data" / "raw"
TABLES_DIR = PROJECT_ROOT / "uploads" / "figuresNtables"
FIGURES_DIR = PROJECT_ROOT / "uploads" / "figuresNtables"

RAW_DIR.mkdir(parents=True, exist_ok=True)
TABLES_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

AEI_URL = "https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/release_2026_06_26/data/aei_claude_ai_2026-06-26.csv"
AEI_RAW_PATH = RAW_DIR / "anthropic_aei_claude_ai_2026-06-26.csv"
FILTERED_PATH = TABLES_DIR / "table_anthropic_country_soc_major_group_spain_global_may2026.csv"
FIGURE_PATH = FIGURES_DIR / "figure_anthropic_country_soc_major_group_spain_global_may2026.png"

# Download the raw Anthropic Economic Index release if it is not already present.
if not AEI_RAW_PATH.exists():
    urllib.request.urlretrieve(AEI_URL, AEI_RAW_PATH)

usecols = [
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
]

pieces = []
for chunk in pd.read_csv(AEI_RAW_PATH, usecols=usecols, chunksize=500_000):
    keep = (
        chunk["date_start"].eq("2026-05-01")
        & chunk["date_end"].eq("2026-06-01")
        & ((chunk["geo_id"].eq("ESP") & chunk["geo_level"].eq("country"))
           | (chunk["geo_id"].eq("GLOBAL") & chunk["geo_level"].eq("global")))
        & chunk["category_name"].eq("soc_occupation")
        & chunk["hierarchy_level"].eq(1)
        & chunk["metric_id"].eq("pct")
    )
    sub = chunk.loc[keep].copy()
    if not sub.empty:
        pieces.append(sub)

spain_global_soc = pd.concat(pieces, ignore_index=True)

plot_df = (
    spain_global_soc
    .pivot_table(index=["node_external_id", "node_name"], columns="geo_id", values="value", aggfunc="first")
    .reset_index()
    .sort_values(["ESP", "node_external_id"], ascending=[False, True], kind="stable")
)
plot_df["Difference (p.p.)"] = plot_df["ESP"] - plot_df["GLOBAL"]
plot_df = plot_df.rename(columns={"node_name": "Job group", "ESP": "Spain (%)", "GLOBAL": "Global average (%)"})
plot_df.to_csv(FILTERED_PATH, index=False)

x = np.arange(len(plot_df))
height = 0.42

fig, ax = plt.subplots(figsize=(8.5, 6.0))
ax.barh(
    x - height / 2,
    plot_df["Spain (%)"],
    height,
    label="Spain",
    color="#b2182b",
)
ax.barh(
    x + height / 2,
    plot_df["Global average (%)"],
    height,
    label="Global average",
    color="#2166ac",
)

ax.set_xlabel("Percent of Claude usage")
ax.set_ylabel("")
ax.set_yticks(x)
ax.set_yticklabels(plot_df["Job group"], fontsize=9)
ax.invert_yaxis()
ax.legend(frameon=False, ncol=2, loc="lower right")
ax.grid(axis="x", alpha=0.25)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
fig.tight_layout()
fig.savefig(FIGURE_PATH, dpi=220, bbox_inches="tight")
plt.close("all")

print(f"Saved filtered table: {FILTERED_PATH}")
print(f"Saved figure: {FIGURE_PATH}")

print(plot_df)


# Source cell 22
from lib.plot_ai_adoption_timing_v1 import build_figures

build_figures()
print("Created figure_ai_adoption_timing_panelA and panelB (PNG).")

# Source cell 24

descriptive_outputs = sorted(
    path for path in (PROJECT_ROOT / "uploads" / "figuresNtables").iterdir()
    if path.is_file() and (
        path.name.startswith("figure_")
        or path.name in {"summary_statistics.tex", "table_top_bottom_exposure_appendix.tex"}
    )
)
pd.DataFrame(
    [{"file": path.name, "bytes": path.stat().st_size} for path in descriptive_outputs]
).to_csv(PROJECT_ROOT / "intermediate" / "descriptive_artifact_manifest_v1.csv", index=False)
print(f"Descriptive stage complete: {len(descriptive_outputs)} publication artifacts.")
print("Next: run 03_Estimates.do.")
