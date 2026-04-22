from pathlib import Path


# ---------------------------------------------------------------------------
# Chemins du projet
# Tous les scripts importent ces constantes plutôt que de construire leurs
# propres chemins, ce qui garantit la cohérence entre les modules.
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
FIGURES_DIR = OUTPUTS_DIR / "figures"
TABLES_DIR = OUTPUTS_DIR / "tables"

NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
DOCS_DIR = PROJECT_ROOT / "docs"
SRC_DIR = PROJECT_ROOT / "src"

# ---------------------------------------------------------------------------
# Paramètres géospatiaux partagés
# ---------------------------------------------------------------------------

# Système de coordonnées cible pour toutes les couches géographiques.
# EPSG:4326 = WGS84 (lat/lon) — format standard des APIs REST et GeoJSON.
CRS_TARGET = "EPSG:4326"
IRIS_DEPT_FILTER = "75"  # code département Paris

# ---------------------------------------------------------------------------
# Paramètres de modélisation — Phase 1 (baseline pédagogique)
# ---------------------------------------------------------------------------

# K=3 est imposé par la consigne pédagogique (pas optimisé par silhouette/elbow).
PEDAGOGICAL_CLUSTER_COUNT = 3
PEDAGOGICAL_TARGET_COLUMN = "y_bin_count"

# Les 7 variables explicatives du modèle, dans l'ordre canonique.
# Cet ordre est utilisé pour la matrice de features, les coefficients et les exports.
BUSINESS_FEATURE_COLUMNS = [
    "x1_population",
    "x2_commerce_restaurant_count",
    "x3_transport_station_count",
    "x4_green_area_m2",
    "x5_road_length_km",
    "x6_terrasse_surface_m2",
    "x7_school_count",
]

# ---------------------------------------------------------------------------
# Source IRIS — IGN / GeoPF (WFS)
# Les contours d'arrondissements sont reconstruits par dissolution des IRIS,
# ce qui évite d'introduire une source externe supplémentaire et garantit
# la cohérence parfaite avec les jointures spatiales.
# ---------------------------------------------------------------------------

IRIS_WFS_BASE_URL = "https://data.geopf.fr/wfs/ows"
IRIS_WFS_LAYER = "STATISTICALUNITS.IRISGE:iris_ge"
IRIS_WFS_FILTER = "code_insee like '75%'"
IRIS_WFS_FILTER_ENCODED = "code_insee%20like%20%2775%25%27"
IRIS_WFS_URL = (
    f"{IRIS_WFS_BASE_URL}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
    f"&TYPENAMES={IRIS_WFS_LAYER}"
    f"&OUTPUTFORMAT=application/json"
    f"&SRSNAME={CRS_TARGET}"
    f"&CQL_FILTER={IRIS_WFS_FILTER_ENCODED}"
)

# ---------------------------------------------------------------------------
# Requêtes Overpass (OpenStreetMap)
# Chaque requête cible la zone administrative de Paris via `area["name"="Paris"]`.
# La syntaxe `node + way + relation` couvre tous les types d'objets OSM,
# et `out center` renvoie les coordonnées du centroïde pour les ways et relations.
# ---------------------------------------------------------------------------

OSM_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Sélecteur de zone réutilisé dans les 4 requêtes ci-dessous.
OSM_PARIS_AREA_QUERY = 'area["name"="Paris"]["boundary"="administrative"]["admin_level"="8"]->.a;'

# Variable cible Y : toutes les corbeilles de rue OSM dans Paris.
OSM_WASTE_BASKET_ARR_QUERY = f"""
[out:json][timeout:120];
{OSM_PARIS_AREA_QUERY}
(
  node(area.a)["amenity"="waste_basket"];
  way(area.a)["amenity"="waste_basket"];
  relation(area.a)["amenity"="waste_basket"];
);
out center;
""".strip()

