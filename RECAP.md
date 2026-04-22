# Paris Bins ML

![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-Pedagogical_Pipeline_Active-success)

Projet académique de **régression multiple appliquée à l'urbanisme parisien**.  
L'objectif est d'optimiser le placement des corbeilles de rue à Paris en prédisant leur nombre idéal par arrondissement, à partir de 7 caractéristiques urbaines : population, commerces, transports, espaces verts, voirie, terrasses autorisées, établissements scolaires.

---

## 1. Contexte & Objectif

La gestion de la propreté urbaine est un défi majeur pour les métropoles. Ce projet modélise le besoin en corbeilles de rue à l'échelle des **20 arrondissements parisiens**.

La source officielle de la Ville de Paris (couche PVP) ne permet pas d'isoler les corbeilles de rue des autres mobiliers urbains. Le projet utilise donc **OpenStreetMap (OSM)** comme source principale pour la variable cible `Y` — avec la limitation assumée que la couverture OSM est incomplète (~5 500 objets vs ~30 000 corbeilles officielles). Ce choix est documenté dans `docs/data_and_sources.md`.

**La modélisation repose sur :**

- Unité d'analyse : les 20 arrondissements
- Cible `Y` : nombre brut de corbeilles OSM par arrondissement (`y_bin_count`)
- Variables explicatives `X1..X7` : population, commerces/restaurants, stations de transport, espaces verts, longueur des routes, surface de terrasses autorisées, nombre d'établissements scolaires
- **Phase 1 (baseline pédagogique)** : `KMeans (K=3)` → variables indicatrices → `LinearRegression`
- **Phase 2 (méthode avancée)** : `MLPRegressor` avec split train/test et LOOCV

Le livrable principal est un **classement prescriptif** des 20 arrondissements (score de priorité : `y_prédit − y_observé`) accompagné d'une **carte choropleth interactive Folium**.

---

## 2. Architecture du pipeline

### 2.1 Phase 1 — Baseline pédagogique

```
Sources API (OSM, INSEE, OpenData Paris)
        │
        ▼  data_loader.py
  Données brutes (data/raw/)
        │
        ▼  preprocessing.py
  Table maître — 20 arrondissements × (Y + X1..X7)
        │
        ▼  modeling.py
  KMeans K=3 → One-Hot (cl_2, cl_3) → LinearRegression
        │
        ├── outputs/tables/  (CSV : features, clusters, coefficients, prédictions, classement)
        ├── docs/modeling_report.md  (rapport auto-généré)
        └── build_map.py → outputs/priority_map.html
```

### 2.2 Phase 2 — Réseau de neurones (optionnel)

```
Table maître (data/processed/master_arrondissements.csv)
        │
        ▼  modeling.py — run_phase2_neural_network_pipeline()
  Split 80/20 (16 train / 4 test)
        │
        ▼
  Pipeline sklearn : StandardScaler + MLPRegressor(8, 4)
        │
        ├── Métriques train / test / LOOCV
        ├── Comparaison avec baseline Phase 1
        └── outputs/figures/  (scatter Y vs X, actual vs predicted, résidus)
```

> **Note :** La Phase 2 n'est pas intégrée dans `main.py`. Elle se lance indépendamment depuis `notebooks/02_modeling.ipynb` ou via `python src/modeling.py` (le `__main__` exécute la Phase 1 ; la Phase 2 doit être appelée explicitement).

---

## 3. Sources de données

| Variable | Colonne | Source | Description | Licence |
|:--------:|:-------:|:------:|:------------|:--------|
| **Y** | `y_bin_count` | Overpass API | Corbeilles OSM `amenity=waste_basket` | ODbL |
| **X1** | `x1_population` | INSEE | Population par arrondissement (agrégation IRIS 2022) | LO 2.0 |
| **X2** | `x2_commerce_restaurant_count` | Overpass API | Comptage `shop=*` et restauration | ODbL |
| **X3** | `x3_transport_station_count` | Overpass API | Stations railway/bus/public_transport (hors entrées métro) | ODbL |
| **X4** | `x4_green_area_m2` | OpenData Paris | Surface espaces verts (hors jardinières) | ODbL |
| **X5** | `x5_road_length_km` | Overpass API | Longueur voirie structurante | ODbL |
| **X6** | `x6_terrasse_surface_m2` | OpenData Paris | Surface terrasses autorisées | ODbL |
| **X7** | `x7_school_count` | OpenData Paris | Établissements scolaires (collèges + élémentaires + maternelles) | ODbL |
| —  | `geometry` | IGN / GeoPF | Contours arrondissements (dissolution des ~992 IRIS parisiens) | LO 2.0 |

> Détail complet des champs, transformations, et résultats d'inspection des APIs : [`docs/data_and_sources.md`](docs/data_and_sources.md)

---

## 4. Structure du projet

