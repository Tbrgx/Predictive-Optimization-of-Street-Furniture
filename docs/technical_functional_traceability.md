# Technical and Functional Traceability

Date de consolidation : 2026-03-13 — Revise le 2026-04-19 (ajout Phase 2 MLP + variables X6/X7)

## 1. Purpose

Ce document rend la reorientation du projet auditable.
Il explicite :

- ce qui avait ete implemente initialement ;
- pourquoi ce chemin etait hors consigne pedagogique ;
- comment la voie primaire a ete reconfiguree ;
- quels artefacts sont maintenant officiels ;
- quelles limites restent actives.

## 2. Project Reset After Gap Analysis

Le fichier `gap_analysis_instructions.md` a formalise l'ecart entre les attentes pedagogiques et le pipeline alors en place.

### Ecart constate

- mauvaise unite d'analyse : IRIS au lieu de 20 arrondissements ;
- mauvaise cible : densite par km2 au lieu d'un nombre brut de corbeilles ;
- mauvais paradigme de modelisation : RandomForest / XGBoost au lieu d'une regression multiple interpretable ;
- absence du bloc pedagogique attendu `KMeans -> dummies -> LinearRegression`.

### Decision prise

Le pipeline `arrondissements + KMeans + regression lineaire` devient la voie primaire.
Le pipeline `IRIS + RandomForest/XGBoost` est conserve uniquement comme historique d'audit.

## 3. Current Official Functional Goal

Le projet doit maintenant produire :

1. une table maitre de 20 arrondissements ;
2. sept variables explicatives `X1..X7` construites selon les consignes ;
3. un clustering KMeans `K=3` (Phase 1 baseline) ;
4. une regression lineaire multiple avec variables indicatrices (Phase 1 baseline) ;
5. un reseau de neurones `MLPRegressor` avec train/test split et LOOCV (Phase 2 methode principale) ;
6. un classement prescriptif des 20 arrondissements ;
7. une carte choropleth de priorite.

## 4. Chronology of Implementations

## Sprint 1

- creation de l'architecture du repository ;
- creation de `config.py`, `requirements.txt`, `src/`, `docs/`, `notebooks/`.

## Sprint 2

- exploration des APIs OpenData Paris et des sources INSEE / GeoPF ;
- qualification des schemas reels ;
- constat de blocage sur la source officielle PVP des corbeilles.

## Sprint 3

- ingestion des sources brutes ;
- construction d'un `master_iris` ;
- rapport de biais OSM.

## Sprint 4

- construction d'un pipeline IRIS de type RandomForest / XGBoost ;
- generation d'un classement IRIS et d'une carte IRIS.

## Sprint 5

- filtrage metier des IRIS speciaux ;
- raffinement cartographique du classement IRIS.

## Sprint de reorientation pedagogique

- reecriture de `config.py` autour des sources pedagogiques ;
- reecriture de `src/data_loader.py` ;
- reecriture de `src/preprocessing.py` ;
- reecriture de `src/modeling.py` ;
- reecriture de `src/build_map.py` ;
- reecriture de `main.py` ;
- regeneration des sorties `master_arrondissements`, coefficients, predictions, ranking et carte ;
- reecriture des notebooks et de la documentation publique.

## Sprint Phase 2 — Reseau de neurones (2026-04-19)

- ajout des constantes `PHASE2_*` et `MLP_*` dans `config.py` ;
- ajout des fonctions `create_feature_response_arrays`, `create_train_test_datasets`, `build_neural_network_pipeline`, `evaluate_regression_predictions`, `run_phase2_neural_network_pipeline` dans `src/modeling.py` ;
- conservation du pipeline KMeans + LinearRegression comme baseline comparative ;
- reecriture de `notebooks/02_modeling.ipynb` pour les etapes 3 a 5 ;
- ajout des visualisations EDA dans `notebooks/01_data_exploration.ipynb`.

## Sprint X6/X7 — Variables terrasses et scolaires (2026-04-19)

