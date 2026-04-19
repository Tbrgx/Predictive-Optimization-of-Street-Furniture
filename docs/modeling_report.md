# Modeling Report – Phase 2

Date d'exécution : 2026-04-19

---

## Cadrage pédagogique

- Unité d'analyse : arrondissement (20 observations)
- Variable cible Y : `y_bin_count` = nombre brut de corbeilles OSM par arrondissement
- Variables explicatives : X1 population, X2 commerces/restaurants, X3 stations de transport, X4 superficie d'espaces verts, X5 longueur de routes
- Phase 2 : MLPRegressor (réseau de neurones, scikit-learn)
- Phase 1 (baseline) : KMeans K=3 → One-Hot Encoding → LinearRegression

---

## Variables du modèle

| Colonne | Définition |
| --- | --- |
| `x1_population` | Population INSEE totale par arrondissement |
| `x2_commerce_restaurant_count` | Comptage OSM des commerces/restaurants |
| `x3_transport_station_count` | Comptage OSM des stations de transport |
| `x4_green_area_m2` | Surface totale d'espaces verts en m² |
| `x5_road_length_km` | Longueur totale des routes OSM en km |
| `y_bin_count` | Cible : nombre de corbeilles par arrondissement |

---

## Arrays X et y

- `X.shape = (20, 5)` — 20 arrondissements, 5 features (X1..X5)
- `y.shape = (20,)` — 20 valeurs cibles `y_bin_count`
- Aucune valeur manquante

---

## Split train/test

- Méthode : `train_test_split(test_size=0.2, random_state=42)` — sans stratification (régression)
- Train : 16 observations
- Test : 4 observations

---

## Architecture du réseau de neurones

- Implémentation : `sklearn.neural_network.MLPRegressor`
- Pipeline : `StandardScaler` → `MLPRegressor`
- `hidden_layer_sizes = (8, 4)` — deux couches cachées
- `activation = "relu"`
- `solver = "adam"`
- `alpha = 0.001` (régularisation L2)
- `max_iter = 5000`
- `random_state = 42`

**Note pédagogique :** avec seulement 20 observations, un réseau de neurones est structurellement en sur-apprentissage. Les résultats du test set (R² négatif) et de la LOOCV illustrent exactement cette limite, ce qui en fait un exemple pédagogique précieux. La puissance expressive du MLP est inadaptée à cette maille ; la baseline linéaire est plus robuste à cette échelle.

---

## Métriques — Réseau de neurones (MLPRegressor)

| Métrique | Valeur |
| --- | ---: |
| `train_r2` | 0.631194 |
| `train_rmse` | 127.790 |
| `train_mae` | 98.436 |
| `test_r2` | -3.8665 |
| `test_rmse` | 207.139 |
| `test_mae` | 176.095 |
| `loocv_r2` | -0.7193 |
| `loocv_rmse` | 261.055 |
| `loocv_mae` | 215.391 |

---

## Métriques — Baseline linéaire (KMeans + LinearRegression)

| Métrique | Valeur |
| --- | ---: |
| `r2` (in-sample) | 0.394934 |
| `adjusted_r2` | 0.041979 |
| `rmse` (in-sample) | 154.864 |
| `mae` (in-sample) | 117.955 |
| `n_rows` | 20 |
| `n_features` | 7 |
| `loocv_rmse` | 792.964 |
| `loocv_mae` | 407.096 |

---

## Comparaison MLP vs Baseline linéaire

| Métrique | MLP (phase 2) | Baseline linéaire |
| --- | ---: | ---: |
| R² train | 0.631 | 0.395 (in-sample) |
| RMSE test | 207.1 | — |
| LOOCV RMSE | 261.1 | 793.0 |
| LOOCV MAE | 215.4 | 407.1 |

**Interprétation :** Le MLP affiche un R² train plus élevé (sur-apprentissage), mais une RMSE LOOCV de 261 vs 793 pour la baseline. Cette comparaison doit être interprétée avec prudence : avec 20 observations, les deux modèles sont hors de leur domaine de validité statistique. La baseline linéaire simple (sans clustering) serait probablement plus stable.

---

## Conclusion

La phase 2 implémente le pipeline complet `X/y → train/test split → MLPRegressor → évaluation`. Les résultats confirment la limitation documentée dans le plan : la maille arrondissement (20 observations) est insuffisante pour un réseau de neurones. Ce pipeline reste un exemple pédagogique illustrant le sur-apprentissage, la nécessité du LOOCV avec des jeux de données très petits, et la comparaison rigoureuse avec une baseline.