```text
paris-bins-ml/
├── RECAP.md                       # Ce document — vue d'ensemble du projet
├── requirements.txt               # Dépendances Python (versions épinglées)
├── config.py                      # Registre central : chemins, hyperparamètres, catalogue de sources
├── main.py                        # Orchestrateur Phase 1 (téléchargement → preprocessing → modélisation → carte)
├── generate_static_map.py         # Génération d'une carte PNG statique (utilitaire)
├── export_visual_report.py        # Conversion HTML notebook → DOCX/PDF (utilitaire)
│
├── data/
│   ├── raw/                       # Données brutes téléchargées des APIs (11 fichiers)
│   ├── processed/                 # Table maître agrégée (GeoJSON + CSV, 20 lignes)
│   └── external/                  # Réservé aux inclusions manuelles
│
├── notebooks/
│   ├── 01_data_exploration.ipynb  # EDA : distributions, valeurs manquantes, visualisations
│   └── 02_modeling.ipynb          # Pipeline interactif Phase 1 + Phase 2 avec commentaires
│
├── outputs/
│   ├── figures/                   # Graphiques EDA et diagnostics Phase 2 (PNG)
│   ├── tables/                    # Tous les artefacts CSV/JSON du pipeline
│   └── priority_map.html          # Carte choropleth interactive (livrable principal)
│
├── src/                           # Code source du pipeline
│   ├── data_loader.py             # Téléchargement et parsing des 11 sources
│   ├── preprocessing.py           # Agrégation spatiale IRIS → arrondissement
│   ├── modeling.py                # Phase 1 (KMeans + Régression) et Phase 2 (MLP)
│   ├── build_map.py               # Génération de la carte Folium
│   └── visualization.py           # Utilitaires graphiques pour notebooks
│
├── docs/
│   ├── data_and_sources.md        # Référentiel données : variables, sources, APIs, table maître
│   ├── scripts_technical_documentation.md  # Architecture du code et logique des scripts
│   ├── technical_functional_traceability.md  # Trace d'audit : historique des sprints, décisions
│   └── modeling_report.md         # Rapport auto-généré à chaque run (équation, métriques, classement)
│
└── _legacy/                       # Pipeline IRIS (RandomForest/XGBoost) — conservé pour audit
```

---

## 5. Installation & Démarrage rapide

```bash
# 1. Créer et activer un environnement virtuel
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 2. Installer les dépendances
pip install -r requirements.txt
```

---

## 6. Utilisation

### Pipeline complet Phase 1 (recommandé)

```bash
python main.py
```

Télécharge les données manquantes, exécute l'ensemble du pipeline Phase 1, génère tous les artefacts et la carte interactive.

### Exécution modulaire

```bash
# Relancer uniquement la modélisation (utilise data/processed/ existant)
python src/modeling.py

# Relancer uniquement la carte (utilise outputs/tables/ existant)
python src/build_map.py
```

### Pipeline Phase 2 (réseau de neurones)

La Phase 2 n'est pas dans `main.py`. Elle s'exécute depuis le notebook interactif :

```bash
jupyter notebook notebooks/02_modeling.ipynb
```

Ou par appel direct depuis Python :

```python
from src.modeling import run_phase2_neural_network_pipeline
results = run_phase2_neural_network_pipeline()
```

---

## 7. Livrables générés

### Phase 1 — Baseline pédagogique

| Fichier | Description |
|---------|-------------|
| `data/processed/master_arrondissements.csv` | Table maître 20 arrondissements (Y + X1..X7) |
| `data/processed/master_arrondissements.geojson` | Même table avec géométries |
| `outputs/tables/arrondissement_feature_matrix.csv` | Matrice de features |
| `outputs/tables/arrondissement_clusters.csv` | Assignation des clusters KMeans |
| `outputs/tables/arrondissement_cluster_profiles.csv` | Profils moyens des 3 clusters |
| `outputs/tables/arrondissement_regression_coefficients.csv` | Coefficients de la régression |
| `outputs/tables/arrondissement_regression_metrics.csv` | R², R² ajusté, RMSE, MAE, LOOCV |
| `outputs/tables/arrondissement_predictions.csv` | Valeurs observées, prédites, résidus |
| `outputs/tables/arrondissement_priority_ranking.csv` | **Classement final prescriptif** |
| `outputs/tables/pedagogical_model_summary.json` | Résumé JSON du pipeline |
| `docs/modeling_report.md` | Rapport Markdown auto-généré (équation, métriques, classement) |
| `outputs/priority_map.html` | **Carte choropleth interactive** |

### Phase 2 — Réseau de neurones (si exécutée)

| Fichier | Description |
|---------|-------------|
| `outputs/tables/neural_network_predictions.csv` | Prédictions MLP (train/test, split indiqué) |
| `outputs/tables/neural_network_metrics.csv` | Métriques train / test / LOOCV |
| `outputs/tables/linear_regression_baseline_metrics.csv` | Métriques Phase 1 pour comparaison |
| `outputs/figures/y_vs_features_scatterplots.png` | Scatter Y vs X1..X7 |
| `outputs/figures/neural_network_actual_vs_predicted.png` | Diagnostic actual vs predicted |
| `outputs/figures/neural_network_residuals.png` | Analyse des résidus |

---

## 8. Documentation détaillée

| Document | Contenu |
|----------|---------|
| [`docs/data_and_sources.md`](docs/data_and_sources.md) | Variables du modèle, détail des sources, inspection APIs, table maître |
| [`docs/scripts_technical_documentation.md`](docs/scripts_technical_documentation.md) | Architecture du code, logique de chaque script |
| [`docs/technical_functional_traceability.md`](docs/technical_functional_traceability.md) | Trace d'audit : historique des sprints, décisions de conception, justifications |
| [`docs/modeling_report.md`](docs/modeling_report.md) | Rapport auto-généré : équation, coefficients, métriques, classement |

---

## 9. Limites connues

- **Y imparfait :** OSM recense ~5 500 corbeilles contre ~30 000 officielles. Le classement est pertinent en valeur relative (quel arrondissement est sous-équipé *par rapport aux autres*), pas comme décompte absolu.
- **Petit échantillon :** 20 observations limitent le pouvoir statistique. Le LOOCV est utilisé à la place du split classique pour pallier cette contrainte.
- **Coefficients pédagogiques :** Les coefficients de la régression doivent être lus comme indicateurs d'association, pas comme estimateurs causaux robustes.
- **Phase 2 expérimentale :** Avec 20 observations et 4 en test, le MLP est instable. Son intérêt est comparatif (valider que la régression linéaire est déjà performante sur ce jeu), non prédictif.
