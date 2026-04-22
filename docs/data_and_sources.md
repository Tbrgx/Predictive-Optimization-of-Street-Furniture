# Données et Sources

Ce document est le référentiel unique pour les données du projet `paris-bins-ml`. Il couvre les définitions des variables du modèle, les spécifications de chaque source, les résultats d'inspection des APIs, et la structure de la table maître.

---

## 1. Variables du modèle — Référence rapide

| Rôle | Variable | Colonne | Source | Description | Licence |
|:----:|:--------:|:-------:|:------:|:------------|:--------|
| **Y** | Cible | `y_bin_count` | Overpass API (OSM) | Nombre brut de corbeilles `amenity=waste_basket` par arrondissement | ODbL |
| **X1** | Explicative | `x1_population` | INSEE | Population totale 2022 agrégée par arrondissement depuis les IRIS | LO 2.0 |
| **X2** | Explicative | `x2_commerce_restaurant_count` | Overpass API (OSM) | Comptage OSM des commerces (`shop=*`) et restauration | ODbL |
| **X3** | Explicative | `x3_transport_station_count` | Overpass API (OSM) | Comptage OSM des stations de transport (hors entrées de métro) | ODbL |
| **X4** | Explicative | `x4_green_area_m2` | OpenData Paris | Surface totale des espaces verts (hors jardinières et décorations) en m² | ODbL |
| **X5** | Explicative | `x5_road_length_km` | Overpass API (OSM) | Longueur totale de la voirie structurante et locale en km | ODbL |
| **X6** | Explicative | `x6_terrasse_surface_m2` | OpenData Paris | Surface totale des terrasses autorisées (longueur × largeur) en m² | ODbL |
| **X7** | Explicative | `x7_school_count` | OpenData Paris | Nombre d'établissements scolaires (collèges + élémentaires + maternelles) | ODbL |
| **—** | Support | `geometry` | IGN / GeoPF | Polygones des 20 arrondissements, reconstruits par dissolution des IRIS | LO 2.0 |

---

## 2. Détail des sources actives

### 2.1 Corbeilles de rue OSM — variable cible Y

- **Source :** OpenStreetMap via Overpass API
- **URL :** `https://overpass-api.de/api/interpreter`
- **Fichier local :** `data/raw/street_bins_osm_arr.json`
- **Licence :** ODbL
- **Définition métier :** objets `amenity=waste_basket` sur l'aire administrative de Paris
- **Champs exploités :**
  - `type` / `id` : type et identifiant OSM (dédoublonnage sur `osm_type + osm_id`)
  - `lat` / `lon` : coordonnées directes (nœuds)
  - `center.lat` / `center.lon` : coordonnées du centre pour les `way` et `relation`
- **Transformation :**
  1. Parsing JSON → GeoDataFrame de points en `EPSG:4326`
  2. Jointure spatiale (`within`) avec les 20 arrondissements
  3. Comptage par arrondissement → `y_bin_count`
- **Limitation importante :** OSM ne recense que ~5 545 corbeilles contre ~30 000 annoncées par la Ville. La source est un fallback méthodologique explicite, pas un inventaire exhaustif. La source officielle PVP a été étudiée et écartée — voir § 3.

---

### 2.2 Commerces et restaurants OSM — X2

- **Source :** OpenStreetMap via Overpass API
- **URL :** `https://overpass-api.de/api/interpreter`
- **Fichier local :** `data/raw/commerce_restaurants_osm.json`
- **Licence :** ODbL
- **Définition métier :**
  - `shop=*` (tout type de commerce)
  - ou `amenity` dans `{restaurant, fast_food, cafe, bar, pub}`
- **Champs exploités :** `type`, `id`, `lat`, `lon`, `center.lat/lon`, `tags.shop`, `tags.amenity`
- **Transformation :**
  1. Parsing JSON → GeoDataFrame de points `EPSG:4326`
  2. Jointure spatiale avec les arrondissements
  3. Comptage par arrondissement → `x2_commerce_restaurant_count`

---

### 2.3 Stations de transport OSM — X3

- **Source :** OpenStreetMap via Overpass API
- **URL :** `https://overpass-api.de/api/interpreter`
- **Fichier local :** `data/raw/transport_stations_osm.json`
- **Licence :** ODbL
- **Définition métier :**
  - `railway` dans `{station, halt, tram_stop}`
  - ou `public_transport=station`
  - ou `amenity=bus_station`
  - **exclusion explicite** de `subway_entrance` (entrées de métro, pas des stations)
- **Champs exploités :** `type`, `id`, `lat/lon`, `center`, `tags.railway`, `tags.public_transport`, `tags.amenity`
- **Transformation :**
  1. Parsing JSON → GeoDataFrame de points `EPSG:4326`
  2. Jointure spatiale avec les arrondissements
  3. Comptage par arrondissement → `x3_transport_station_count`

