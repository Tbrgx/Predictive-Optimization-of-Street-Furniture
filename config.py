from pathlib import Path


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

CRS_TARGET = "EPSG:4326"
IRIS_DEPT_FILTER = "75"

PEDAGOGICAL_CLUSTER_COUNT = 3
PEDAGOGICAL_TARGET_COLUMN = "y_bin_count"
BUSINESS_FEATURE_COLUMNS = [
    "x1_population",
    "x2_commerce_restaurant_count",
    "x3_transport_station_count",
    "x4_green_area_m2",
    "x5_road_length_km",
    "x6_terrasse_surface_m2",
    "x7_school_count",
]

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

OSM_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSM_PARIS_AREA_QUERY = 'area["name"="Paris"]["boundary"="administrative"]["admin_level"="8"]->.a;'

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

OSM_ROADS_QUERY = f"""
[out:json][timeout:240];
{OSM_PARIS_AREA_QUERY}
way(area.a)["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|pedestrian)$"];
out geom;
""".strip()

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
PHASE2_TEST_SIZE = 0.2
PHASE2_RANDOM_STATE = 42
MLP_HIDDEN_LAYER_SIZES = (8, 4)
MLP_ACTIVATION = "relu"
MLP_SOLVER = "adam"
MLP_ALPHA = 0.001
MLP_MAX_ITER = 5000

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
