# Documentation Technique des Scripts

Date de redaction : 2026-04-20 — Mis a jour le 2026-04-22

## Objet

Ce document presente chaque script Python du projet **paris-bins-ml** en decrivant sa raison d'etre, sa position dans le pipeline, et les blocs fonctionnels qui le composent.
L'objectif n'est pas de commenter chaque ligne de code, mais de donner une vision structuree des responsabilites et des choix techniques pour chaque fichier, de maniere a pouvoir expliquer le projet a un auditeur, un jury ou un relecteur technique.

Le projet contient **8 scripts actifs** repartis en 3 couches :

| Couche | Scripts | Role |
| --- | --- | --- |
| Configuration | `config.py` | Parametres, chemins, catalogue de sources |
| Coeur metier (`src/`) | `data_loader.py`, `preprocessing.py`, `modeling.py`, `build_map.py`, `visualization.py` | Acquisition, preparation, modelisation, cartographie |
| Utilitaires racine | `main.py`, `generate_static_map.py`, `export_visual_report.py` | Orchestration, carte statique, export DOCX/PDF |

---

## 1. `config.py` — Registre central de configuration

**Localisation :** racine du projet
**Lignes :** ~288
**Dependances :** `pathlib` uniquement

### Role

Ce fichier centralise toutes les constantes du projet : chemins de fichiers, parametres de modelisation et catalogue exhaustif des sources de donnees. Aucun autre script ne doit contenir de valeur en dur ; tout est parametre ici.

### Blocs fonctionnels

#### 1.1 Arborescence de fichiers

```python
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
# ...
```

Declare les chemins absolus vers les sous-repertoires du projet (`data/raw/`, `data/processed/`, `outputs/figures/`, `outputs/tables/`, `docs/`). Tous les autres scripts importent ces constantes au lieu de construire leurs propres chemins, ce qui garantit la coherence entre les modules et evite les doublons de chemins.

#### 1.2 Parametres de modelisation

```python
PEDAGOGICAL_CLUSTER_COUNT = 3
PEDAGOGICAL_TARGET_COLUMN = "y_bin_count"
BUSINESS_FEATURE_COLUMNS = ["x1_population", ..., "x7_school_count"]
```

Definit les hyperparametres de la Phase 1 (nombre de clusters, variable cible, liste des features) et de la Phase 2 (architecture du reseau de neurones : `MLP_HIDDEN_LAYER_SIZES = (8, 4)`, fonction d'activation, solveur, regularisation, nombre d'iterations). Le `random_state = 42` est fixe pour assurer la reproductibilite.

#### 1.3 Requetes Overpass (OpenStreetMap)

```python
OSM_WASTE_BASKET_ARR_QUERY = """
[out:json][timeout:120];
area["name"="Paris"]["boundary"="administrative"]["admin_level"="8"]->.a;
( node(area.a)["amenity"="waste_basket"]; ... );
out center;
"""
```

Quatre requetes Overpass QL encodees en brut, chacune ciblent un type d'objet precis dans la zone administrative de Paris : corbeilles (`amenity=waste_basket`), commerces/restaurants, stations de transport, routes. La syntaxe `area->` selectionne la zone de travail, les filtres `[tag=value]` isolent les objets voulus. Ce bloc permet de modifier une requete sans toucher au code d'execution.

#### 1.4 Catalogue `DATA_SOURCES`

```python
DATA_SOURCES = {
    "street_bins_osm_arr": { "name": ..., "url": ..., "status": "primary", ... },
    "iris_population":     { ..., "file_format": "zip", ... },
    ...
}
```

Dictionnaire Python de 13 entrees, chacune decrivant une source de donnees avec :

- `url` : point d'acces distant ;
- `local_filename` : nom du fichier en cache local ;
- `file_format` : format attendu (csv, json, geojson, zip) ;
- `read_csv_kwargs` : parametres de lecture (separateur `;`, compression) ;
- `status` : `primary`, `legacy` ou `blocked` (permet de desactiver une source sans supprimer sa declaration) ;
- `retry_attempts`, `retry_delay_seconds`, `timeout_seconds` : politique de robustesse reseau ;
- `fallback_url` : URL de secours en cas d'echec de la source principale.

