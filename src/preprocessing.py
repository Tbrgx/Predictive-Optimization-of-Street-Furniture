from __future__ import annotations

import geopandas as gpd
import pandas as pd

from config import CRS_TARGET


def ensure_target_crs(geodf: gpd.GeoDataFrame, target_crs: str = CRS_TARGET) -> gpd.GeoDataFrame:
    """Return a GeoDataFrame projected in the target CRS.

    Appelé systématiquement avant chaque opération spatiale pour prévenir les
    erreurs silencieuses de superposition de couches dans des systèmes de
    coordonnées incompatibles (ex. mélange WGS84 / Lambert-93).
    Lever une erreur explicite si le CRS est absent est préférable à une
    reprojection silencieuse incorrecte.
    """
    if geodf.crs is None:
        raise ValueError("Input GeoDataFrame has no CRS defined.")
    if str(geodf.crs) == target_crs:
        return geodf.copy()
    return geodf.to_crs(target_crs)


def build_arrondissement_boundaries_from_iris(iris_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Dissolve Paris IRIS polygons into the 20 arrondissement boundaries.

    Les contours d'arrondissements ne sont pas téléchargés comme couche externe.
    Ils sont **reconstruits** par dissolution des ~992 IRIS parisiens, ce qui :
    - évite d'introduire une source de données supplémentaire ;
    - garantit la cohérence topologique parfaite avec les IRIS utilisés pour
      les jointures spatiales (pas de micro-gaps ni d'overlaps aux frontières).

    La validation stricte (exactement 20 lignes, codes 01–20, pas de géométrie
    nulle) détecte toute anomalie de la source IGN avant qu'elle ne se propage
    silencieusement dans le pipeline.
    """
    iris = ensure_target_crs(iris_gdf)
    iris["code_insee"] = iris["code_insee"].astype(str).str.zfill(5)
    iris["nom_commune"] = iris["nom_commune"].astype(str)

    arr_gdf = (
        iris[["code_insee", "nom_commune", "geometry"]]
        .dissolve(by=["code_insee", "nom_commune"], as_index=False)
        .rename(columns={"nom_commune": "arrondissement_name"})
    )
    # Les 2 derniers chiffres du code INSEE correspondent au numéro d'arrondissement :
    # 75101 → "01", 75115 → "15", 75120 → "20"
    arr_gdf["arrondissement_code"] = arr_gdf["code_insee"].str[-2:]
    arr_gdf = arr_gdf[["arrondissement_code", "arrondissement_name", "code_insee", "geometry"]]
    arr_gdf = arr_gdf.sort_values("arrondissement_code").reset_index(drop=True)

    expected_codes = {f"{idx:02d}" for idx in range(1, 21)}
    observed_codes = set(arr_gdf["arrondissement_code"])
    if len(arr_gdf) != 20 or observed_codes != expected_codes:
        raise ValueError(
            "Arrondissement boundaries are invalid: expected 20 rows with codes 01-20."
        )
    if arr_gdf.geometry.isna().any() or arr_gdf.geometry.is_empty.any():
        raise ValueError("Arrondissement boundaries contain null or empty geometries.")

    return arr_gdf


def aggregate_points_to_arrondissement(
    points_gdf: gpd.GeoDataFrame,
    arr_gdf: gpd.GeoDataFrame,
    value_name: str,
) -> pd.DataFrame:
    """Spatially join points to arrondissements and count rows per arrondissement.

    Le prédicat `within` (point strictement à l'intérieur du polygone) est plus
    robuste que `intersects` pour les points ponctuels, car il évite de compter
    un point positionné exactement sur une frontière dans deux arrondissements.
    """
    if points_gdf.empty:
        return pd.DataFrame(columns=["arrondissement_code", value_name])

    points = ensure_target_crs(points_gdf)
    arr = ensure_target_crs(arr_gdf)
    joined = gpd.sjoin(
        points,
        arr[["arrondissement_code", "geometry"]],
        how="left",
        predicate="within",
    )
    aggregated = (
        joined.groupby("arrondissement_code")
        .size()
        .rename(value_name)
        .reset_index()
    )
    return aggregated


def aggregate_lines_length_to_arrondissement(
    lines_gdf: gpd.GeoDataFrame,
    arr_gdf: gpd.GeoDataFrame,
    value_name: str,
) -> pd.DataFrame:
    """Intersect lines with arrondissements and sum their length in kilometers.

    Contrairement aux points, les routes traversent souvent plusieurs arrondissements.
    `gpd.overlay` découpe chaque tronçon aux frontières avant le calcul de longueur,
    ce qui attribue à chaque arrondissement uniquement la portion qui lui appartient.

    La reprojection en Lambert-93 (EPSG:2154) est obligatoire avant `.length` :
    en WGS84 (degrés), `.length` renverrait des valeurs en degrés décimaux,
    sans signification métrique. Lambert-93 est la projection officielle pour la
    France métropolitaine et minimise les distorsions à l'échelle parisienne.

    `keep_geom_type=False` permet de conserver les fragments MultiLineString
    qui peuvent apparaître après découpe aux frontières d'arrondissement.
    """
    if lines_gdf.empty:
        return pd.DataFrame(columns=["arrondissement_code", value_name])

    lines = ensure_target_crs(lines_gdf)
    arr = ensure_target_crs(arr_gdf)
    intersections = gpd.overlay(
        lines[["geometry"]],
        arr[["arrondissement_code", "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    if intersections.empty:
        return pd.DataFrame(columns=["arrondissement_code", value_name])

    # Reprojection Lambert-93 pour des longueurs en mètres
    intersections_l93 = intersections.to_crs("EPSG:2154")
    intersections[value_name] = intersections_l93.geometry.length / 1_000  # mètres → km
    aggregated = (
        intersections.groupby("arrondissement_code", as_index=False)[value_name]
        .sum()
    )
    return aggregated


def aggregate_green_area_to_arrondissement(
    green_gdf: gpd.GeoDataFrame,
    arr_gdf: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Intersect green spaces with arrondissements and sum area in square meters.

    Même principe que `aggregate_lines_length_to_arrondissement` mais pour les
    surfaces. Un parc qui chevauche plusieurs arrondissements (ex. Bois de
    Vincennes entre 12e et communes limitrophes) est découpé et la surface
    comptée uniquement dans la portion parisienne concernée.

    La reprojection Lambert-93 est obligatoire avant `.area` pour les mêmes
    raisons que pour les longueurs (voir fonction précédente).
    """
    if green_gdf.empty:
        return pd.DataFrame(columns=["arrondissement_code", "x4_green_area_m2"])

    green = ensure_target_crs(green_gdf)
    arr = ensure_target_crs(arr_gdf)
    intersections = gpd.overlay(
        green[["geometry"]],
        arr[["arrondissement_code", "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    if intersections.empty:
        return pd.DataFrame(columns=["arrondissement_code", "x4_green_area_m2"])

    # Reprojection Lambert-93 pour des surfaces en m²
    intersections_l93 = intersections.to_crs("EPSG:2154")
    intersections["x4_green_area_m2"] = intersections_l93.geometry.area
    aggregated = (
        intersections.groupby("arrondissement_code", as_index=False)["x4_green_area_m2"]
        .sum()
    )
    return aggregated


def build_master_arrondissements(
    arr_gdf: gpd.GeoDataFrame,
    bins_gdf: gpd.GeoDataFrame,
    population_df: pd.DataFrame,
    commerce_gdf: gpd.GeoDataFrame,
    transport_gdf: gpd.GeoDataFrame,
    green_gdf: gpd.GeoDataFrame,
    roads_gdf: gpd.GeoDataFrame,
    terrasses_df: pd.DataFrame,
    schools_df: pd.DataFrame,
) -> gpd.GeoDataFrame:
    """Build the arrondissement-level pedagogical feature table.

    8 jointures LEFT JOIN successives sur `arrondissement_code`. Le LEFT JOIN
    garantit que les 20 arrondissements sont toujours présents même si une source
    ne couvre pas un arrondissement (ex. absence de données terrasses pour
    un arrondissement). Les NaN résultants sont remplis à 0.

    Les types sont forcés explicitement après l'assemblage pour éviter que les
    NaN intermédiaires (float par défaut en pandas) ne corrompent les colonnes
    de comptage entier (y_bin_count, x2, x3, x7).
    """
    arr = ensure_target_crs(arr_gdf).copy()

    bins_counts = aggregate_points_to_arrondissement(bins_gdf, arr, "y_bin_count")
    commerce_counts = aggregate_points_to_arrondissement(
        commerce_gdf,
        arr,
        "x2_commerce_restaurant_count",
    )
    transport_counts = aggregate_points_to_arrondissement(
        transport_gdf,
        arr,
        "x3_transport_station_count",
    )
    green_area = aggregate_green_area_to_arrondissement(green_gdf, arr)
    road_length = aggregate_lines_length_to_arrondissement(
        roads_gdf,
        arr,
        "x5_road_length_km",
    )

    master = arr.merge(population_df, on="arrondissement_code", how="left")
    master = master.merge(bins_counts, on="arrondissement_code", how="left")
    master = master.merge(commerce_counts, on="arrondissement_code", how="left")
    master = master.merge(transport_counts, on="arrondissement_code", how="left")
    master = master.merge(green_area, on="arrondissement_code", how="left")
    master = master.merge(road_length, on="arrondissement_code", how="left")
    master = master.merge(terrasses_df, on="arrondissement_code", how="left")
    master = master.merge(schools_df, on="arrondissement_code", how="left")

    fill_zero_columns = [
        "x1_population",
        "y_bin_count",
        "x2_commerce_restaurant_count",
        "x3_transport_station_count",
        "x4_green_area_m2",
        "x5_road_length_km",
        "x6_terrasse_surface_m2",
        "x7_school_count",
    ]
    for column in fill_zero_columns:
        master[column] = pd.to_numeric(master[column], errors="coerce").fillna(0.0)

    # Forçage des types : les comptages discrets doivent être des entiers
    integer_columns = [
        "y_bin_count",
        "x2_commerce_restaurant_count",
        "x3_transport_station_count",
        "x7_school_count",
    ]
    for column in integer_columns:
        master[column] = master[column].round().astype(int)

    master["x1_population"] = master["x1_population"].astype(float)
    master["x4_green_area_m2"] = master["x4_green_area_m2"].astype(float)
    master["x5_road_length_km"] = master["x5_road_length_km"].astype(float)
    master["x6_terrasse_surface_m2"] = master["x6_terrasse_surface_m2"].astype(float)

    expected_columns = [
        "arrondissement_code",
        "arrondissement_name",
        "geometry",
        "y_bin_count",
        "x1_population",
        "x2_commerce_restaurant_count",
        "x3_transport_station_count",
        "x4_green_area_m2",
        "x5_road_length_km",
        "x6_terrasse_surface_m2",
        "x7_school_count",
    ]
    master = master[expected_columns].sort_values("arrondissement_code").reset_index(drop=True)
    return master
