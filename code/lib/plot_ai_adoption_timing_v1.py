"""Produce the two panels documenting the timing of AI adoption in Spain."""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "raw" / "spain_ai_adoption_timing_sources.csv"
OUTPUT_DIR = ROOT / "rendered"

BLUE = "#0B5AA5"
SKY_BLUE = "#8EC9EE"
GRAY = "#6B7280"
GRID = "#D9DEE5"
TEXT = "#252A31"

RELEASE = pd.Timestamp("2022-11-01")
ADJUSTMENT_END = pd.Timestamp("2024-11-30")
LATER_END = pd.Timestamp("2026-03-31")
X_MIN = pd.Timestamp("2021-01-01")
X_MAX = pd.Timestamp("2026-04-01")


def _style_axis(ax: plt.Axes, y_max: float, y_ticks: list[float]) -> None:
    ax.axvspan(RELEASE, ADJUSTMENT_END, color=SKY_BLUE, alpha=0.16, zorder=0)
    ax.axvspan(ADJUSTMENT_END, LATER_END, color=GRAY, alpha=0.09, zorder=0)
    ax.axvline(RELEASE, color=GRAY, linestyle=(0, (3, 2)), linewidth=1.0, zorder=1)

    ax.text(
        RELEASE + (ADJUSTMENT_END - RELEASE) / 2,
        y_max * 0.955,
        "Adjustment",
        ha="center",
        va="top",
        fontsize=8,
        color=GRAY,
    )
    ax.text(
        ADJUSTMENT_END + (LATER_END - ADJUSTMENT_END) / 2,
        y_max * 0.955,
        "Later period",
        ha="center",
        va="top",
        fontsize=8,
        color=GRAY,
    )
    ax.annotate(
        "ChatGPT release",
        xy=(RELEASE, 0),
        xytext=(4, 5),
        textcoords="offset points",
        rotation=90,
        ha="left",
        va="bottom",
        fontsize=7.5,
        color=GRAY,
    )

    ax.set_xlim(X_MIN, X_MAX)
    ax.set_ylim(0, y_max)
    ax.set_yticks(y_ticks)
    ax.set_ylabel("Percent", color=TEXT)
    ax.set_xlabel("Year", color=TEXT)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.grid(axis="x", visible=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRAY)
    ax.spines["bottom"].set_color(GRAY)
    ax.tick_params(colors=TEXT, labelsize=8)


def _label_points(
    ax: plt.Axes, data: pd.DataFrame, color: str, y_max: float
) -> None:
    for row in data.itertuples(index=False):
        high_point = row.value_percent >= 0.80 * y_max
        ax.annotate(
            f"{row.value_percent:g}%",
            (row.date, row.value_percent),
            xytext=(0, -14 if high_point else 7),
            textcoords="offset points",
            ha="center",
            va="top" if high_point else "bottom",
            fontsize=8,
            color=color,
        )


def _save(fig: plt.Figure, stem: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_DIR / f"{stem}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def build_figures() -> None:
    data = pd.read_csv(DATA_FILE, parse_dates=["date"])

    firm = data.loc[data["series_id"].eq("firm_ict")].sort_values("date")
    ebae = data.loc[data["series_id"].eq("firm_ebae")]
    fig, ax = plt.subplots(figsize=(6.3, 3.25))
    _style_axis(ax, y_max=24, y_ticks=[0, 5, 10, 15, 20])
    ax.plot(
        firm["date"],
        firm["value_percent"],
        color=BLUE,
        linewidth=1.6,
        marker="o",
        markersize=4.8,
        label="INE/Eurostat ICT survey",
        zorder=3,
    )
    ax.scatter(
        ebae["date"],
        ebae["value_percent"],
        color=GRAY,
        marker="D",
        s=31,
        label="Banco de Espana EBAE",
        zorder=3,
    )
    _label_points(ax, firm, BLUE, y_max=24)
    _label_points(ax, ebae, GRAY, y_max=24)
    ax.legend(loc="upper left", frameon=False, fontsize=8, handlelength=2.2)
    fig.tight_layout(pad=0.5)
    _save(fig, "figure_ai_adoption_timing_panelA")

    people = data.loc[data["series_id"].eq("chatgpt_frequent")].sort_values("date")
    fig, ax = plt.subplots(figsize=(6.3, 3.25))
    _style_axis(ax, y_max=32, y_ticks=[0, 5, 10, 15, 20, 25, 30])
    ax.plot(
        people["date"],
        people["value_percent"],
        color=BLUE,
        linewidth=1.6,
        marker="o",
        markersize=4.8,
        zorder=3,
    )
    _label_points(ax, people, BLUE, y_max=32)
    fig.tight_layout(pad=0.5)
    _save(fig, "figure_ai_adoption_timing_panelB")


if __name__ == "__main__":
    build_figures()
