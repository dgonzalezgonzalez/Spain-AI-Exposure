from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA_PATH = Path("data/sepe_demandas_ocupacion_long.parquet")

st.set_page_config(
    page_title="SEPE Demandas por Ocupación",
    page_icon="📊",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["fecha"] = pd.to_datetime(
        {
            "year": df["anio"].astype(int),
            "month": df["mes"].astype(int),
            "day": 1,
        }
    )
    df["subgrupo_label"] = (
        df["codigo_ocupacion"].astype(str) + " - " + df["subgrupo_ocupacion"].astype(str)
    )
    return df


st.title("Parados registrados del SEPE por subgrupo de ocupación")
st.caption(
    "Fuente: libros mensuales 'Libro completo' del SEPE, hoja de demandas pendientes "
    "por subgrupo principal de ocupación para ambos sexos. El parquet final exporta "
    "solo la serie de parados registrados desde 2011."
)

if not DATA_PATH.exists():
    st.error(
        "No existe `data/sepe_demandas_ocupacion_long.parquet`. "
        "Ejecuta `python run_pipeline.py` antes de abrir el dashboard."
    )
    st.stop()

df = load_data(str(DATA_PATH))

with st.sidebar:
    st.header("Filtros")
    year_options = sorted(df["anio"].dropna().unique().tolist())
    selected_years = st.multiselect("Año", year_options, default=year_options)

    subgrupo_options = sorted(df["subgrupo_label"].dropna().unique().tolist())
    selected_subgrupos = st.multiselect(
        "Subgrupo de ocupación",
        subgrupo_options,
        default=[],
        placeholder="Todos los subgrupos",
    )

filtered = df[df["anio"].isin(selected_years)].copy()
if selected_subgrupos:
    filtered = filtered[filtered["subgrupo_label"].isin(selected_subgrupos)]

if filtered.empty:
    st.warning("No hay datos para la combinación de filtros actual.")
    st.stop()

monthly = (
    filtered.groupby("fecha", as_index=False)["total de parados registrados"]
    .sum()
    .sort_values("fecha")
    .reset_index(drop=True)
)
monthly["variacion_interanual_pct"] = monthly["total de parados registrados"].pct_change(12) * 100

latest_total = int(monthly["total de parados registrados"].iloc[-1])
latest_date = monthly["fecha"].iloc[-1]
latest_yoy = monthly["variacion_interanual_pct"].iloc[-1]
unique_subgrupos = filtered["codigo_ocupacion"].nunique()

col1, col2, col3 = st.columns(3)
col1.metric("Último total de parados", f"{latest_total:,}".replace(",", "."))
col2.metric("Fecha más reciente", latest_date.strftime("%Y-%m"))
col3.metric(
    "Variación interanual",
    "n/d" if pd.isna(latest_yoy) else f"{latest_yoy:.2f}%",
)

st.subheader("Evolución temporal total")
fig_evolution = px.line(
    monthly,
    x="fecha",
    y="total de parados registrados",
    markers=True,
    title="Evolución mensual de parados registrados",
    labels={"fecha": "Fecha", "total de parados registrados": "Parados registrados"},
)
fig_evolution.update_layout(margin=dict(l=10, r=10, t=50, b=10))
st.plotly_chart(fig_evolution, use_container_width=True)

left, right = st.columns(2)

with left:
    st.subheader("Ranking de subgrupos con más parados")
    ranking = (
        filtered.groupby(["codigo_ocupacion", "subgrupo_ocupacion"], as_index=False)[
            "total de parados registrados"
        ]
        .sum()
        .sort_values("total de parados registrados", ascending=False)
        .head(15)
    )
    ranking["label"] = ranking["codigo_ocupacion"].astype(str) + " - " + ranking[
        "subgrupo_ocupacion"
    ].astype(str)
    fig_ranking = px.bar(
        ranking.sort_values("total de parados registrados", ascending=True),
        x="total de parados registrados",
        y="label",
        orientation="h",
        title="Top 15 subgrupos",
        labels={"total de parados registrados": "Parados registrados", "label": "Subgrupo"},
    )
    fig_ranking.update_layout(margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig_ranking, use_container_width=True)

with right:
    st.subheader("Variación interanual")
    yoy = monthly.dropna(subset=["variacion_interanual_pct"]).copy()
    if yoy.empty:
        st.info("Hace falta al menos un año completo para calcular la variación interanual.")
    else:
        fig_yoy = px.bar(
            yoy,
            x="fecha",
            y="variacion_interanual_pct",
            title="Cambio porcentual frente al mismo mes del año anterior",
            labels={
                "fecha": "Fecha",
                "variacion_interanual_pct": "Variación interanual (%)",
            },
        )
        fig_yoy.update_layout(margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig_yoy, use_container_width=True)

st.subheader("Tabla descargable")
table_df = filtered.sort_values(["anio", "mes", "codigo_ocupacion"]).copy()
st.dataframe(table_df, use_container_width=True, hide_index=True)
st.download_button(
    "Descargar tabla filtrada en CSV",
    data=table_df.to_csv(index=False).encode("utf-8"),
    file_name="sepe_demandas_ocupacion_filtrado.csv",
    mime="text/csv",
)

st.caption(
    f"Filas visibles: {len(table_df):,} | Subgrupos en selección: {unique_subgrupos:,}".replace(
        ",", "."
    )
)
