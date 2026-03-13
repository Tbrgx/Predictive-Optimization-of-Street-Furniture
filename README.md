# Paris Bins ML

Projet academique de regression multiple appliquee a l'urbanisme parisien.
La voie primaire du repository suit maintenant strictement la consigne pedagogique :

- unite d'analyse = 20 arrondissements ;
- cible `Y` = nombre brut de corbeilles OSM par arrondissement ;
- variables explicatives `X1..X5` = population, commerces/restaurants, stations de transport, espaces verts, longueur de routes ;
- clustering `KMeans (K=3)` puis variables indicatrices ;
- modele final = `LinearRegression`.

Le livrable principal est un classement prescriptif des 20 arrondissements, complete par une carte choropleth `Folium`.

## Repository Structure

```text
paris-bins-ml/
├── README.md
├── requirements.txt
├── config.py
├── main.py
├── data/
│   ├── raw/
│   ├── processed/
│   └── external/
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   └── 02_modeling.ipynb
├── outputs/
│   ├── figures/
│   └── tables/
├── src/
│   ├── __init__.py
│   ├── data_loader.py
│   ├── preprocessing.py
│   ├── modeling.py
│   ├── build_map.py
│   └── visualization.py
└── docs/
    ├── api_exploration_report.md
    ├── data_dictionary.md
    ├── modeling_report.md
    └── technical_functional_traceability.md
```

## Primary Method

1. Telecharger ou reutiliser les jeux de donnees pedagogiques.
2. Construire 20 polygones d'arrondissement par dissolution des contours IRIS.
3. Agreger la cible `Y` et les variables `X1..X5` a l'echelle arrondissement.
4. Standardiser `X1..X5`, estimer `KMeans(n_clusters=3)`, puis creer `cl_2` et `cl_3`.
5. Entrainement d'une regression lineaire multiple sur 20 observations.
6. Calcul du score prescriptif `priority_score = y_predicted - y_observed`.
7. Export du classement des 20 arrondissements et de la carte finale.

## Setup

```bash
pip install -r requirements.txt
```

## Run

Execution du pipeline principal :

```bash
python main.py
```

Execution par etape :

```bash
python src/modeling.py
python src/build_map.py
```

## Primary Outputs

- `data/processed/master_arrondissements.csv`
- `data/processed/master_arrondissements.geojson`
- `outputs/tables/arrondissement_feature_matrix.csv`
- `outputs/tables/arrondissement_clusters.csv`
- `outputs/tables/arrondissement_regression_coefficients.csv`
- `outputs/tables/arrondissement_predictions.csv`
- `outputs/tables/arrondissement_priority_ranking.csv`
- `outputs/priority_map.html`

Le rapport de modelisation pedagogique est dans [docs/modeling_report.md](/c:/Bin Placement Project/paris-bins-ml/docs/modeling_report.md).
La trace de migration et d'audit est dans [docs/technical_functional_traceability.md](/c:/Bin Placement Project/paris-bins-ml/docs/technical_functional_traceability.md).

## Data Sources

### Primary sources used in the pedagogical pipeline

- `street_bins_osm_arr`
  - Source : OpenStreetMap via Overpass API
  - URL : `https://overpass-api.de/api/interpreter`
  - Licence : ODbL
  - Usage : cible `Y`, comptage `amenity=waste_basket`
- `commerce_restaurants_osm`
  - Source : OpenStreetMap via Overpass API
  - URL : `https://overpass-api.de/api/interpreter`
  - Licence : ODbL
  - Usage : `X2`, `shop=*` et `amenity in {restaurant, fast_food, cafe, bar, pub}`
- `transport_stations_osm`
  - Source : OpenStreetMap via Overpass API
  - URL : `https://overpass-api.de/api/interpreter`
  - Licence : ODbL
  - Usage : `X3`, stations de transport hors `subway_entrance`
- `roads_osm`
  - Source : OpenStreetMap via Overpass API
  - URL : `https://overpass-api.de/api/interpreter`
  - Licence : ODbL
  - Usage : `X5`, longueur des routes structurantes
- `iris_population`
  - Source : INSEE
  - URL : `https://www.insee.fr/fr/statistiques/fichier/8647014/base-ic-evol-struct-pop-2022_csv.zip`
  - Licence : Licence Ouverte / Open Licence
  - Usage : `X1`, population par arrondissement agregee depuis les IRIS
- `green_spaces`
  - Source : OpenData Paris
  - URL : `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/espaces_verts/exports/csv`
  - Licence : ODbL
  - Usage : `X4`, surface des espaces verts
- `iris_contours`
  - Source : IGN / GeoPF
  - URL : `https://data.geopf.fr/wfs/ows`
  - Licence : Licence Ouverte / Open Licence
  - Usage : construction des 20 arrondissements

## Methodological Note

La source officielle PVP de la Ville de Paris pour les corbeilles reste bloquee comme inventaire objet exploitable. Le pipeline primaire utilise donc le fallback OSM pour `Y`, avec une limitation explicite de couverture. Cette limite est documentee dans [docs/api_exploration_report.md](/c:/Bin Placement Project/paris-bins-ml/docs/api_exploration_report.md) et [docs/technical_functional_traceability.md](/c:/Bin Placement Project/paris-bins-ml/docs/technical_functional_traceability.md).

L'ancienne voie experimentale a maille IRIS ainsi que les rapports associes (`osm_bias_report.md`, `gap_analysis_instructions.md`, artefacts IRIS) ont ete deplaces dans le dossier `_legacy/` pour historique d'audit. Ils ne font plus partie du pipeline primaire.
