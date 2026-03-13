# Analyse d'Écart : Consignes vs Implémentation Actuelle

Ce document analyse point par point les différences majeures entre les consignes exigées (indiquées dans la demande) et l'état actuel du code du projet `paris-bins-ml`.

**Conclusion générale : Le projet actuel NE RESPECTE PAS ces consignes.**
Il a été développé avec une approche beaucoup plus granulaire (IRIS) et des algorithmes différents (Random Forest) par rapport à l'approche simplifiée demandée (Arrondissements, K-Means, Régression Linéaire).

---

## 1. Unité d'analyse (Étape 1)

| Consigne | Implémentation Actuelle | Statut |
| :--- | :--- | :--- |
| **Arrondissement** (20 observations) | **IRIS** (Infracommunal, ~992 observations) | ❌ Non respecté |

*Le projet actuel est beaucoup plus fin géographiquement, ce qui est techniquement mieux pour la précision urbaine, mais contredit la consigne stricte des 20 arrondissements.*

## 2. Variables / Features (Étape 1)

| Consigne | Implémentation Actuelle | Statut |
| :--- | :--- | :--- |
| X₁ (population) | `P22_POP`, `P22_PMEN` (INSEE) | ✅ Respecté |
| X₂ (commerces/restaurants) | ❌ Absentes totalement | ❌ Non respecté |
| X₃ (stations de transport) | ❌ Absentes (Trilib' à la place) | ❌ Non respecté |
| X₄ (superficie espaces verts) | `green_area_m2` | ✅ Respecté |
| X₅ (km de routes/densité) | ❌ Absentes | ❌ Non respecté |

*La documentation actuelle (Limitations L2) reconnaît explicitement que les features commerciales et de transports manquent.*

## 3. Clustering (Étape 2)

| Consigne | Implémentation Actuelle | Statut |
| :--- | :--- | :--- |
| K-means sur les features pour créer des profils d'arrondissements. | ❌ Aucun clustering implémenté. | ❌ Non respecté |

## 4. One-Hot Encoding / Dummy Coding (Étape 3)

| Consigne | Implémentation Actuelle | Statut |
| :--- | :--- | :--- |
| Transformation des clusters en variables binaires (`Cl1`, `Cl2`...). | ❌ Non applicable (pas de clusters). | ❌ Non respecté |

## 5. Modélisation (Étape 4)

| Consigne | Implémentation Actuelle | Statut |
| :--- | :--- | :--- |
| **Régression Linéaire Multiple** (`Y = X₁...X₅ + dummies`) | **Random Forest Regressor** et **XGBoost**. Baseline: `DummyRegressor` (médiane). | ❌ Non respecté |

*Le pipeline utilise des modèles d'ensembles non-linéaires au lieu d'une régression linéaire basique avec variables indicatrices.*

---

## Conclusion et Recommandations

L'approche actuelle est techniquement plus avancée (Machine Learning sur 992 zones IRIS avec gestion des non-linéarités via arbres de décision), mais elle est **hors-sujet** par rapport à l'exercice pédagogique demandé.

Pour respecter les consignes du professeur, il faudrait **réécrire intégralement le pipeline** :
1.  **Agréger** toutes les données au niveau Arrondissement (un `groupby` sur `arrondissement_code`).
2.  **Trouver et intégrer** des données pour les commerces, les transports et les routes (ex: requêtes OSM supplémentaires).
3.  **Remplacer** `RandomForestRegressor` par un pipeline `scikit-learn` comprenant :
    *   `KMeans` pour obtenir les labels de clusters.
    *   `OneHotEncoder` pour les transformer en dummies.
    *   `LinearRegression` pour le modèle prédictif final.
