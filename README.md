# Paris Bins ML

Projet academique de machine learning applique a l'urbanisme parisien.
Le pipeline suit la consigne pedagogique en deux phases :

- unite d'analyse = 20 arrondissements ;
- cible `Y` = nombre brut de corbeilles OSM par arrondissement ;
- variables explicatives `X1..X7` = population, commerces/restaurants, stations de transport, espaces verts, longueur de routes, surface de terrasses autorisees, etablissements scolaires ;
- **Phase 1 (baseline)** : clustering `KMeans (K=3)` + variables indicatrices + `LinearRegression` ;
- **Phase 2 (methode principale)** : `MLPRegressor` (reseau de neurones, sklearn) avec split train/test et LOOCV.

Le livrable principal est un pipeline de prediction avec evaluation comparative et un classement prescriptif des 20 arrondissements.

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

## Pipeline Phase 2 (methode principale)

1. Telecharger ou reutiliser les jeux de donnees pedagogiques.
2. Construire 20 polygones d'arrondissement par dissolution des contours IRIS.
3. Agreger la cible `Y` et les variables `X1..X7` a l'echelle arrondissement.
4. Creer les arrays `X (20, 7)` et `y (20,)`.
5. Separer en train (16 obs) et test (4 obs) avec `train_test_split(test_size=0.2, random_state=42)`.
6. Entrainer `MLPRegressor(hidden_layer_sizes=(8,4), activation='relu', solver='adam')` via un `Pipeline` avec `StandardScaler`.
7. Evaluer les predictions sur train, test et en LOOCV.
8. Comparer avec la baseline lineaire (phase 1).
9. Exporter les metriques, predictions et visualisations.

## Pipeline Phase 1 (baseline comparative)

1-3. Identique a la phase 2.
4. Standardiser `X1..X7`, estimer `KMeans(n_clusters=3)`, puis creer `cl_2` et `cl_3`.
5. Entrainement d'une `LinearRegression` sur 20 observations.
6. Calcul du score prescriptif `priority_score = y_predicted - y_observed`.

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

### Phase 2 (reseau de neurones)

- `data/processed/master_arrondissements.csv`
- `data/processed/master_arrondissements.geojson`
- `outputs/tables/phase2_feature_matrix.csv`
- `outputs/tables/phase2_target_vector.csv`
- `outputs/tables/phase2_train_test_summary.csv`
- `outputs/tables/neural_network_predictions.csv`
- `outputs/tables/neural_network_metrics.csv`
- `outputs/tables/linear_regression_baseline_metrics.csv`
- `outputs/figures/y_vs_features_scatterplots.png`
- `outputs/figures/neural_network_actual_vs_predicted.png`
- `outputs/figures/neural_network_residuals.png`

### Phase 1 (baseline)

- `outputs/tables/arrondissement_feature_matrix.csv`
- `outputs/tables/arrondissement_clusters.csv`
- `outputs/tables/arrondissement_regression_coefficients.csv`
- `outputs/tables/arrondissement_predictions.csv`
- `outputs/tables/arrondissement_priority_ranking.csv`

Le rapport de modelisation est dans [docs/modeling_report.md](docs/modeling_report.md).
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
- `terrasses_autorisations`
  - Source : Direction de l'Urbanisme - Ville de Paris
  - URL : `https://opendata.paris.fr/explore/dataset/terrasses-autorisations/`
  - Licence : ODbL
  - Usage : `X6`, surface totale des terrasses autorisees (SUM longueur x largeur)
- `etablissements_scolaires_colleges` / `_elementaires` / `_maternelles`
  - Source : Direction des Affaires Scolaires - Ville de Paris
  - URL : `https://opendata.paris.fr/explore/dataset/etablissements-scolaires-*/`
  - Licence : ODbL
  - Usage : `X7`, comptage consolide des etablissements scolaires (derniere annee scolaire)

## Methodological Note

La source officielle PVP de la Ville de Paris pour les corbeilles reste bloquee comme inventaire objet exploitable. Le pipeline primaire utilise donc le fallback OSM pour `Y`, avec une limitation explicite de couverture. Cette limite est documentee dans [docs/api_exploration_report.md](/c:/Bin Placement Project/paris-bins-ml/docs/api_exploration_report.md) et [docs/technical_functional_traceability.md](/c:/Bin Placement Project/paris-bins-ml/docs/technical_functional_traceability.md).

L'ancienne voie experimentale a maille IRIS ainsi que les rapports associes (`osm_bias_report.md`, `gap_analysis_instructions.md`, artefacts IRIS) ont ete deplaces dans le dossier `_legacy/` pour historique d'audit. Ils ne font plus partie du pipeline primaire.