---

### 2.4 Routes OSM — X5

- **Source :** OpenStreetMap via Overpass API
- **URL :** `https://overpass-api.de/api/interpreter`
- **Fichier local :** `data/raw/roads_osm.json`
- **Licence :** ODbL
- **Définition métier :**
  - `highway` dans `{motorway, trunk, primary, secondary, tertiary, unclassified, residential, living_street, service, pedestrian}`
  - **exclusions :** `footway`, `path`, `cycleway`, `steps` (voies non-motorisées)
- **Champs exploités :** `type`, `id`, `geometry` (séquence de coordonnées), `tags.highway`
- **Transformation :**
  1. Parsing JSON → GeoDataFrame de `LineString` en `EPSG:4326`
  2. Intersection géométrique (`gpd.overlay`) avec les arrondissements pour découper les tronçons aux frontières
  3. Reprojection en Lambert-93 (`EPSG:2154`) pour calculer des longueurs métriques
  4. Somme des longueurs en km par arrondissement → `x5_road_length_km`

---

### 2.5 Population INSEE par IRIS — X1

- **Source :** INSEE — Base infracommunale évolution et structure de la population 2022
- **Page source :** `https://www.insee.fr/fr/statistiques/8647014`
- **URL fichier :** `https://www.insee.fr/fr/statistiques/fichier/8647014/base-ic-evol-struct-pop-2022_csv.zip`
- **Fichier local :** `data/raw/iris_population_2022.csv.zip`
- **Licence :** Licence Ouverte / Open Licence 2.0
- **Format :** archive ZIP contenant un CSV délimité par `;`, 76 colonnes, périmètre national
- **Champs utilisés :**

| Champ | Type | Description |
|-------|------|-------------|
| `IRIS` | texte | Code IRIS sur 9 caractères (clé de jointure avec les contours) |
| `COM` | texte | Code commune / arrondissement (`75101`…`75120` pour Paris) |
| `P22_POP` | flottant | Population totale 2022 — variable retenue pour `X1` |
| `P22_PMEN` | flottant | Population des ménages 2022 — chargée mais non utilisée en modèle |