- ajout de 4 sources dans `DATA_SOURCES` : `terrasses_autorisations`, `etablissements_scolaires_colleges`, `_elementaires`, `_maternelles` ;
- extension de `BUSINESS_FEATURE_COLUMNS` et `PHASE2_FEATURE_COLUMNS` a 7 colonnes ;
- ajout de `load_terrasses_for_arrondissements` et `load_schools_for_arrondissements` dans `src/data_loader.py` ;
- extension de `build_master_arrondissements` dans `src/preprocessing.py` ;
- cablage dans `build_pedagogical_master_table` dans `src/modeling.py`.

## 5. Primary Technical Design

## 5.1 Variable target

- `Y = y_bin_count`
- source : OpenStreetMap `amenity=waste_basket`
- niveau : arrondissement
- transformation : comptage par jointure spatiale

## 5.2 Explanatory variables

- `X1 = x1_population`
  - source : INSEE
  - agregation : somme de `P22_POP` par arrondissement
- `X2 = x2_commerce_restaurant_count`
  - source : OSM
  - definition : `shop=*` ou `amenity in {restaurant, fast_food, cafe, bar, pub}`
- `X3 = x3_transport_station_count`
  - source : OSM
  - definition : `railway in {station, halt, tram_stop}` ou `public_transport=station` ou `amenity=bus_station`
  - exclusion : `subway_entrance`
- `X4 = x4_green_area_m2`
  - source : OpenData Paris `espaces_verts`
  - filtre : exclusion `Jardiniere` et `Decorations sur la voie publique`
- `X5 = x5_road_length_km`
  - source : OSM
  - definition : routes structurantes et locales, hors `footway`, `path`, `cycleway`, `steps`
- `X6 = x6_terrasse_surface_m2`
  - source : OpenData Paris `terrasses-autorisations`
  - definition : SUM(longueur x largeur) des terrasses autorisees par arrondissement
  - agregation : somme des surfaces en m2
- `X7 = x7_school_count`
  - source : OpenData Paris (colleges + ecoles elementaires + ecoles maternelles)
  - definition : comptage consolide des etablissements scolaires, filtre sur la derniere annee scolaire disponible
  - agregation : COUNT(*) par arrondissement, somme des 3 types

## 5.3 Geographic unit

Les arrondissements ne sont pas telecharges comme couche externe.
Ils sont construits par dissolution des IRIS GeoPF sur `code_insee`.

Controles implementes :

- exactement 20 lignes ;
- codes `01` a `20` ;
- geometries non nulles.

## 5.4 Clustering and regression

- standardisation de `X1..X7` ;
- `KMeans(n_clusters=3, random_state=42, n_init=20)` ;
- creation des variables `cl_2` et `cl_3` avec `drop_first=True` ;
- `LinearRegression()` sur les 20 arrondissements ;
- calcul de :
  - `R2`
  - `adjusted R2`
  - `RMSE`
  - `MAE`
  - `LOOCV RMSE`
  - `LOOCV MAE`

## 5.5 Prescriptive logic

- `priority_score = y_predicted - y_observed`
- un score positif indique un deficit estime de corbeilles relativement au profil urbain de l'arrondissement
- classement final : les 20 arrondissements tries par `priority_score` decroissant

## 6. Data Lineage

### Raw datasets

- `data/raw/street_bins_osm_arr.json`
- `data/raw/commerce_restaurants_osm.json`
- `data/raw/transport_stations_osm.json`
- `data/raw/roads_osm.json`
- `data/raw/iris_contours_paris.geojson`
- `data/raw/iris_population_2022.csv.zip`
- `data/raw/green_spaces.csv`
- `data/raw/terrasses_autorisations.csv` (ajout 2026-04-19)
- `data/raw/etablissements_colleges.csv` (ajout 2026-04-19)
- `data/raw/etablissements_elementaires.csv` (ajout 2026-04-19)
- `data/raw/etablissements_maternelles.csv` (ajout 2026-04-19)

### Processed datasets

- `data/processed/master_arrondissements.csv`
- `data/processed/master_arrondissements.geojson`

### Outputs

