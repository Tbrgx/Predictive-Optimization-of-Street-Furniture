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
    """Normalize text to ASCII for robust rule-based filtering.

    NFKD décompose les caractères accentués (ex. 'é' → 'e' + combining accent),
    puis l'encodage ASCII ignore les combinants, produisant une chaîne sans accents.
    Cela permet de comparer des valeurs texte françaises sans se soucier des
    variantes d'encodage ou de casse (le résultat est mis en minuscules).
    """
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
    """Download a dataset from a URL and persist it locally.

    `stream=True` + `iter_content` évitent de charger l'intégralité de la réponse
    en mémoire avant écriture — indispensable pour le ZIP INSEE (~50 MB) et les
    JSON Overpass (routes OSM > 30 MB).
    """
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
    """Download the requested configured datasets.

    Stratégie de robustesse :
    1. Cache local : si le fichier existe déjà, le téléchargement est sauté
       (sauf si force=True), pour éviter des appels inutiles aux APIs Overpass
       qui ont des limites de débit.
    2. Retries : le catalogue définit `retry_attempts` et `retry_delay_seconds`
       par source ; les APIs Overpass nécessitent parfois plusieurs tentatives.
    3. Fallback URL : si toutes les tentatives échouent, une URL de secours
       est essayée (ex. data.gouv.fr pour les IRIS IGN).
    """
    requested_names = dataset_names or list(DATA_SOURCES.keys())
    downloaded_paths: dict[str, Path] = {}

    for name in requested_names:
        if name not in DATA_SOURCES:
            raise KeyError(f"Unknown dataset '{name}'.")

        source = DATA_SOURCES[name]
        # Les sources "blocked" (PVP) et "legacy" (Trilib') sont silencieusement ignorées.
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
    """Convert an Overpass JSON response into a point GeoDataFrame in EPSG:4326.

    Les objets Overpass de type `node` exposent `lat`/`lon` directement.
    Les `way` et `relation` n'ont pas de coordonnées propres ; l'API renvoie
    leur centroïde dans l'objet `center` quand `out center` est spécifié dans
    la requête. Les éléments sans aucune coordonnée sont ignorés.

    La déduplication sur `(osm_type, osm_id)` élimine les doublons qui peuvent
    apparaître quand un objet est référencé à la fois comme `way` et comme membre
    d'une `relation`.
    """
    json_file = Path(json_path)
    with json_file.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)

    rows: list[dict[str, Any]] = []
    for element in payload.get("elements", []):
        latitude = element.get("lat")
        longitude = element.get("lon")
        if latitude is None or longitude is None:
            # Fallback centroïde pour les ways/relations
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
    """Convert an Overpass JSON response with way geometries into a line GeoDataFrame.

    Contrairement aux points, les routes sont requêtées avec `out geom` (pas
    `out center`), ce qui renvoie la séquence complète de nœuds de chaque way
    dans le tableau `geometry`. On reconstruit des objets `LineString` Shapely
    à partir de ces coordonnées pour calculer les longueurs réelles ultérieurement.

    Un `way` avec moins de 2 points est ignoré (impossible de construire une ligne).
    """
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
    """Load the INSEE population ZIP, filter to Paris, and keep the core columns.

    Stratégie de lecture en deux passes :
    1. Tentative directe avec `compression="zip"` (fonctionne si le ZIP contient
       un seul membre CSV avec un nom standard).
    2. En cas d'échec (noms de membres atypiques ou ZIP multi-fichiers), ouverture
       manuelle du ZIP pour trouver le premier membre `.csv` et le lire.

    `str.zfill(9)` normalise les codes IRIS sur 9 chiffres car pandas les lit
    parfois comme entiers (perdant les zéros initiaux), et la jointure avec les
    contours IGN requiert exactement 9 caractères.
    """
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

    # Normalisation des codes pour garantir la cohérence des jointures
    population_df["IRIS"] = population_df["IRIS"].astype("string").str.zfill(9)
    population_df["COM"] = population_df["COM"].astype("string").str.zfill(5)
    # Filtre Paris : codes commune commençant par "75" (75101…75120)
    population_df = population_df.loc[population_df["COM"].str.startswith(dept_filter)].copy()
    population_df["P22_POP"] = pd.to_numeric(population_df["P22_POP"], errors="coerce").fillna(0.0)
    population_df["P22_PMEN"] = pd.to_numeric(population_df["P22_PMEN"], errors="coerce").fillna(0.0)

    return population_df.reset_index(drop=True)


