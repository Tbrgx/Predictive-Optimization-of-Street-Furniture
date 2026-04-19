from __future__ import annotations

import json
import time
import unicodedata
import zipfile
from pathlib import Path
from typing import Any, Optional, Union

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString, shape

from config import CRS_TARGET, DATA_SOURCES, PEDAGOGICAL_DATASET_NAMES, RAW_DATA_DIR


LoadedDataset = Union[pd.DataFrame, gpd.GeoDataFrame, dict[str, Any]]


def normalize_text(value: Any) -> str:
    """Normalize text to ASCII for robust rule-based filtering."""
    if pd.isna(value):
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def _resolve_dataset_path(name: str, dataset_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolve a raw dataset path from its configured name."""
    source = DATA_SOURCES[name]
    return Path(dataset_path) if dataset_path is not None else RAW_DATA_DIR / source["local_filename"]


def download_dataset(
    name: str,
    url: str,
    save_path: Union[str, Path],
    file_format: str = "csv",
    method: str = "GET",
    params: Optional[dict[str, Any]] = None,
    data: Optional[Union[str, bytes]] = None,
    headers: Optional[dict[str, str]] = None,
    timeout_seconds: int = 60,
) -> Path:
    """Download a dataset from a URL and persist it locally."""
    destination = Path(save_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    response = requests.request(
        method=method.upper(),
        url=url,
        params=params,
        data=data,
        headers=headers,
        stream=True,
        timeout=timeout_seconds,
    )
    response.raise_for_status()

    with destination.open("wb") as file_handle:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file_handle.write(chunk)

    return destination


def download_all_datasets(
    dataset_names: Optional[list[str]] = None,
    force: bool = False,
) -> dict[str, Path]:
    """Download the requested configured datasets."""
    requested_names = dataset_names or list(DATA_SOURCES.keys())
    downloaded_paths: dict[str, Path] = {}

    for name in requested_names:
        if name not in DATA_SOURCES:
            raise KeyError(f"Unknown dataset '{name}'.")

        source = DATA_SOURCES[name]
        if source.get("status") == "blocked":
            continue

        destination = RAW_DATA_DIR / source["local_filename"]
        if destination.exists() and not force:
            downloaded_paths[name] = destination
            continue

        attempts = int(source.get("retry_attempts", 1))
        delay_seconds = int(source.get("retry_delay_seconds", 0))
        timeout_seconds = int(source.get("timeout_seconds", 60))
        method = source.get("request_method", "GET")
        params = source.get("request_params")
        data = source.get("request_data")
        headers = source.get("request_headers")

        last_error: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            try:
                downloaded_paths[name] = download_dataset(
                    name=name,
                    url=source["url"],
                    save_path=destination,
                    file_format=source.get("file_format", "csv"),
                    method=method,
                    params=params,
                    data=data,
                    headers=headers,
                    timeout_seconds=timeout_seconds,
                )
                last_error = None
                break
            except requests.RequestException as exc:
                last_error = exc
                if attempt < attempts and delay_seconds > 0:
                    time.sleep(delay_seconds)

        if last_error is not None:
            fallback_url = source.get("fallback_url")
            if fallback_url:
                downloaded_paths[name] = download_dataset(
                    name=name,
                    url=fallback_url,
                    save_path=destination,
                    file_format=source.get("file_format", "csv"),
                    method="GET",
                    timeout_seconds=timeout_seconds,
                )
            else:
                raise last_error

    return downloaded_paths


def download_pedagogical_datasets(
    dataset_names: Optional[list[str]] = None,
    force: bool = False,
) -> dict[str, Path]:
    """Download the primary datasets for the arrondissement pedagogical pipeline."""
    requested = dataset_names or PEDAGOGICAL_DATASET_NAMES
    return download_all_datasets(dataset_names=requested, force=force)


def parse_overpass_points(json_path: Union[str, Path]) -> gpd.GeoDataFrame:
    """Convert an Overpass JSON response into a point GeoDataFrame in EPSG:4326."""
    json_file = Path(json_path)
    with json_file.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)

    rows: list[dict[str, Any]] = []
    for element in payload.get("elements", []):
        latitude = element.get("lat")
        longitude = element.get("lon")
        if latitude is None or longitude is None:
            center = element.get("center", {})
            latitude = center.get("lat")
            longitude = center.get("lon")

        if latitude is None or longitude is None:
            continue

        tags = element.get("tags", {})
        rows.append(
            {
                "osm_id": element.get("id"),
                "osm_type": element.get("type"),
                "amenity": tags.get("amenity"),
                "shop": tags.get("shop"),
                "railway": tags.get("railway"),
                "public_transport": tags.get("public_transport"),
                "name": tags.get("name"),
                "tags_json": json.dumps(tags, sort_keys=True),
                "lat": latitude,
                "lon": longitude,
            }
        )

    points_gdf = gpd.GeoDataFrame(
        rows,
        geometry=gpd.points_from_xy(
            [row["lon"] for row in rows],
            [row["lat"] for row in rows],
        ),
        crs=CRS_TARGET,
    )
    if points_gdf.empty:
        return points_gdf
    return points_gdf.drop_duplicates(subset=["osm_type", "osm_id"]).reset_index(drop=True)


def parse_overpass_lines(json_path: Union[str, Path]) -> gpd.GeoDataFrame:
    """Convert an Overpass JSON response with way geometries into a line GeoDataFrame."""
    json_file = Path(json_path)
    with json_file.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)

    rows: list[dict[str, Any]] = []
    geometries: list[LineString] = []
    for element in payload.get("elements", []):
        geometry_points = element.get("geometry", [])
        if len(geometry_points) < 2:
            continue

        coords = [(point["lon"], point["lat"]) for point in geometry_points]
        if len(coords) < 2:
            continue

        tags = element.get("tags", {})
        rows.append(
            {
                "osm_id": element.get("id"),
                "osm_type": element.get("type"),
                "highway": tags.get("highway"),
                "name": tags.get("name"),
                "tags_json": json.dumps(tags, sort_keys=True),
            }
        )
        geometries.append(LineString(coords))

    lines_gdf = gpd.GeoDataFrame(rows, geometry=geometries, crs=CRS_TARGET)
    if lines_gdf.empty:
        return lines_gdf
    return lines_gdf.drop_duplicates(subset=["osm_type", "osm_id"]).reset_index(drop=True)


def parse_overpass_to_geodataframe(json_path: Union[str, Path]) -> gpd.GeoDataFrame:
    """Backward-compatible alias for point parsing."""
    return parse_overpass_points(json_path)


def load_insee_population(zip_path: Union[str, Path], dept_filter: str = "75") -> pd.DataFrame:
    """Load the INSEE population ZIP, filter to Paris, and keep the core columns."""
    selected_columns = ["IRIS", "COM", "P22_POP", "P22_PMEN"]
    source_path = Path(zip_path)

    try:
        population_df = pd.read_csv(
            source_path,
            compression="zip",
            sep=";",
            usecols=selected_columns,
            dtype={"IRIS": "string", "COM": "string"},
        )
    except Exception:
        with zipfile.ZipFile(source_path) as zip_file:
            csv_members = [member for member in zip_file.namelist() if member.lower().endswith(".csv")]
            if not csv_members:
                raise FileNotFoundError(f"No CSV member found inside '{source_path}'.")
            with zip_file.open(csv_members[0]) as csv_file:
                population_df = pd.read_csv(
                    csv_file,
                    sep=";",
                    usecols=selected_columns,
                    dtype={"IRIS": "string", "COM": "string"},
                )

    population_df["IRIS"] = population_df["IRIS"].astype("string").str.zfill(9)
    population_df["COM"] = population_df["COM"].astype("string").str.zfill(5)
    population_df = population_df.loc[population_df["COM"].str.startswith(dept_filter)].copy()
    population_df["P22_POP"] = pd.to_numeric(population_df["P22_POP"], errors="coerce").fillna(0.0)
    population_df["P22_PMEN"] = pd.to_numeric(population_df["P22_PMEN"], errors="coerce").fillna(0.0)

    return population_df.reset_index(drop=True)


def load_population_for_arrondissements(
    zip_path: Optional[Union[str, Path]] = None,
    dept_filter: str = "75",
) -> pd.DataFrame:
    """Aggregate INSEE population totals to the arrondissement level."""
    dataset_path = _resolve_dataset_path("iris_population", zip_path)
    population_df = load_insee_population(dataset_path, dept_filter=dept_filter)
    population_df["arrondissement_code"] = population_df["COM"].str[-2:]

    arrondissement_population = (
        population_df.groupby("arrondissement_code", as_index=False)["P22_POP"]
        .sum()
        .rename(columns={"P22_POP": "x1_population"})
    )
    return arrondissement_population


def load_green_spaces_for_arrondissements(
    csv_path: Optional[Union[str, Path]] = None,
) -> gpd.GeoDataFrame:
    """Load the OpenData Paris green spaces polygons used for X4."""
    dataset_path = _resolve_dataset_path("green_spaces", csv_path)
    read_kwargs = DATA_SOURCES["green_spaces"].get("read_csv_kwargs", {})
    green_df = pd.read_csv(dataset_path, **read_kwargs)

    categories = green_df["categorie"].map(normalize_text)
    types = green_df["type_ev"].map(normalize_text)
    green_df = green_df.loc[~categories.eq("jardiniere")].copy()
    green_df = green_df.loc[~types.eq("decorations sur la voie publique")].copy()
    green_df = green_df.loc[green_df["geom"].notna()].copy()
    green_df["geom"] = green_df["geom"].apply(json.loads)

    green_gdf = gpd.GeoDataFrame(
        green_df,
        geometry=green_df["geom"].apply(shape),
        crs=CRS_TARGET,
    )
    invalid_mask = ~green_gdf.geometry.is_valid
    if invalid_mask.any():
        green_gdf.loc[invalid_mask, "geometry"] = green_gdf.loc[invalid_mask, "geometry"].buffer(0)

    green_gdf = green_gdf.loc[
        green_gdf.geometry.notna() & ~green_gdf.geometry.is_empty
    ].copy()
    return green_gdf.reset_index(drop=True)


def load_dataset(name: str) -> LoadedDataset:
    """Load a dataset from the raw data directory based on its configured format."""
    if name not in DATA_SOURCES:
        available = ", ".join(sorted(DATA_SOURCES))
        raise KeyError(f"Unknown dataset '{name}'. Available datasets: {available}")

    source = DATA_SOURCES[name]
    dataset_path = RAW_DATA_DIR / source["local_filename"]
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset '{name}' not found at '{dataset_path}'. "
            "Place the raw file in data/raw/ before loading it."
        )

    file_format = source.get("file_format", dataset_path.suffix.lstrip(".")).lower()

    if file_format == "csv":
        return pd.read_csv(dataset_path, **source.get("read_csv_kwargs", {}))
    if file_format == "json":
        with dataset_path.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle)
    if file_format in {"xlsx", "xls"}:
        return pd.read_excel(dataset_path)
    if file_format in {"geojson", "gpkg", "shp"}:
        return gpd.read_file(dataset_path)
    if file_format == "zip":
        if dataset_path.name.endswith(".csv.zip"):
            read_kwargs = source.get("read_csv_kwargs", {"compression": "zip"})
            return pd.read_csv(dataset_path, **read_kwargs)
        return gpd.read_file(dataset_path)

    raise ValueError(f"Unsupported file format '{file_format}' for dataset '{name}'.")


def load_terrasses_for_arrondissements(
    csv_path: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """Charge les terrasses autorisees et calcule la surface totale (m2) par arrondissement."""
    dataset_path = _resolve_dataset_path("terrasses_autorisations", csv_path)
    read_kwargs = DATA_SOURCES["terrasses_autorisations"].get("read_csv_kwargs", {})
    df = pd.read_csv(dataset_path, **read_kwargs)

    df["longueur"] = pd.to_numeric(df["longueur"], errors="coerce").fillna(0.0)
    df["largeur"] = pd.to_numeric(df["largeur"], errors="coerce").fillna(0.0)
    df["surface_m2"] = df["longueur"] * df["largeur"]

    df = df.loc[df["arrondissement"].notna()].copy()
    df["arrondissement_code"] = df["arrondissement"].astype(str).str[-2:]

    aggregated = (
        df.groupby("arrondissement_code", as_index=False)["surface_m2"]
        .sum()
        .rename(columns={"surface_m2": "x6_terrasse_surface_m2"})
    )
    return aggregated


def load_schools_for_arrondissements(
    colleges_path: Optional[Union[str, Path]] = None,
    elementaires_path: Optional[Union[str, Path]] = None,
    maternelles_path: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """Charge les 3 types d'etablissements scolaires, filtre la derniere annee scolaire, et renvoie un comptage par arrondissement."""
    sources = [
        ("etablissements_scolaires_colleges", colleges_path),
        ("etablissements_scolaires_elementaires", elementaires_path),
        ("etablissements_scolaires_maternelles", maternelles_path),
    ]
    frames = []
    for dataset_name, override_path in sources:
        path = _resolve_dataset_path(dataset_name, override_path)
        read_kwargs = DATA_SOURCES[dataset_name].get("read_csv_kwargs", {})
        df = pd.read_csv(path, **read_kwargs, dtype={"arr_insee": "string"})
        df = df.loc[df["annee_scol"].notna()].copy()
        latest = df["annee_scol"].max()
        df = df.loc[df["annee_scol"] == latest].copy()
        df = df.loc[df["arr_insee"].notna()].copy()
        df["arrondissement_code"] = df["arr_insee"].astype(str).str.zfill(5).str[-2:]
        frames.append(df[["arrondissement_code"]])

    all_schools = pd.concat(frames, ignore_index=True)
    aggregated = (
        all_schools.groupby("arrondissement_code")
        .size()
        .rename("x7_school_count")
        .reset_index()
    )
    return aggregated