- **Transformation :**
  1. Lecture streaming du ZIP (tentative directe avec `compression="zip"`, puis extraction manuelle du membre CSV en cas d'échec)
  2. Normalisation des codes : `IRIS` rempli à 9 chiffres, `COM` à 5 chiffres
  3. Filtre `COM` commençant par `75`
  4. Extraction `arrondissement_code = COM[-2:]` (les 2 derniers chiffres du code commune correspondent au numéro d'arrondissement)
  5. Somme de `P22_POP` par arrondissement → `x1_population`

- **Note d'inspection :** Le fichier est national et couvre ~50 000 IRIS. Les en-têtes ont été vérifiées (76 colonnes) sans persistance locale complète. Aucun endpoint de métadonnées API n'expose le nombre total de lignes.

---

### 2.6 Espaces verts OpenData Paris — X4

- **Source :** OpenData Paris
- **URL :** `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/espaces_verts/exports/csv`
- **Fichier local :** `data/raw/green_spaces.csv`
- **Licence :** ODbL
- **Nombre de records :** 2 527 (au 2026-03-12)
- **Filtres métier appliqués :**
  - exclusion `categorie = Jardiniere` (866 lignes, biaiserait un indicateur de superficie accessible)
  - exclusion `type_ev = Decorations sur la voie publique`
- **Champs utilisés :** `nom_ev`, `categorie`, `type_ev`, `geom` (polygone GeoJSON), `geom_x_y` (centroïde)
- **Transformation :**
  1. Filtrage métier via normalisation Unicode (suppression des accents pour comparaisons robustes)
  2. Parsing de la colonne `geom` (chaîne JSON) en objets Shapely
  3. Réparation des géométries invalides via `buffer(0)` (trick Shapely pour les auto-intersections)
  4. Intersection avec les arrondissements + reprojection Lambert-93 (`EPSG:2154`)
  5. Calcul de surface `.geometry.area` en m² + somme par arrondissement → `x4_green_area_m2`

- **Notes d'inspection :**
  - Le jeu contient des catégories non pertinentes : `Jardiniere` (866), `Murs végétalisés`, `Talus`, `Cimetiere`
  - Valeurs manquantes sur les champs surfaciques : `poly_area` renseigné à 1944/2527, `surface_totale_reelle` à 1928/2527 (raison du recalcul d'aire via géométrie plutôt qu'en attribut)
  - `geom` et `geom_x_y` renseignés sur 2525/2527 lignes

---

### 2.7 Terrasses autorisées OpenData Paris — X6

- **Source :** OpenData Paris
- **URL :** `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/terrasses-autorisations/exports/csv`
- **Fichier local :** `data/raw/terrasses_autorisations.csv`
- **Licence :** ODbL
- **Définition métier :** surface de chaque terrasse = `longueur × largeur` déclarées dans l'autorisation
- **Transformation :**
  1. Calcul `surface_m2 = longueur × largeur` (valeurs manquantes remplacées par 0)
  2. Nettoyage du champ `arrondissement` (coercion numérique, suppression des NaN)
  3. Extraction `arrondissement_code` sur 2 chiffres (`str[-2:].zfill(2)`)
  4. Somme des surfaces par arrondissement → `x6_terrasse_surface_m2`

---

### 2.8 Établissements scolaires OpenData Paris — X7

- **Source :** OpenData Paris (3 datasets distincts)
- **URLs :**
  - Collèges : `...etablissements-scolaires-colleges/exports/csv`
  - Élémentaires : `...etablissements-scolaires-ecoles-elementaires/exports/csv`
  - Maternelles : `...etablissements-scolaires-maternelles/exports/csv`
- **Fichiers locaux :** `data/raw/etablissements_colleges.csv`, `_elementaires.csv`, `_maternelles.csv`
- **Licence :** ODbL
- **Transformation :**
  1. Pour chaque fichier : filtre sur la dernière année scolaire disponible (`annee_scol.max()`)
  2. Filtre `arr_insee` commençant par `75`
  3. Extraction `arrondissement_code = arr_insee[-2:].zfill(2)`
  4. Concaténation des 3 DataFrames + comptage par arrondissement → `x7_school_count`

---

### 2.9 Contours IRIS GeoPF/IGN — support géographique

- **Source :** IGN / GeoPF via WFS
- **URL WFS :** `https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=STATISTICALUNITS.IRISGE:iris_ge&OUTPUTFORMAT=application/json&SRSNAME=EPSG:4326&CQL_FILTER=code_insee%20like%20%2775%25%27`
- **Fichier local :** `data/raw/iris_contours_paris.geojson`
- **Licence :** Licence Ouverte / Open Licence 2.0
- **Nombre de records :** 992 IRIS parisiens (codes `75101`→`75120`)
- **Champs utilisés :**

| Champ | Description |
|-------|-------------|
| `code_insee` | Code commune (`75101`…`75120`) — clé de dissolution en arrondissements |
| `nom_commune` | Nom de l'arrondissement |
| `code_iris` | Code IRIS complet sur 9 caractères — clé de jointure avec INSEE |
| `nom_iris` | Libellé de l'IRIS |
| `geometry` | Polygone IRIS en `EPSG:4326` |

- **Transformation :**
  1. Filtre côté serveur `code_insee like '75%'`
  2. Dissolution (`dissolve`) par `code_insee + nom_commune` → 20 polygones d'arrondissements
  3. Extraction `arrondissement_code = code_insee[-2:]`
  4. Validation stricte : exactement 20 lignes, codes `01`→`20`, aucune géométrie nulle

- **Fallback déclaré :** `https://www.data.gouv.fr/api/1/datasets/r/eac194ba-c917-4b25-a53b-0e4cf43312f2`

- **Note d'inspection :**
  - La couche `iris-ge` est plus récente que l'ancien fallback `contours-iris-r`
  - `code_iris` est la clé de jointure naturelle avec les données de population INSEE (`IRIS` → `code_iris`)
  - Le filtre `code_insee like '75%'` couvre exactement les 20 arrondissements

---

## 3. Source bloquée : PVP mobiliers urbains

La source officielle de la Ville de Paris a été inspectée en détail et écartée comme variable cible.

- **Dataset ID :** `plan-de-voirie-mobiliers-urbains-jardinieres-bancs-corbeilles-de-rue`
- **URL source :** `https://opendata.paris.fr/explore/dataset/plan-de-voirie-mobiliers-urbains-jardinieres-bancs-corbeilles-de-rue`
- **Nombre de records :** 273 306

### Blocage constaté

Le titre du dataset regroupe explicitement `Jardinières + Bancs + Corbeilles de rue`. Le champ `lib_classe` qui aurait dû permettre le filtrage par type est **null sur 273 306/273 306 lignes**.

L'investigation complémentaire a montré que :
- `num_pave` ne correspond pas à un type de mobilier mais à un code de pavé graphique (code géographiquement localisé, primitives quasi-superposées avec `igds_element_type` différents)
- La couche ArcGIS source (`capgeo2.paris.fr`) n'expose aucun champ documenté comme "corbeille / banc / jardinière"
- Le comptage brut du PVP (273 306 lignes) est incohérent avec les ~30 000 corbeilles annoncées par la Ville de Paris

### Échantillon inspecté

| `objectid` | `num_pave` | `lib_level` | `lib_classe` | `geo_point_2d` |
|---|---|---|---|---|
| `79987` | `161N` | `ENVIRONNEMENT` | `null` | `48.854433, 2.241983` |
| `80022` | `163G` | `ENVIRONNEMENT` | `null` | `48.872234, 2.278859` |

### Décision de sprint

Ne pas utiliser la couche PVP comme variable cible. Conserver OSM (`amenity=waste_basket`) comme fallback méthodologique explicite avec la limitation documentée (~5 545 objets vs ~30 000 corbeilles officielles).

---

## 4. Source explorée mais non retenue : Stations Trilib'

> Cette source a été inspectée en phase d'exploration mais n'est pas utilisée dans le pipeline primaire. Elle est conservée ici comme trace d'exploration.

- **Dataset ID :** `dechets-menagers-points-dapport-volontaire-stations-trilib`
- **Nombre de records :** 439 (toutes en `Mobilier en service`)
- **Champ géographique :** `geo_shape` (Point) et `geo_point_2d` — compatibles `EPSG:4326`
- **Statut dans `config.py` :** `"status": "legacy"` — non téléchargée dans le pipeline pédagogique
- **Raison de non-rétention :** remplacée par les stations de transport OSM (X3), source plus large et homogène

---

## 5. Table maître `master_arrondissements`

Fichiers produits par `src/preprocessing.py` via `build_master_arrondissements()` :

- `data/processed/master_arrondissements.csv` — version tabulaire (sans géométrie)
- `data/processed/master_arrondissements.geojson` — version géospatiale

**Granularité :** 1 ligne = 1 arrondissement | **Volume :** 20 lignes

| Colonne | Type | Description |
|---------|------|-------------|
| `arrondissement_code` | texte | Code `01` à `20` |
| `arrondissement_name` | texte | Libellé de l'arrondissement |
| `geometry` | géométrie | Polygone en `EPSG:4326` (dans le GeoJSON uniquement) |
| `y_bin_count` | entier | Nombre brut de corbeilles OSM observées |
| `x1_population` | flottant | Population INSEE totale |
| `x2_commerce_restaurant_count` | entier | Nombre OSM de commerces/restaurants |
| `x3_transport_station_count` | entier | Nombre OSM de stations de transport |
| `x4_green_area_m2` | flottant | Surface totale d'espaces verts en m² |
| `x5_road_length_km` | flottant | Longueur totale des routes en km |
| `x6_terrasse_surface_m2` | flottant | Surface totale des terrasses autorisées en m² |
| `x7_school_count` | entier | Nombre total d'établissements scolaires |
| `cluster_label` | entier | Cluster KMeans brut (`0`, `1`, `2`) |
| `cl_2` | entier | Variable indicatrice cluster 2 (One-Hot, `drop_first=True`) |
| `cl_3` | entier | Variable indicatrice cluster 3 (One-Hot, `drop_first=True`) |
| `y_predicted` | flottant | Prédiction de la régression linéaire |
| `residual` | flottant | `y_bin_count - y_predicted` |
| `priority_score` | flottant | `y_predicted - y_bin_count` (positif = déficit estimé) |

---

## 6. Réponses critiques (résumé d'inspection)

**Q1. Le dataset PVP contient-il uniquement des corbeilles ?**
Non. Le champ de filtrage `lib_classe` est null sur l'intégralité du dataset. Aucun filtre robuste n'est disponible dans le schéma public. → Source bloquée (voir § 3).

**Q2. Les coordonnées sont-elles en WGS84 (EPSG:4326) ?**
Oui pour toutes les sorties API inspectées. Le CRS est validé explicitement dans `preprocessing.py` avant chaque opération spatiale.

**Q3. Combien de corbeilles y a-t-il dans Paris ?**
~30 000 selon les communications officielles de la Ville. OSM en recense ~5 545. Le projet utilise OSM comme proxy relatif (classement par arrondissement), non comme décompte absolu.

**Q4. Les contours IRIS couvrent-ils les 20 arrondissements ?**
Oui. Le filtre `code_insee like '75%'` retourne exactement 992 IRIS pour les codes `75101`→`75120`.

**Q5. Y a-t-il des clés communes entre les datasets ?**
Une clé directe existe entre contours IRIS et INSEE : `code_iris` ↔ `IRIS`. Pour les autres sources OpenData Paris, la jointure spatiale sur les polygones IRIS/arrondissements est obligatoire.

---

## 7. Artefacts hérités (legacy)

Les éléments suivants ont été déplacés dans `_legacy/` et ne font plus partie du pipeline primaire :

- `master_iris` — table à l'échelle IRIS (ancienne unité d'analyse)
- Pipeline `RandomForestRegressor` / `XGBRegressor` / `DummyRegressor`
- Classement Top 50 IRIS et carte de priorisation IRIS
- Rapport de biais OSM (`_legacy/docs/osm_bias_report.md`)