def load_population_for_arrondissements(
    zip_path: Optional[Union[str, Path]] = None,
    dept_filter: str = "75",
) -> pd.DataFrame:
    """Aggregate INSEE population totals to the arrondissement level.

    Le code arrondissement est extrait des 2 derniers caractères du code commune
    INSEE : "75101" → "01", "75115" → "15". Ce mapping est une propriété stable
    du découpage parisien (arrondissement N = commune 751NN).
    """
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
    """Load the OpenData Paris green spaces polygons used for X4.

    Deux filtres métier sont appliqués pour exclure les éléments décoratifs qui
    biaiseraient la surface d'espaces verts accessibles :
    - `categorie == "Jardiniere"` : 866 lignes, petits objets sur voie publique
    - `type_ev == "Decorations sur la voie publique"` : talus, murs végétalisés

    `buffer(0)` est un trick Shapely standard pour réparer les polygones
    auto-intersectants (topologie invalide) sans modifier leur forme perceptible.
    Ces géométries invalides proviennent généralement d'artefacts de numérisation
    et provoqueraient des erreurs lors des intersections spatiales ultérieures.
    """
    dataset_path = _resolve_dataset_path("green_spaces", csv_path)
    read_kwargs = DATA_SOURCES["green_spaces"].get("read_csv_kwargs", {})
    green_df = pd.read_csv(dataset_path, **read_kwargs)

    # normalize_text retire les accents pour des comparaisons robustes
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
        # buffer(0) : trick Shapely pour corriger les auto-intersections sans altérer la forme
        green_gdf.loc[invalid_mask, "geometry"] = green_gdf.loc[invalid_mask, "geometry"].buffer(0)

    green_gdf = green_gdf.loc[
        green_gdf.geometry.notna() & ~green_gdf.geometry.is_empty
    ].copy()
    return green_gdf.reset_index(drop=True)


def load_dataset(name: str) -> LoadedDataset:
    """Load a dataset from the raw data directory based on its configured format.

    Dispatcher générique utilisé principalement dans les notebooks pour un accès
    ponctuel. Le pipeline principal utilise les fonctions spécialisées ci-dessus
    pour les sources complexes (INSEE, espaces verts, terrasses, établissements).
    """
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
    """Charge les terrasses autorisees et calcule la surface totale (m2) par arrondissement.

    La surface n'est pas un attribut direct du dataset : elle est reconstituée
    en multipliant `longueur × largeur` déclarées dans l'autorisation administrative.
    Les valeurs non numériques sont remplacées par 0 (terrasses sans dimensions renseignées).

    Le code arrondissement est extrait du champ numérique `arrondissement` via
    `str[-2:].zfill(2)` pour homogénéiser avec les autres sources (format "01"…"20").
    """
    dataset_path = _resolve_dataset_path("terrasses_autorisations", csv_path)
    read_kwargs = DATA_SOURCES["terrasses_autorisations"].get("read_csv_kwargs", {})
    df = pd.read_csv(dataset_path, **read_kwargs)

    df["longueur"] = pd.to_numeric(df["longueur"], errors="coerce").fillna(0.0)
    df["largeur"] = pd.to_numeric(df["largeur"], errors="coerce").fillna(0.0)
    df["surface_m2"] = df["longueur"] * df["largeur"]

    df = df.loc[df["arrondissement"].notna()].copy()
    arr_num = pd.to_numeric(df["arrondissement"], errors="coerce")
    df = df.loc[arr_num.notna()].copy()
    arr_num = arr_num.loc[df.index]
    # int → str → [-2:] → zfill(2) : "1" → "01", "15" → "15", "750015" → "15"
    df["arrondissement_code"] = arr_num.astype(int).astype(str).str[-2:].str.zfill(2)

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
    """Charge les 3 types d'etablissements scolaires et renvoie un comptage par arrondissement.

    Chaque fichier couvre plusieurs années scolaires. On filtre sur `annee_scol.max()`
    pour ne compter que les établissements actifs lors de l'année la plus récente,
    ce qui évite de comptabiliser des établissements fermés ou fusionnés.

    Les 3 DataFrames sont concaténés avant agrégation : un arrondissement reçoit
    donc bien le total collèges + élémentaires + maternelles.
    """
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
        # Filtre sur la dernière année scolaire disponible dans le fichier
        latest = df["annee_scol"].max()
        df = df.loc[df["annee_scol"] == latest].copy()
        df = df.loc[df["arr_insee"].notna()].copy()
        # Garde uniquement les établissements parisiens (code INSEE 75xxx)
        df = df.loc[df["arr_insee"].astype(str).str.startswith("75")].copy()
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
