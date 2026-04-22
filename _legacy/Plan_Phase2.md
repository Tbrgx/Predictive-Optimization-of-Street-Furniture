# Plan de finalisation de la phase 2 `arrondissements + train/test + neural network`

## Résumé

État actuel du repo après audit :

- **Step 1 est couvert** : dépendances Python, modules `src/`, notebooks, config, loaders.
- **Step 2 est partiellement couvert** : le notebook [02_modeling.ipynb](/c:/Bin Placement Project/paris-bins-ml/notebooks/02_modeling.ipynb) et [01_data_exploration.ipynb](/c:/Bin Placement Project/paris-bins-ml/notebooks/01_data_exploration.ipynb) contiennent lecture des données, statistiques descriptives, contrôle des NA, corrélations et quelques visualisations.
- **Step 2 n’est pas complet au sens demandé** : il manque des scatterplots systématiques et une séparation claire entre “EDA phase 1” et “préparation phase 2”.
- **Steps 3, 4 et 5 sont absents** dans le sens de ta consigne actuelle :
  - pas de création explicite de `X` et `y`,
  - pas de `train/test split`,
  - pas de modèle de **neural network**,
  - pas de rapport d’évaluation correspondant.
- Le repo est aujourd’hui centré sur une **régression linéaire multiple avec KMeans** ; cette logique doit devenir **secondaire / baseline**, pas la phase 2 finale.

Choix verrouillés pour le plan :

- maille conservée : **20 arrondissements** ;
- implémentation du NN : **`sklearn.neural_network.MLPRegressor`** ;
- livraison : **pipeline dans `src/` + notebook pédagogique** ;
- évaluation : **train/test split + LOOCV**.

## Changements d’implémentation

### 1. Stabiliser la base de données de phase 2

- Conserver [src/data_loader.py](/c:/Bin Placement Project/paris-bins-ml/src/data_loader.py) et [src/preprocessing.py](/c:/Bin Placement Project/paris-bins-ml/src/preprocessing.py) comme socle de construction de `master_arrondissements`.
- Ajouter dans [config.py](/c:/Bin Placement Project/paris-bins-ml/config.py) les constantes de phase 2 :
  - `PHASE2_FEATURE_COLUMNS = ["x1_population", "x2_commerce_restaurant_count", "x3_transport_station_count", "x4_green_area_m2", "x5_road_length_km"]`
  - `PHASE2_TARGET_COLUMN = "y_bin_count"`
  - `PHASE2_TEST_SIZE = 0.2`
  - `PHASE2_RANDOM_STATE = 42`
  - `MLP_HIDDEN_LAYER_SIZES = (8, 4)`
  - `MLP_ACTIVATION = "relu"`
  - `MLP_SOLVER = "adam"`
  - `MLP_ALPHA = 0.001`
  - `MLP_MAX_ITER = 5000`
- Faire de `master_arrondissements.csv` la table de travail officielle pour toute la phase 2.

### 2. Réécrire la phase 2 dans `src/modeling.py`

- Conserver le chargement de `master_arrondissements`, mais ajouter un chemin principal orienté “Step 3 -> Step 5”.
- Exposer ces fonctions comme interface publique :
  - `load_master_arrondissements(...)`
  - `create_feature_response_arrays(master_df) -> tuple[pd.DataFrame, pd.Series]`
  - `create_train_test_datasets(X, y, test_size=0.2, random_state=42) -> dict[str, pd.DataFrame | pd.Series]`
  - `build_neural_network_pipeline() -> sklearn.pipeline.Pipeline`
  - `evaluate_regression_predictions(y_true, y_pred) -> dict[str, float]`
  - `run_phase2_neural_network_pipeline(...) -> dict[str, Any]`
- `create_feature_response_arrays` devra :
  - sélectionner strictement `X1..X5`,
  - sélectionner `y_bin_count` comme cible,
  - contrôler les types numériques,
  - vérifier l’absence de `NaN`,
  - retourner `X` et `y` dans un format prêt pour scikit-learn.
- `create_train_test_datasets` devra utiliser :
  - `train_test_split(X, y, test_size=0.2, random_state=42)`
  - sans stratification, car il s’agit d’une régression.