# Variable X2 : commerces et restauration.
# `shop` sans valeur = tous les types de commerces ; la liste `amenity` restreint
# aux catégories de restauration pertinentes (pas les stations-service, hôpitaux, etc.)
OSM_COMMERCE_RESTAURANTS_QUERY = f"""
[out:json][timeout:180];
{OSM_PARIS_AREA_QUERY}
(
  node(area.a)["shop"];
  way(area.a)["shop"];
  relation(area.a)["shop"];
  node(area.a)["amenity"~"^(restaurant|fast_food|cafe|bar|pub)$"];
  way(area.a)["amenity"~"^(restaurant|fast_food|cafe|bar|pub)$"];
  relation(area.a)["amenity"~"^(restaurant|fast_food|cafe|bar|pub)$"];
);
out center;
""".strip()

# Variable X3 : stations de transport hors métro.
# `subway_entrance` est explicitement exclu car ce sont des entrées (pas des stations),
# et leur comptage serait disproportionné dans les arrondissements centraux.
OSM_TRANSPORT_STATIONS_QUERY = f"""
[out:json][timeout:180];
{OSM_PARIS_AREA_QUERY}
(
  node(area.a)["railway"~"^(station|halt|tram_stop)$"];
  way(area.a)["railway"~"^(station|halt|tram_stop)$"];
  relation(area.a)["railway"~"^(station|halt|tram_stop)$"];
  node(area.a)["public_transport"="station"];
  way(area.a)["public_transport"="station"];
  relation(area.a)["public_transport"="station"];
  node(area.a)["amenity"="bus_station"];
  way(area.a)["amenity"="bus_station"];
  relation(area.a)["amenity"="bus_station"];
);
out center;
""".strip()

# Variable X5 : longueur de voirie.
# `out geom` est nécessaire (à la différence de `out center`) pour récupérer
# la géométrie complète des ways et calculer leur longueur réelle.
# Les voies piétonnes/cyclables sont exclues car elles ne génèrent pas de flux
# de déchets comparables à la voirie motorisée.
OSM_ROADS_QUERY = f"""
[out:json][timeout:240];
{OSM_PARIS_AREA_QUERY}
way(area.a)["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|pedestrian)$"];
out geom;
""".strip()

# ---------------------------------------------------------------------------
# Catalogue des sources de données
# Design "déclaratif" : ajouter/désactiver une source sans toucher au code
# de téléchargement. Le champ `status` contrôle l'inclusion dans le pipeline :
#   - "primary"  : téléchargé et utilisé
#   - "legacy"   : ignoré par le pipeline pédagogique
#   - "blocked"  : source inspectée mais inutilisable (voir data_and_sources.md §3)
# ---------------------------------------------------------------------------

