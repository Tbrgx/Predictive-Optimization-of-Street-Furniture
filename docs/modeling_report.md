# Modeling Report

Date d'execution : 2026-03-13

## Cadrage pedagogique

- Unite d'analyse : arrondissement (20 observations)
- Variable cible Y : `y_bin_count` = nombre brut de corbeilles OSM par arrondissement
- Variables explicatives : X1 population, X2 commerces/restaurants, X3 stations de transport, X4 superficie d'espaces verts, X5 longueur de routes
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
| `cl_2`, `cl_3` | Variables indicatrices des clusters KMeans |

## Clusters d'arrondissements

- Cluster 0 : size=8, X1=174643.6, X2=2509.1, X3=35.2, X4=535592.0, X5=149.471
- Cluster 1 : size=10, X1=41703.5, X2=2055.9, X3=13.3, X4=88866.7, X5=60.293
- Cluster 2 : size=2, X1=149760.5, X2=2093.5, X3=36.5, X4=9774412.9, X5=260.901

## Equation finale

```text
Y = 108.330 - 0.000807*x1_population - 0.027403*x2_commerce_restaurant_count + 10.128120*x3_transport_station_count - 0.000008*x4_green_area_m2 + 0.852140*x5_road_length_km - 5.288935*cl_2 - 179.632895*cl_3
```

## Coefficients

| Terme | Coefficient |
| --- | ---: |
| `Intercept` | 108.329682 |
| `x1_population` | -0.000807 |
| `x2_commerce_restaurant_count` | -0.027403 |
| `x3_transport_station_count` | 10.128120 |
| `x4_green_area_m2` | -0.000008 |
| `x5_road_length_km` | 0.852140 |
| `cl_2` | -5.288935 |
| `cl_3` | -179.632895 |

## Metriques

| Metrique | Valeur |
| --- | ---: |
| `r2` | 0.379454 |
| `adjusted_r2` | 0.017469 |
| `rmse` | 157.709073 |
| `mae` | 119.879948 |
| `n_rows` | 20 |
| `n_features` | 7 |
| `loocv_rmse` | 784.157608 |
| `loocv_mae` | 406.331206 |

## Classement prescriptif

- Le score de priorite est `y_predicted - y_bin_count`.
- Un score positif signifie qu'un arrondissement presente un deficit estime de corbeilles par rapport a son profil urbain.

| Rang | Arrondissement | Observe | Predit | Priority Score | Cluster |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | Paris 17e Arrondissement | 315 | 510.592 | 195.592 | 0 |
| 2 | Paris 18e Arrondissement | 126 | 299.923 | 173.923 | 0 |
| 3 | Paris 7e Arrondissement | 164 | 320.835 | 156.835 | 1 |
| 4 | Paris 20e Arrondissement | 166 | 314.388 | 148.388 | 0 |
| 5 | Paris 8e Arrondissement | 177 | 308.338 | 131.338 | 1 |
| 6 | Paris 16e Arrondissement | 160 | 278.983 | 118.983 | 2 |
| 7 | Paris 9e Arrondissement | 108 | 215.345 | 107.345 | 1 |
| 8 | Paris 2e Arrondissement | 75 | 132.964 | 57.964 | 1 |
| 9 | Paris 19e Arrondissement | 383 | 433.252 | 50.252 | 0 |
| 10 | Paris 11e Arrondissement | 123 | 158.741 | 35.741 | 0 |
| 11 | Paris 6e Arrondissement | 154 | 176.439 | 22.439 | 1 |
| 12 | Paris 15e Arrondissement | 526 | 525.431 | -0.569 | 0 |
| 13 | Paris 3e Arrondissement | 113 | 98.681 | -14.319 | 1 |
| 14 | Paris 4e Arrondissement | 160 | 140.860 | -19.140 | 1 |
| 15 | Paris 1er Arrondissement | 328 | 217.172 | -110.828 | 1 |
| 16 | Paris 14e Arrondissement | 437 | 318.618 | -118.382 | 0 |
| 17 | Paris 12e Arrondissement | 365 | 246.017 | -118.983 | 2 |
| 18 | Paris 5e Arrondissement | 319 | 169.577 | -149.423 | 1 |
| 19 | Paris 10e Arrondissement | 386 | 203.789 | -182.211 | 1 |
| 20 | Paris 13e Arrondissement | 953 | 468.054 | -484.946 | 0 |

## Conclusion

Le pipeline primaire suit maintenant strictement la logique pedagogique attendue : 20 arrondissements, clustering KMeans, variables indicatrices, puis regression lineaire multiple.