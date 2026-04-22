from __future__ import annotations

import sys
from pathlib import Path

import branca.colormap as cm
import folium
import geopandas as gpd
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import OUTPUTS_DIR, PROCESSED_DATA_DIR, TABLES_DIR


def build_arrondissement_priority_map(
    master_geojson_path: Path | None = None,
    ranking_csv_path: Path | None = None,
) -> Path:
    """Build the pedagogical arrondissement priority choropleth map.

    La carte est un fichier HTML autonome (aucun serveur requis) qui intègre
    les données GeoJSON, les styles et la bibliothèque Folium/Leaflet en inline.
    Elle peut être ouverte directement dans n'importe quel navigateur.
    """
    master_path = master_geojson_path or PROCESSED_DATA_DIR / "master_arrondissements.geojson"
    ranking_path = ranking_csv_path or TABLES_DIR / "arrondissement_priority_ranking.csv"

    if not master_path.exists():
        raise FileNotFoundError(f"Missing arrondissement master GeoJSON: {master_path}")
    if not ranking_path.exists():
        raise FileNotFoundError(f"Missing arrondissement ranking CSV: {ranking_path}")

    master_gdf = gpd.read_file(master_path)
    ranking_df = pd.read_csv(ranking_path, encoding="utf-8-sig", dtype={"arrondissement_code": "string"})

    master_gdf["arrondissement_code"] = master_gdf["arrondissement_code"].astype(str).str.zfill(2)
    ranking_df["arrondissement_code"] = ranking_df["arrondissement_code"].astype(str).str.zfill(2)

    map_gdf = master_gdf.merge(
        ranking_df[["arrondissement_code", "priority_rank"]],
        on="arrondissement_code",
        how="left",
    )
    if len(map_gdf) != 20:
        raise ValueError("The arrondissement map must contain exactly 20 polygons.")

    # Calcul du centroïde géographique réel de Paris pour centrer la carte,
    # plutôt qu'une coordonnée codée en dur qui deviendrait incorrecte si le GeoJSON change.
    center = map_gdf.to_crs("EPSG:4326").union_all().centroid
    fmap = folium.Map(
        location=[center.y, center.x],
        zoom_start=11,
        # CartoDB positron : fond clair et minimaliste qui ne concurrence pas
        # les couleurs du choropleth.
        tiles="CartoDB positron",
    )

    priority_min = float(map_gdf["priority_score"].min())
    priority_max = float(map_gdf["priority_score"].max())
    # Palette divergente centrée sur 0 :
    #   bleu  (#2B6CB0) = surplus  → le modèle prédit MOINS que l'observé
    #   blanc (#F7FAFC) = neutre   → prédiction proche de l'observé
    #   rouge (#C53030) = déficit  → le modèle prédit PLUS que l'observé
    colormap = cm.LinearColormap(
        colors=["#2B6CB0", "#F7FAFC", "#C53030"],
        vmin=priority_min,
        vmax=priority_max,
    )
    colormap.caption = "Priority Score (predicted - observed bins)"
    colormap.add_to(fmap)

    def style_function(feature: dict) -> dict[str, float | str]:
        priority_score = feature["properties"].get("priority_score")
        # Gris neutre si le score est manquant (ne devrait pas arriver avec 20 arrondissements complets)
        fill_color = "#d9d9d9" if priority_score is None else colormap(priority_score)
        return {
            "fillColor": fill_color,
            "color": "#1f2937",
            "weight": 1.2,
            "fillOpacity": 0.8,
        }

    tooltip = folium.GeoJsonTooltip(
        fields=[
            "arrondissement_code",
            "arrondissement_name",
            "priority_rank",
            "y_bin_count",
            "y_predicted",
            "priority_score",
            "cluster_label",
            "x1_population",
            "x2_commerce_restaurant_count",
            "x3_transport_station_count",
            "x4_green_area_m2",
            "x5_road_length_km",
        ],
        aliases=[
            "Arrondissement code",
            "Arrondissement",
            "Priority rank",
            "Observed bins",
            "Predicted bins",
            "Priority score",
            "Cluster",
            "X1 Population",
            "X2 Commerce/Restaurants",
            "X3 Transport stations",
            "X4 Green area (m2)",
            "X5 Road length (km)",
        ],
        localize=True,
        sticky=False,
        labels=True,
    )

    folium.GeoJson(
        map_gdf,
        style_function=style_function,
        tooltip=tooltip,
        name="Arrondissement priorities",
    ).add_to(fmap)

    output_path = OUTPUTS_DIR / "priority_map.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(output_path)
    return output_path


if __name__ == "__main__":
    result_path = build_arrondissement_priority_map()
    print(f"Map saved to {result_path}")