Ce design de type "catalogue declaratif" permet d'ajouter ou supprimer une source sans modifier le code de telechargement.

---

## 2. `src/data_loader.py` — Acquisition et lecture des donnees

**Localisation :** `src/`
**Lignes :** ~406
**Dependances :** `requests`, `geopandas`, `pandas`, `shapely`, `json`, `zipfile`

### Role

Interface exclusive du projet avec les sources externes. Ce module telecharge l'ensemble des jeux de donnees du catalogue, gere le format heterogene des fichiers et expose des fonctions de lecture specialisees pour les sources complexes (INSEE, espaces verts, terrasses, etablissements scolaires).

### Blocs fonctionnels

#### 2.1 Telechargement unitaire et robuste

```python
def download_dataset(name, url, save_path, file_format, method, ...):
def download_all_datasets(dataset_names, force):
```

`download_dataset` effectue une requete HTTP (GET ou POST selon la source) et ecrit la reponse en streaming (`iter_content`) pour gerer les fichiers volumineux sans saturer la memoire. `download_all_datasets` orchestre le telechargement de toute la liste, avec :

- un cache local (si le fichier existe, le telechargement est saute sauf si `force=True`) ;
- une boucle de re-tentatives parametree par le catalogue (`retry_attempts`, `retry_delay_seconds`) ;
- un mecanisme de repli automatique (`fallback_url`) en cas d'echec apres toutes les tentatives, pour la couche IRIS de l'IGN par exemple.

#### 2.2 Parseurs Overpass (JSON → GeoDataFrame)

```python
def parse_overpass_points(json_path):
def parse_overpass_lines(json_path):
```

Deux fonctions jumelles qui lisent un JSON brut renvoye par l'API Overpass et le convertissent en `GeoDataFrame` geographique. La logique de `parse_overpass_points` :

1. itere sur chaque `element` du JSON ;
2. extrait les coordonnees (`lat`/`lon`) directement ou via l'objet imbrique `center` (pour les `way`/`relation`) ;
3. conserve les tags OSM utiles (`amenity`, `shop`, `railway`, etc.) ;
4. cree un GeoDataFrame avec projection EPSG:4326 ;
5. deduplique sur `(osm_type, osm_id)` pour eviter les doublons.

`parse_overpass_lines` suit la meme logique mais reconstruit des geometries `LineString` a partir des tableaux de coordonnees de chaque `way`, pour le calcul ulterieur de longueurs de routes.

#### 2.3 Chargement de la population INSEE

```python
def load_insee_population(zip_path, dept_filter="75"):
def load_population_for_arrondissements(zip_path):
```

Le fichier INSEE est un ZIP contenant un CSV aux colonnes semicolonne. `load_insee_population` :

1. tente une lecture directe avec `compression="zip"` ;
2. en cas d'echec (noms de membres atypiques), ouvre manuellement le ZIP, detecte le membre CSV, et le lit ;
3. normalise les codes IRIS sur 9 caracteres et les codes commune (COM) sur 5 ;
4. filtre sur le departement 75 (Paris) ;
5. convertit les colonnes de population en numerique avec gestion des valeurs manquantes.

