from __future__ import annotations

from typing import Optional

import folium
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def plot_distribution(
    data: pd.DataFrame,
    column: str,
    bins: int = 30,
    figsize: tuple[int, int] = (8, 5),
) -> plt.Axes:
    """Plot a univariate distribution for a numeric column."""
    fig, ax = plt.subplots(figsize=figsize)
    sns.histplot(data=data, x=column, bins=bins, kde=True, ax=ax)
    ax.set_title(f"Distribution of {column}")
    return ax


def plot_missing_values(
    data: pd.DataFrame,
    figsize: tuple[int, int] = (10, 5),
) -> plt.Axes:
    """Plot the missing-value ratio for each column."""
    missing_ratio = data.isna().mean().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=figsize)
    sns.barplot(x=missing_ratio.index, y=missing_ratio.values, ax=ax)
    ax.set_ylabel("Missing ratio")
    ax.set_xlabel("Columns")
    ax.tick_params(axis="x", rotation=90)
    ax.set_title("Missing values by column")
    return ax


def plot_choropleth(
    geodf: gpd.GeoDataFrame,
    column: str,
    cmap: str = "YlOrRd",
    figsize: tuple[int, int] = (10, 10),
) -> plt.Axes:
    """Render a static choropleth map from a GeoDataFrame."""
    fig, ax = plt.subplots(figsize=figsize)
    geodf.plot(column=column, cmap=cmap, legend=True, ax=ax, edgecolor="black", linewidth=0.2)
    ax.set_axis_off()
    ax.set_title(f"Choropleth - {column}")
    return ax


def make_folium_map(
    geodf: gpd.GeoDataFrame,
    column: str,
    tooltip_columns: Optional[list[str]] = None,
    map_location: tuple[float, float] = (48.8566, 2.3522),
    zoom_start: int = 11,
) -> folium.Map:
    """Create an interactive folium choropleth-ready map."""
    tooltip_fields = tooltip_columns or [column]
    fmap = folium.Map(location=map_location, zoom_start=zoom_start, tiles="CartoDB positron")

    folium.GeoJson(
        geodf,
        tooltip=folium.GeoJsonTooltip(fields=tooltip_fields),
        style_function=lambda _: {
            "fillColor": "#3186cc",
            "color": "#1f1f1f",
            "weight": 0.4,
            "fillOpacity": 0.5,
        },
    ).add_to(fmap)

    return fmap