- `outputs/tables/arrondissement_feature_matrix.csv`
- `outputs/tables/arrondissement_clusters.csv`
- `outputs/tables/arrondissement_cluster_profiles.csv`
- `outputs/tables/arrondissement_regression_coefficients.csv`
- `outputs/tables/arrondissement_regression_metrics.csv`
- `outputs/tables/arrondissement_predictions.csv`
- `outputs/tables/arrondissement_priority_ranking.csv`
- `outputs/tables/pedagogical_model_summary.json`
- `outputs/priority_map.html`
- `outputs/tables/phase2_feature_matrix.csv` (Phase 2)
- `outputs/tables/phase2_target_vector.csv` (Phase 2)
- `outputs/tables/phase2_train_test_summary.csv` (Phase 2)
- `outputs/tables/neural_network_predictions.csv` (Phase 2)
- `outputs/tables/neural_network_metrics.csv` (Phase 2)
- `outputs/tables/linear_regression_baseline_metrics.csv` (Phase 2)
- `outputs/figures/y_vs_features_scatterplots.png`
- `outputs/figures/neural_network_actual_vs_predicted.png`
- `outputs/figures/neural_network_residuals.png`

## 7. Main Technical Choices and Justifications

### Pourquoi conserver OSM pour Y

La source officielle PVP de la Ville n'est pas exploitable comme inventaire objet defendable.
OSM reste imparfait, mais c'est la seule source ouverte point-a-point executable dans le pipeline.

### Pourquoi compter et non densifier

La consigne pedagogique attend explicitement une regression multiple sur 20 arrondissements avec une variable `Y` brute.
Le projet ne cherche plus ici a modeliser une densite IRIS.

### Pourquoi garder KMeans avant la regression

Le clustering n'est pas utilise comme fin analytique autonome.
Il sert a produire les variables indicatrices demandees dans l'exercice pedagogique.

### Pourquoi utiliser la regression sur les features brutes

Le clustering est fait sur variables standardisees pour eviter les effets d'echelle.
La regression est faite sur les variables brutes afin de garder une lecture simple des coefficients.

### Pourquoi utiliser LOOCV

Avec seulement 20 observations, un train/test split classique serait instable.
Le `LeaveOneOut` fournit un controle plus coherent pour une lecture pedagogique.

## 8. Legacy Pipeline Status

Le pipeline suivant n'est plus la voie officielle :

- `master_iris`
- `RandomForestRegressor`
- `XGBRegressor`
- `DummyRegressor`
- `Top 50 IRIS`
- filtrage `special_iris`
- carte de priorisation IRIS

Ces elements peuvent rester dans le repository pour audit historique, mais ils ne doivent plus etre consideres comme resultat principal ni chemin d'execution recommandes.

## 9. Reproducibility

Installation :

```bash
pip install -r requirements.txt
```

Execution de bout en bout :

```bash
python main.py
```

Execution par module :

```bash
python src/modeling.py
python src/build_map.py
```

## 10. Acceptance Checks Applied

Les verifications cibles de la reorientation sont :

- `master_arrondissements.csv` contient 20 lignes ;
- les codes `01` a `20` sont presents une seule fois ;
- `y_bin_count` et `x1..x5` existent ;
- aucune feature `x1..x5` n'est `NaN` ;
- `cluster_label` ne contient que `0`, `1`, `2` ;
- `cl_2` et `cl_3` sont binaires ;
- la matrice de regression contient `7` colonnes ;
- les coefficients et l'intercept sont exportes ;
- `outputs/priority_map.html` est produit ;
- le chemin primaire n'annonce plus `RandomForest`, `XGBoost` ni `Top 50 IRIS`.

## 11. Residual Limitations

- `Y` reste une observation OSM et non un stock officiel exhaustif de corbeilles ;
- le modele porte sur 20 observations, donc son pouvoir statistique est limite ;
- les coefficients doivent etre interpretes pedagogiquement, pas comme un causal estimateur robuste ;
- le classement final est pertinent pour un exercice de regression multiple appliquee, pas comme systeme operationnel definitif de la Ville de Paris.
