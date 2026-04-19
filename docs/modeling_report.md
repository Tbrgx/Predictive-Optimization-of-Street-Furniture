# Modeling Report

Date d'execution : 2026-04-19

## Cadrage pedagogique

- Unite d'analyse : arrondissement (20 observations)
- Variable cible Y : `y_bin_count` = nombre brut de corbeilles OSM par arrondissement
- Variables explicatives : X1 population, X2 commerces/restaurants, X3 stations de transport, X4 superficie d'espaces verts, X5 longueur de routes, X6 surface de terrasses autorisees, X7 nombre d'etablissements scolaires
- Etape 2 : KMeans avec K=3
- Etape 3 : One-Hot Encoding avec `drop_first=True` pour produire `cl_2` et `cl_3`
- Etape 4 : LinearRegression

## Variables du modele

| Colonne | Definition |
| --- | --- |
| `x1_population` | Population INSEE totale par arrondissement |
| `x2_commerce_restaurant_count` | Comptage OSM des commerces/restaurants |
| `x3_transport_station_count` | Comptage OSM des stations de transport |
| `x4_green_area_m2` | Surface totale d'espaces verts en m2 |
| `x5_road_length_km` | Longueur totale des routes OSM en km |
| `x6_terrasse_surface_m2` | Surface totale des terrasses autorisees (longueur x largeur) en m2 |
| `x7_school_count` | Nombre total d'etablissements scolaires (colleges + elementaires + maternelles) |
| `cl_2`, `cl_3` | Variables indicatrices des clusters KMeans |

## Clusters d'arrondissements

- Cluster 0 : size=9, X1=164341.7, X2=2568.8, X3=33.4, X4=482432.2, X5=140.431, X6=11935.9, X7=67.1
- Cluster 1 : size=9, X1=37234.3, X2=1949.1, X3=12.7, X4=92390.4, X5=59.465, X6=8595.9, X7=16.2
- Cluster 2 : size=2, X1=149760.5, X2=2095.0, X3=36.5, X4=9774412.9, X5=261.119, X6=13853.3, X7=42.5

## Equation finale

```text
Y = 608.402 - 0.001091*x1_population - 0.143900*x2_commerce_restaurant_count + 12.384215*x3_transport_station_count - 0.000037*x4_green_area_m2 - 0.609625*x5_road_length_km + 0.009577*x6_terrasse_surface_m2 - 1.477650*x7_school_count - 282.962159*cl_2 + 119.476536*cl_3
```

## Coefficients

| Terme | Coefficient |
| --- | ---: |
| `Intercept` | 608.402159 |
| `x1_population` | -0.001091 |
| `x2_commerce_restaurant_count` | -0.143900 |
| `x3_transport_station_count` | 12.384215 |
| `x4_green_area_m2` | -0.000037 |
| `x5_road_length_km` | -0.609625 |
| `x6_terrasse_surface_m2` | 0.009577 |
| `x7_school_count` | -1.477650 |
| `cl_2` | -282.962159 |
| `cl_3` | 119.476536 |

## Metriques

| Metrique | Valeur |
| --- | ---: |
| `r2` | 0.462293 |
| `adjusted_r2` | -0.021643 |
| `rmse` | 145.989622 |
| `mae` | 106.277379 |
| `n_rows` | 20 |
| `n_features` | 9 |
| `loocv_rmse` | 839.394164 |
| `loocv_mae` | 430.078938 |

## Classement prescriptif

- Le score de priorite est `y_predicted - y_bin_count`.
- Un score positif signifie qu'un arrondissement presente un deficit estime de corbeilles par rapport a son profil urbain.

| Rang | Arrondissement | Observe | Predit | Priority Score | Cluster |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | Paris 17e Arrondissement | 323 | 557.117 | 234.117 | 0 |
| 2 | Paris 20e Arrondissement | 172 | 322.199 | 150.199 | 0 |
| 3 | Paris 7e Arrondissement | 179 | 301.289 | 122.289 | 1 |
| 4 | Paris 16e Arrondissement | 161 | 279.372 | 118.372 | 2 |
| 5 | Paris 18e Arrondissement | 158 | 265.746 | 107.746 | 0 |
| 6 | Paris 8e Arrondissement | 177 | 279.375 | 102.375 | 1 |
| 7 | Paris 19e Arrondissement | 390 | 474.790 | 84.790 | 0 |
| 8 | Paris 2e Arrondissement | 75 | 148.373 | 73.373 | 1 |
| 9 | Paris 9e Arrondissement | 108 | 156.207 | 48.207 | 1 |
| 10 | Paris 11e Arrondissement | 123 | 144.307 | 21.307 | 0 |
| 11 | Paris 4e Arrondissement | 161 | 159.646 | -1.354 | 1 |
| 12 | Paris 14e Arrondissement | 437 | 414.880 | -22.120 | 0 |
| 13 | Paris 3e Arrondissement | 114 | 82.689 | -31.311 | 1 |
| 14 | Paris 10e Arrondissement | 384 | 352.409 | -31.591 | 0 |
| 15 | Paris 6e Arrondissement | 154 | 109.924 | -44.076 | 1 |
| 16 | Paris 15e Arrondissement | 526 | 449.715 | -76.285 | 0 |
| 17 | Paris 1er Arrondissement | 333 | 235.307 | -97.693 | 1 |
| 18 | Paris 12e Arrondissement | 367 | 248.628 | -118.372 | 2 |
| 19 | Paris 5e Arrondissement | 318 | 146.191 | -171.809 | 1 |
| 20 | Paris 13e Arrondissement | 955 | 486.837 | -468.163 | 0 |

## Conclusion

Le pipeline primaire suit maintenant strictement la logique pedagogique attendue : 20 arrondissements, clustering KMeans, variables indicatrices, puis regression lineaire multiple.