- `build_neural_network_pipeline` devra utiliser :
  - `Pipeline([("scaler", StandardScaler()), ("mlp", MLPRegressor(...))])`
  - hyperparamètres fixes :
    - `hidden_layer_sizes=(8, 4)`
    - `activation="relu"`
    - `solver="adam"`
    - `alpha=0.001`
    - `max_iter=5000`
    - `random_state=42`
- `run_phase2_neural_network_pipeline` devra :
  - construire ou charger `master_arrondissements`,
  - créer `X` et `y`,
  - produire les jeux `X_train`, `X_test`, `y_train`, `y_test`,
  - entraîner le MLP,
  - prédire sur train et test,
  - calculer métriques train, test et LOOCV,
  - exporter les résultats.

### 3. Garder la régression actuelle comme baseline, pas comme chemin principal

- Ne pas supprimer la logique actuelle `KMeans + LinearRegression`.
- La déplacer clairement dans un rôle de **baseline / comparaison**.
- Le rapport de phase 2 devra comparer :
  - **baseline linéaire actuelle**
  - **MLPRegressor**
- La conclusion officielle devra porter sur le réseau de neurones, puisque c’est la phase 2 à finaliser.

### 4. Compléter la phase 2 dans les notebooks et les livrables

- Réécrire [notebooks/02_modeling.ipynb](/c:/Bin Placement Project/paris-bins-ml/notebooks/02_modeling.ipynb) pour suivre exactement les étapes :
  1. chargement de `master_arrondissements`
  2. création de `X` et `y`
  3. création du split train/test
  4. entraînement du réseau de neurones
  5. prédictions
  6. métriques
  7. visualisations d’évaluation
- Compléter [notebooks/01_data_exploration.ipynb](/c:/Bin Placement Project/paris-bins-ml/notebooks/01_data_exploration.ipynb) avec :
  - scatterplots `Y` vs `X1..X5`
  - matrice de corrélation lisible
  - tableau explicite des valeurs manquantes
  - note claire sur l’absence ou la nécessité de feature engineering supplémentaire
- Mettre à jour [docs/modeling_report.md](/c:/Bin Placement Project/paris-bins-ml/docs/modeling_report.md) pour qu’il documente :
  - les arrays `X` et `y`,
  - le split train/test,
  - l’architecture du MLP,
  - les métriques train/test/LOOCV,
  - la comparaison avec la baseline linéaire.
- Restaurer un vrai [README.md](/c:/Bin Placement Project/paris-bins-ml/README.md) comme point d’entrée officiel si sa suppression locale est bien l’état courant voulu du repo ; sinon le recréer proprement en cohérence avec la nouvelle phase 2.

### 5. Sorties à produire

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
- `docs/modeling_report.md`

## Tests et scénarios d’acceptation

- `master_arrondissements` contient bien **20 lignes** et les colonnes `X1..X5 + Y`.
- `create_feature_response_arrays` retourne :
  - `X.shape == (20, 5)`
  - `y.shape == (20,)`
- `X` ne contient aucun `NaN`.
- Le split produit :
  - `16` lignes train
  - `4` lignes test
- Le pipeline MLP s’entraîne sans erreur et retourne des prédictions de taille correcte sur train et test.
- Les métriques exportées contiennent au minimum :
  - `train_r2`, `train_rmse`, `train_mae`
  - `test_r2`, `test_rmse`, `test_mae`
  - `loocv_r2`, `loocv_rmse`, `loocv_mae`
- Le notebook `02_modeling.ipynb` reflète exactement les Steps 3, 4 et 5.
- Le repo ne présente plus la régression linéaire comme “phase 2 finale”, mais comme baseline ou héritage pédagogique.
- Les scatterplots de `01_data_exploration.ipynb` couvrent `Y` vs chacun des `X1..X5`.

## Hypothèses et défauts retenus

- On **garde la maille arrondissement**, même si elle est faible pour un réseau de neurones ; cette limite devra être documentée explicitement.
- On utilise **`MLPRegressor` de scikit-learn**, sans ajout de TensorFlow/Keras.
- On respecte la consigne de **train/test split**, mais on ajoute **LOOCV** pour rendre l’évaluation un peu plus robuste avec seulement 20 observations.
- La cible reste `y_bin_count` brute.
- Aucun feature engineering supplémentaire n’est ajouté par défaut, sauf si l’EDA montre un besoin clair et simple à justifier pédagogiquement.
- La régression linéaire actuelle est conservée comme **baseline comparative**, pas supprimée.