DATA_SOURCES = {
    "street_bins": {
        "name": "Corbeilles de rue - source officielle PVP (bloquee)",
        "url": "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/plan-de-voirie-mobiliers-urbains-jardinieres-bancs-corbeilles-de-rue/exports/csv",
        "license": "ODbL",
        "description": (
            "Couche PVP melangeant jardinieres, bancs et corbeilles de rue. "
            "Le schema public ne permet pas d'isoler les seules corbeilles et "
            "la couche ressemble a un dessin vectoriel plus qu'a un inventaire objet."
        ),
        "file_format": "csv",
        "local_filename": "street_bins_pvp_raw.csv",
        "read_csv_kwargs": {"sep": ";"},
        "status": "blocked",
        "recommended_for_target": False,
    },
    "street_bins_osm_arr": {
        "name": "Corbeilles de rue OSM - arrondissement",
        "url": OSM_OVERPASS_URL,
        "license": "ODbL",
        "description": "Points OSM amenity=waste_basket pour la cible pedagogique Y.",
        "file_format": "json",
        "local_filename": "street_bins_osm_arr.json",
        "request_method": "POST",
        "request_data": OSM_WASTE_BASKET_ARR_QUERY,
        "status": "primary",
        "retry_attempts": 3,
        "retry_delay_seconds": 30,
        "timeout_seconds": 180,
    },
    "commerce_restaurants_osm": {
        "name": "Commerces et restaurants OSM",
        "url": OSM_OVERPASS_URL,
        "license": "ODbL",
        "description": "Points OSM shop=* et amenity restaurant-like pour la variable X2.",
        "file_format": "json",
        "local_filename": "commerce_restaurants_osm.json",
        "request_method": "POST",
        "request_data": OSM_COMMERCE_RESTAURANTS_QUERY,
        "status": "primary",
        "retry_attempts": 3,
        "retry_delay_seconds": 30,
        "timeout_seconds": 240,
    },
    "transport_stations_osm": {
        "name": "Stations de transport OSM",
        "url": OSM_OVERPASS_URL,
        "license": "ODbL",
        "description": "Stations railway/public_transport/bus_station pour la variable X3.",
        "file_format": "json",
        "local_filename": "transport_stations_osm.json",
        "request_method": "POST",
        "request_data": OSM_TRANSPORT_STATIONS_QUERY,
        "status": "primary",
        "retry_attempts": 3,
        "retry_delay_seconds": 30,
        "timeout_seconds": 240,
    },
    "roads_osm": {
        "name": "Routes OSM",
        "url": OSM_OVERPASS_URL,
        "license": "ODbL",
        "description": "Ways OSM highway pour la variable X5 de longueur de routes.",
        "file_format": "json",
        "local_filename": "roads_osm.json",
        "request_method": "POST",
        "request_data": OSM_ROADS_QUERY,
        "status": "primary",
        "retry_attempts": 3,
        "retry_delay_seconds": 30,
        "timeout_seconds": 300,
    },
    "iris_contours": {
        "name": "Contours IRIS Paris - IRIS GE WFS",
        "url": IRIS_WFS_URL,
        "license": "Licence Ouverte / Open Licence version 2.0",
        "description": (
            "Couche IRIS GE via GeoPF WFS, demandee directement en EPSG:4326 "
            "et filtree cote serveur sur Paris."
        ),
        "file_format": "geojson",
        "local_filename": "iris_contours_paris.geojson",
        "wfs_layer": IRIS_WFS_LAYER,
        "wfs_filter": IRIS_WFS_FILTER,
        "timeout_seconds": 120,
        # URL de secours sur data.gouv.fr en cas d'indisponibilité du WFS IGN.
        "fallback_url": "https://www.data.gouv.fr/api/1/datasets/r/eac194ba-c917-4b25-a53b-0e4cf43312f2",
        "status": "primary",
    },
    "iris_population": {
        "name": "Population INSEE par IRIS",
        "url": "https://www.insee.fr/fr/statistiques/fichier/8647014/base-ic-evol-struct-pop-2022_csv.zip",
        "license": "Licence Ouverte / Open Licence",
        "description": "Base infracommunale INSEE de population par IRIS, version 2022.",
        "file_format": "zip",
        "local_filename": "iris_population_2022.csv.zip",
        "read_csv_kwargs": {"compression": "zip", "sep": ";"},
        "status": "primary",
    },
    "green_spaces": {
        "name": "Espaces verts",
        "url": "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/espaces_verts/exports/csv",
        "license": "ODbL",
        "description": "Emprises et attributs des espaces verts et assimiles geres par la Ville de Paris.",
        "file_format": "csv",
        "local_filename": "green_spaces.csv",
        "read_csv_kwargs": {"sep": ";"},
        "status": "primary",
    },
    "terrasses_autorisations": {
        "name": "Terrasses et etalages - Autorisations",
        "url": "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/terrasses-autorisations/exports/csv",
        "license": "ODbL",
        "description": "Surface de terrasses autorisees par arrondissement pour la variable X6.",
        "file_format": "csv",
        "local_filename": "terrasses_autorisations.csv",
        "read_csv_kwargs": {"sep": ";"},
        "status": "primary",
    },
    "etablissements_scolaires_colleges": {
        "name": "Etablissements scolaires - Colleges",
        "url": "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/etablissements-scolaires-colleges/exports/csv",
        "license": "ODbL",
        "description": "Localisation des colleges parisiens pour la variable X7.",
        "file_format": "csv",
        "local_filename": "etablissements_colleges.csv",
        "read_csv_kwargs": {"sep": ";"},
        "status": "primary",
    },
    "etablissements_scolaires_elementaires": {
        "name": "Etablissements scolaires - Ecoles elementaires",
        "url": "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/etablissements-scolaires-ecoles-elementaires/exports/csv",
        "license": "ODbL",
        "description": "Localisation des ecoles elementaires pour la variable X7.",
        "file_format": "csv",
        "local_filename": "etablissements_elementaires.csv",
        "read_csv_kwargs": {"sep": ";"},
        "status": "primary",
    },
    "etablissements_scolaires_maternelles": {
        "name": "Etablissements scolaires - Ecoles maternelles",
        "url": "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/etablissements-scolaires-maternelles/exports/csv",
        "license": "ODbL",
        "description": "Localisation des maternelles pour la variable X7.",
        "file_format": "csv",
        "local_filename": "etablissements_maternelles.csv",
        "read_csv_kwargs": {"sep": ";"},
        "status": "primary",
    },
    "trilib_stations": {
        "name": "Stations Trilib' (legacy)",
        "url": "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/dechets-menagers-points-dapport-volontaire-stations-trilib/exports/csv",
        "license": "Licence Ouverte / Open Licence",
        "description": "Source legacy conservee a titre documentaire, non utilisee dans le pipeline primaire.",
        "file_format": "csv",
        "local_filename": "trilib_stations.csv",
        "read_csv_kwargs": {"sep": ";"},
        "status": "legacy",
    },
}