`load_population_for_arrondissements` re-aggrege ensuite les 1 000+ IRIS de Paris en extrayant les 2 derniers chiffres du code commune (qui correspondent au numero d'arrondissement) pour obtenir un total de population par arrondissement.

#### 2.4 Chargement des espaces verts

```python
def load_green_spaces_for_arrondissements(csv_path):
```

Lit le CSV OpenData Paris des espaces verts puis :

1. normalise les textes (suppression des accents via `unicodedata.normalize`) pour effectuer un filtrage metier robuste ;
2. exclut les categories non pertinentes (`jardiniere`, `decorations sur la voie publique`) ;
3. parse la colonne `geom` (chaine JSON) en objets Shapely ;
4. repare les geometries invalides via `buffer(0)` ;
5. supprime les geometries nulles ou vides.

Le resultat est un GeoDataFrame de polygones exploitable pour les jointures spatiales.

#### 2.5 Chargement des terrasses et etablissements scolaires

```python
def load_terrasses_for_arrondissements(csv_path):
def load_schools_for_arrondissements(colleges_path, elementaires_path, maternelles_path):
```

`load_terrasses_for_arrondissements` calcule la surface en m2 de chaque terrasse (`longueur × largeur`), nettoie les arrondissements manquants et agrege par `SUM` a l'echelle arrondissement.

`load_schools_for_arrondissements` consolide trois fichiers CSV distincts (colleges, ecoles elementaires, maternelles). Pour chacun, elle filtre sur la derniere annee scolaire disponible, s'assure que le code INSEE commence par `75`, et extrait le code arrondissement. Le resultat final est un `COUNT(*)` par arrondissement tous types confondus.

#### 2.6 Chargeur generique

```python
def load_dataset(name):
```

Fonction de dispatch : resout le chemin local d'un jeu de donnees depuis le catalogue, detecte son format (`csv`, `json`, `geojson`, `xlsx`, `zip`), et appelle le reader pandas/geopandas adapte. Sert principalement pour les acces ponctuels en notebooks.

---

## 3. `src/preprocessing.py` — Preparation geospatiale

**Localisation :** `src/`
**Lignes :** ~211
**Dependances :** `geopandas`, `pandas`

### Role

Transformer les donnees brutes ponctuelles ou lineaires en indicateurs agrege a l'echelle arrondissement, via des operations d'analyse spatiale (jointures, intersections, calculs de surface et de longueur). Ce module produit la table maitre qui alimente les modeles.

### Blocs fonctionnels

#### 3.1 Reprojection et validation CRS

```python
def ensure_target_crs(geodf, target_crs="EPSG:4326"):
```

Fonction utilitaire de securite qui garantit que tout GeoDataFrame passe en argument est dans le systeme de coordonnees cible (WGS84). Si le CRS est absent, une erreur est levee. Si le CRS est different, une reprojection est effectuee. Ce controle est appele avant chaque operation spatiale pour eviter les erreurs silencieuses de superposition de couches incompatibles.

#### 3.2 Construction des 20 arrondissements

```python
def build_arrondissement_boundaries_from_iris(iris_gdf):
```

Les polygones d'arrondissements ne sont pas telecharges tels quels. Ils sont **reconstruits** par dissolution des ~1 000 polygones IRIS :

1. normalisation des codes INSEE et noms de communes ;
2. groupement (`dissolve`) par `code_insee` + `nom_commune` pour fusionner les IRIS en 20 arrondissements ;
3. extraction du code arrondissement (`01` a `20`) depuis les 2 derniers caracteres du code INSEE ;
4. verification stricte : exactement 20 lignes, codes `01` a `20` presents, aucune geometrie nulle ou vide.

Ce choix de reconstruction (plutot que le telechargement d'une couche pre-decoupee) evite d'introduire une source externe supplementaire et garantit la coherence parfaite avec les contours IRIS utilises pour les jointures spatiales.

#### 3.3 Comptage spatial de points

```python
def aggregate_points_to_arrondissement(points_gdf, arr_gdf, value_name):
```

Jointure spatiale classique (`sjoin` avec predicat `within`) : chaque point (corbeille, commerce, station) est rattache a l'arrondissement qui le contient geographiquement, puis un `groupby` + `size()` produit le comptage. Le resultat est un DataFrame avec deux colonnes : `arrondissement_code` et le nombre d'objets.

#### 3.4 Cumul de longueur de routes

```python
def aggregate_lines_length_to_arrondissement(lines_gdf, arr_gdf, value_name):
```

Operation plus complexe : les routes traversent potentiellement plusieurs arrondissements. Le bloc effectue donc :

1. une intersection geometrique (`gpd.overlay`) qui decoupe chaque troncon de route aux frontieres d'arrondissement ;
2. une reprojection en Lambert-93 (EPSG:2154, projection metrique) pour calculer les longueurs en metres ;
3. une conversion en kilometres et une sommation par arrondissement.

#### 3.5 Cumul de surface d'espaces verts

```python
def aggregate_green_area_to_arrondissement(green_gdf, arr_gdf):
```

Meme principe que le bloc precedent mais applique aux polygones : intersection des espaces verts avec les arrondissements, reprojection en Lambert-93, calcul de la surface en m2 via `.geometry.area`, puis sommation par arrondissement.

#### 3.6 Construction de la table maitre

```python
def build_master_arrondissements(arr_gdf, bins_gdf, population_df, commerce_gdf, ...):
```

Fonction pivot du pipeline. Elle enchaine 8 jointures `merge` successives (toutes en `LEFT JOIN` sur `arrondissement_code`) pour assembler la table consolidee :

| Variable | Source |
| --- | --- |
| `y_bin_count` | `aggregate_points_to_arrondissement` (corbeilles) |
| `x1_population` | `load_population_for_arrondissements` |
| `x2_commerce_restaurant_count` | `aggregate_points_to_arrondissement` (commerces) |
| `x3_transport_station_count` | `aggregate_points_to_arrondissement` (transport) |
| `x4_green_area_m2` | `aggregate_green_area_to_arrondissement` |
| `x5_road_length_km` | `aggregate_lines_length_to_arrondissement` |
| `x6_terrasse_surface_m2` | `load_terrasses_for_arrondissements` |
| `x7_school_count` | `load_schools_for_arrondissements` |

Apres l'assemblage, les valeurs manquantes sont remplies a 0, les types sont forces (entier pour les comptages, flottant pour les surfaces/longueurs), et les colonnes sont triees dans l'ordre attendu. Le resultat est un GeoDataFrame de 20 lignes et 10 colonnes (code, nom, geometrie, Y, X1..X7).

---

## 4. `src/modeling.py` — Modelisation et pipeline analytique

**Localisation :** `src/`
**Lignes :** ~685
**Dependances :** `sklearn`, `geopandas`, `matplotlib`, `numpy`, `pandas`, `json`

### Role

Script le plus volumineux du projet. Il contient la logique de modelisation complete en deux phases : la regression lineaire pedagogique (Phase 1) et le reseau de neurones (Phase 2), ainsi que la generation automatisee du rapport et de tous les artefacts de sortie.

### Blocs fonctionnels

#### 4.1 Construction de la table maitre (orchestration)

```python
def build_pedagogical_master_table(force_download=False):
```

Fonction d'orchestration qui coordonne l'ensemble du flux de donnees :

1. appelle `download_pedagogical_datasets` pour telecharger les sources manquantes ;
2. charge chacune des 11 sources via les fonctions specialisees de `data_loader.py` ;
3. appelle `build_arrondissement_boundaries_from_iris` puis `build_master_arrondissements` de `preprocessing.py` ;
4. renvoie le GeoDataFrame maitre pret pour la modelisation.

Ce bloc fait le lien entre la couche d'acquisition (data_loader) et la couche analytique (modeling).

#### 4.2 Clustering KMeans

```python
def fit_arrondissement_kmeans(X_raw, n_clusters=3):
```

1. standardise les 7 features via `StandardScaler` pour neutraliser les differences d'echelle (la population est en dizaines de milliers, les longueurs de routes sont en kilometres) ;
2. entraîne un `KMeans(n_clusters=3, n_init=20, random_state=42)` sur les vecteurs standardises ;
3. renvoie les labels de cluster et un tableau de profils moyens par cluster (moyennes des features brutes + taille du cluster).

Le nombre de clusters `K=3` est impose par la consigne pedagogique.

#### 4.3 Encodage des variables indicatrices

```python
def build_cluster_dummies(cluster_labels):
```

Convertit les labels KMeans en variables binaires (`cl_2`, `cl_3`) pour la regression lineaire. Le bloc :

1. renumerote les clusters en `1, 2, 3` par ordre d'apparition pour la lisibilite ;
2. applique un `OneHotEncoder(drop="first")` qui supprime la premiere categorie (reference) pour eviter la multi-colinearite parfaite ;
3. garantit que les colonnes `cl_2` et `cl_3` existent meme si KMeans ne produit que 2 clusters (cas de securite theorique).

#### 4.4 Regression lineaire et diagnostics

```python
def fit_multiple_linear_regression(X_reg, y):
```

Entraîne une `LinearRegression` sur les 9 colonnes (X1..X7 + cl_2 + cl_3) et renvoie :

- les predictions et residus ;
- un tableau des coefficients (intercept + pentes) ;
- les metriques in-sample : R2, R2 ajuste, RMSE, MAE.

Le R2 ajuste tient compte du rapport entre le nombre d'observations (20) et le nombre de features (9), ce qui est important pour un echantillon aussi petit.

```python
def evaluate_linear_regression_loocv(X_reg, y):
```

Validation croisee Leave-One-Out : chaque arrondissement est tour a tour exclu de l'entraînement et predit par un modele ajuste sur les 19 autres. Ce choix est motive par la taille tres reduite de l'echantillon (20 observations) ou un split classique 80/20 serait trop instable.

#### 4.5 Pipeline complet Phase 1

```python
def run_pedagogical_regression_pipeline(force_download=False):
```

Fonction principale de la Phase 1. Elle enchaine :

1. construction de la table maitre ;
2. clustering + encodage des dummies ;
3. regression lineaire + LOOCV ;
4. calcul du score prescriptif (`priority_score = y_predicted - y_observed`) ;
5. export de 8 fichiers CSV/GeoJSON dans `outputs/tables/` et `data/processed/` ;
6. export d'un JSON de synthese ;
7. generation du rapport Markdown via `write_modeling_report` ;
8. renvoi d'un dictionnaire contenant tous les artefacts (pour utilisation en notebook).

#### 4.6 Generateur de rapport Markdown

```python
def write_modeling_report(master_df, cluster_summary_df, coefficients_df, metrics_df, ranking_df):
```

Construit programmatiquement un fichier `docs/modeling_report.md` contenant :

- le cadrage pedagogique (unite d'analyse, variable cible, methode) ;
- le dictionnaire des variables du modele ;
- les profils moyens des 3 clusters ;
- l'equation de regression sous forme lisible (`Y = 123.45 + 0.001234*x1_population + ...`) ;
- le tableau de coefficients ;
- les metriques de performance ;
- le classement prescriptif des 20 arrondissements.

Ce rapport est regenere automatiquement a chaque execution du pipeline, ce qui garantit qu'il est toujours synchronise avec les donnees.

#### 4.7 Pipeline Phase 2 — Reseau de neurones (MLPRegressor)

```python
def create_feature_response_arrays(master_df):
def create_train_test_datasets(X, y, test_size=0.2, random_state=42):
def build_neural_network_pipeline():
def evaluate_regression_predictions(y_true, y_pred):
def run_phase2_neural_network_pipeline(csv_path=None, force_download=False):
```

La Phase 2 suit une progression methodique :

1. **Extraction et validation** (`create_feature_response_arrays`) : selectionne les colonnes X1..X7 et Y, force les types numeriques, verifie l'absence totale de NaN (sinon erreur explicite).

2. **Split train/test** (`create_train_test_datasets`) : separation 80/20 (16 observations train, 4 test) avec `random_state=42` pour la reproductibilite. Pas de stratification car il s'agit d'une regression (pas de classes).

3. **Construction du pipeline sklearn** (`build_neural_network_pipeline`) : cree un `Pipeline` a deux etapes :
   - `StandardScaler` : normalisation des features (centrage-reduction) ;
   - `MLPRegressor(hidden_layer_sizes=(8,4), activation='relu', solver='adam', alpha=0.001, max_iter=5000)` : reseau de neurones a deux couches cachees.

4. **Evaluation triple** : metriques calculees sur train, test et en LOOCV (Leave-One-Out sur les 20 observations). La Phase 2 compare aussi automatiquement ses resultats avec le baseline lineaire de la Phase 1.

5. **Visualisations automatiques** : trois graphiques sont generes :
   - scatterplots Y vs chaque feature X1..X7 (exploration visuelle) ;
   - actual vs predicted (diagnostic de la qualite du modele) ;
   - residus vs predicted (detection de patterns non captures).

---

## 5. `src/build_map.py` — Cartographie interactive

**Localisation :** `src/`
**Lignes :** ~122
**Dependances :** `folium`, `branca`, `geopandas`, `pandas`

### Role

Produit la carte choropleth HTML interactive qui constitue le livrable visuel principal du projet. La carte affiche le score de priorite de chaque arrondissement avec un degradage colore et des info-bulles detaillees.

### Blocs fonctionnels

#### 5.1 Chargement et jointure des donnees

```python
master_gdf = gpd.read_file(master_path)
ranking_df = pd.read_csv(ranking_path)
map_gdf = master_gdf.merge(ranking_df[["arrondissement_code", "priority_rank"]], ...)
```

Charge la geometrie des 20 arrondissements (GeoJSON), le classement prescriptif (CSV), et les joint sur le code arrondissement. Une verification post-jointure (`len == 20`) garantit l'integrite du resultat.

#### 5.2 Creation du fond de carte et de la palette

```python
fmap = folium.Map(location=[center.y, center.x], zoom_start=11, tiles="CartoDB positron")
colormap = cm.LinearColormap(colors=["#2B6CB0", "#F7FAFC", "#C53030"], vmin=..., vmax=...)
```

Le fond de carte utilise le style `CartoDB positron` (clair, lisible). La palette de couleurs est un degradage lineaire bleu → blanc → rouge : bleu pour les arrondissements en surplus (modele predit moins que l'observe), rouge pour ceux en deficit de corbeilles (modele predit plus que l'observe).

#### 5.3 Style et info-bulles

```python
def style_function(feature):
    priority_score = feature["properties"].get("priority_score")
    fill_color = colormap(priority_score)
    return {"fillColor": fill_color, "color": "#1f2937", "weight": 1.2, "fillOpacity": 0.8}

tooltip = folium.GeoJsonTooltip(fields=[...], aliases=[...])
```

Chaque arrondissement est colore en fonction de son `priority_score`. L'info-bulle affichee au survol de la souris presente 12 indicateurs : code, nom, rang de priorite, nombre de corbeilles observees et predites, score de priorite, cluster, et les valeurs X1 a X5.

Le fichier HTML genere (`outputs/priority_map.html`) est autonome et peut etre ouvert dans n'importe quel navigateur sans serveur.

---

## 6. `src/visualization.py` — Utilitaires graphiques

**Localisation :** `src/`
**Lignes :** ~77
**Dependances :** `matplotlib`, `seaborn`, `folium`, `geopandas`

### Role

Bibliotheque de fonctions courtes et reutilisables pour l'exploration visuelle des donnees, principalement utilisee dans les notebooks.

### Blocs fonctionnels

#### 6.1 Distribution univariee

```python
def plot_distribution(data, column, bins=30, figsize=(8, 5)):
```

Trace un histogramme avec courbe KDE (estimation de densite par noyau) pour explorer la distribution d'une variable numerique.

#### 6.2 Diagnostic des valeurs manquantes

```python
def plot_missing_values(data, figsize=(10, 5)):
```

Calcule le ratio de valeurs manquantes pour chaque colonne et produit un diagramme en barres trie par ordre decroissant. Utile pour un audit rapide de la qualite des donnees brutes.

#### 6.3 Choropleth statique

```python
def plot_choropleth(geodf, column, cmap="YlOrRd", figsize=(10, 10)):
```

Genere une carte statique via matplotlib/geopandas. Plus simple que la carte Folium, adaptee pour les insertions dans les rapports PDF ou les notebooks.

#### 6.4 Carte Folium generique

```python
def make_folium_map(geodf, column, tooltip_columns=None, ...):
```

Version generique simplifiee de la carte interactive (par rapport a `build_map.py` qui est specialisee pour le rendu de priorite). Utile pour des explorations ad hoc en notebook.

---

## 7. `main.py` — Orchestrateur principal

**Localisation :** racine du projet
**Lignes :** ~22
**Dependances :** `src.build_map`, `src.modeling`

### Role

Point d'entree unique du projet. Le script ne contient aucune logique metier ; il se contente d'appeler les deux fonctions de haut niveau dans l'ordre correct, puis d'afficher les chemins des artefacts produits.

### Bloc fonctionnel

```python
def main():
    outputs = run_pedagogical_regression_pipeline()
    map_path = build_arrondissement_priority_map()
    print(f"Priority ranking: {ranking_path}")
    print(f"Priority map: {map_path}")
```

1. `run_pedagogical_regression_pipeline()` : execute le pipeline complet de la Phase 1 (telechargement → preprocessing → clustering → regression → export) ;
2. `build_arrondissement_priority_map()` : construit la carte choropleth a partir des artefacts produits a l'etape precedente.

Ce decoupage permet d'executer le pipeline complet via `python main.py` ou de lancer chaque module individuellement (`python src/modeling.py`, `python src/build_map.py`).

> **Note Phase 2 :** La fonction `run_phase2_neural_network_pipeline()` est implementee dans `src/modeling.py` mais n'est **pas appelee par `main.py`**. La Phase 2 s'execute depuis `notebooks/02_modeling.ipynb` ou par appel Python direct.

---

## 8. `generate_static_map.py` — Carte PNG statique

**Localisation :** racine du projet
**Lignes :** ~41
**Dependances :** `geopandas`, `matplotlib`

### Role

Utilitaire independant qui genere une carte choropleth statique en PNG a partir du GeoJSON traite. Complement a `build_map.py` pour les contextes ou un fichier image est preferable au HTML interactif (rapports PDF, presentations).

### Bloc fonctionnel

```python
def create_static_map():
    gdf = gpd.read_file("data/processed/master_arrondissements.geojson")
    gdf.plot(column="priority_score", cmap="coolwarm", legend=True, ...)
    ax.annotate(text=str(row["arrondissement_code"]), xy=(centroid.x, centroid.y), ...)
    plt.savefig("outputs/figures/priority_map_static.png", dpi=150)
```

- Lit directement `data/processed/master_arrondissements.geojson` (doit exister)
- Applique la palette `coolwarm` sur `priority_score` (rouge = deficit, bleu = surplus)
- Annote chaque polygone avec son code arrondissement via le centroide
- Sauvegarde `outputs/figures/priority_map_static.png`

> Ce script n'est pas appele par `main.py` ; il s'execute a la demande via `python generate_static_map.py`.

---

## 9. `export_visual_report.py` — Export DOCX et PDF

**Localisation :** racine du projet
**Lignes :** ~259
**Dependances :** `beautifulsoup4`, `python-docx`, `lxml`, `subprocess`
> **Attention :** `beautifulsoup4` est absent de `requirements.txt` ; l'installer manuellement (`pip install beautifulsoup4`) avant d'utiliser ce script.

### Role

Convertit un rapport HTML (typiquement exporte depuis un notebook Jupyter) en documents professionnels Word (DOCX) et/ou PDF, prets a etre livres dans un contexte academique ou client.

### Blocs fonctionnels

#### 9.1 Interface en ligne de commande

```python
def parse_args():
    parser.add_argument("input_html", type=Path, help="Path to the HTML report.")
    parser.add_argument("--docx", ...)
    parser.add_argument("--pdf", ...)
    parser.add_argument("--no-docx", ...)
    parser.add_argument("--no-pdf", ...)
```

Le script s'utilise depuis le terminal : `python export_visual_report.py outputs/report.html`. Les options `--no-docx` et `--no-pdf` permettent de desactiver l'un ou l'autre format.

#### 9.2 Parsing HTML et extraction des blocs

```python
def iter_output_blocks(soup):
    OUTPUT_SELECTORS = (".jp-RenderedHTMLCommon", ".jp-RenderedImage", ".jp-OutputArea-output pre")
```

Le HTML d'un notebook Jupyter exporte contient des classes CSS specifiques pour les cellules de sortie. Le script utilise `BeautifulSoup` avec des selecteurs CSS pour extraire uniquement les blocs de contenu utiles (texte, images, tableaux) en ignorant le chrome d'interface de Jupyter.

#### 9.3 Conversion en DOCX

```python
def render_html_fragment(document, node, max_width_inches):
def export_docx(input_html, output_docx, max_width_inches):
```

Un moteur de rendu recursif qui parcourt l'arbre HTML noeud par noeud et genere les elements Word correspondants :

- `<h1>` a `<h4>` → titres Word avec niveaux hierarchiques ;
- `<p>` → paragraphes ;
- `<ul>` / `<ol>` → listes a puces / numerotees ;
- `<table>` → tableau Word avec grille ;
- `<img>` avec `src="data:image/..."` → image inline decodee depuis le base64 ;
- `<pre>` → bloc de code.

Les images inline (encodees en base64 dans le HTML) sont decodees et inserees dans le document Word avec une largeur maximale configurable.

#### 9.4 Conversion en PDF (via navigateur headless)

```python
def find_browser():
    COMMON_BROWSER_PATHS = (
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        ...
    )

def export_pdf(input_html, output_pdf):
    subprocess.run([str(browser), "--headless", "--print-to-pdf=...", file_url], check=True)
```

Le script detecte automatiquement la presence de Chrome ou Edge sur la machine, puis lance le navigateur en mode headless (sans interface graphique) avec l'option `--print-to-pdf` pour effectuer un rendu fidele du HTML en PDF. Ce choix garantit un rendu identique a ce que l'utilisateur voit dans son navigateur, contrairement aux convertisseurs HTML-vers-PDF tiers qui peuvent perdre des styles CSS.

---

## 10. Synthese des dependances entre scripts

Le diagramme suivant montre l'ordre d'appel entre les modules :

```text
main.py
  ├── src/modeling.py
  │     ├── src/data_loader.py
  │     │     └── config.py
  │     └── src/preprocessing.py
  │           └── config.py
  └── src/build_map.py
        └── config.py
```

Les fichiers `src/visualization.py`, `export_colab.py` et `export_visual_report.py` sont des utilitaires independants du pipeline principal. Ils sont appeles a la demande (notebooks, ligne de commande) mais ne sont pas necessaires pour l'execution de bout en bout.

---

## 11. Notebooks

Le projet contient deux notebooks Jupyter qui servent de support de presentation et d'exploration interactive :

| Notebook | Role |
| --- | --- |
| `notebooks/01_data_exploration.ipynb` | Exploration des donnees brutes : distributions, valeurs manquantes, visualisations EDA |
| `notebooks/02_modeling.ipynb` | Reproduction interactive des etapes de modelisation (Phase 1 et Phase 2) avec graphiques et commentaires |

Ces notebooks importent les fonctions des modules `src/` et s'appuient sur le meme `config.py`. Ils ne contiennent pas de logique autonome : ils appellent le code des scripts et en presentent les resultats de maniere narrative.

---

## 12. Documentation existante

| Document | Contenu |
| --- | --- |
| `RECAP.md` | Vue d'ensemble du projet : contexte, pipeline, sources, livrables, limites |
| `docs/data_and_sources.md` | Referentiel donnees : variables du modele, detail des sources, inspection APIs, table maitre |
| `docs/modeling_report.md` | Rapport auto-genere par le pipeline (equation, coefficients, metriques, classement) |
| `docs/technical_functional_traceability.md` | Tracabilite technique et fonctionnelle, historique des sprints, justifications des choix |
| `docs/scripts_technical_documentation.md` | Le present document |