# ---------------------------------------------------------------------------
# Paramètres de modélisation — Phase 2 (réseau de neurones MLPRegressor)
# Phase 2 n'est pas appelée par main.py ; elle s'exécute depuis les notebooks
# ou via run_phase2_neural_network_pipeline() directement.
# ---------------------------------------------------------------------------

# Phase 2 utilise les mêmes features que Phase 1 (X1..X7), sans les dummies KMeans.
PHASE2_FEATURE_COLUMNS = [
    "x1_population",
    "x2_commerce_restaurant_count",
    "x3_transport_station_count",
    "x4_green_area_m2",
    "x5_road_length_km",
    "x6_terrasse_surface_m2",
    "x7_school_count",
]
PHASE2_TARGET_COLUMN = "y_bin_count"
# 20% = 4 observations en test sur 20 au total — split minimal acceptable.
PHASE2_TEST_SIZE = 0.2
# Graine fixe pour la reproductibilité du split et de l'initialisation du réseau.
PHASE2_RANDOM_STATE = 42

# Architecture MLP : deux couches cachées légères (8 → 4 neurones).
# Volontairement sous-paramétré pour ne pas sur-ajuster sur 20 observations.
MLP_HIDDEN_LAYER_SIZES = (8, 4)
MLP_ACTIVATION = "relu"
MLP_SOLVER = "adam"
# alpha = coefficient de régularisation L2 (pénalise les grands poids).
MLP_ALPHA = 0.001
# max_iter élevé car adam sur petit jeu peut nécessiter beaucoup d'itérations.
MLP_MAX_ITER = 5000

# ---------------------------------------------------------------------------
# Liste canonique des datasets à télécharger pour le pipeline pédagogique
# ---------------------------------------------------------------------------

PEDAGOGICAL_DATASET_NAMES = [
    "street_bins_osm_arr",
    "commerce_restaurants_osm",
    "transport_stations_osm",
    "roads_osm",
    "iris_contours",
    "iris_population",
    "green_spaces",
    "terrasses_autorisations",
    "etablissements_scolaires_colleges",
    "etablissements_scolaires_elementaires",
    "etablissements_scolaires_maternelles",
]
