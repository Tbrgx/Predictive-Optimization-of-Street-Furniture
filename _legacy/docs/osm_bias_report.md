# OSM Bias Report

Date d'execution : 2026-03-12

## Donnees chargees
- Corbeilles OSM parsees : 5545
- IRIS Paris charges : 992
- Population INSEE Paris : 992 lignes
- Stations Trilib' actives : 439
- Espaces verts retenus apres filtres : 1513

## 1. Couverture par arrondissement
- Figure : `outputs/figures/osm_bins_by_arrondissement.png`
- Top 5 des arrondissements en nombre absolu de bins OSM : 13: 953, 15: 526, 14: 437, 10: 386, 19: 383
- Lecture : la distribution absolue suit en partie la taille et l'intensite urbaine des arrondissements. Elle ne suffit pas seule a conclure a une surrepresentation des arrondissements centraux, mais elle met en evidence une couverture tres heterogene.

## 2. Correlation biais-features
- Pearson `bin_density` vs `population_density` : -0.133
- Pearson `bin_density` vs `distance_to_paris_centroid_m` : -0.228
- Pearson `bin_density` vs `green_ratio` : 0.020
- Flag centralite (`|r| > 0.7`) : Non

## 3. Test de vraisemblance
- Reference APUR utilisee : ~26000 corbeilles
- Corbeilles OSM / reference APUR : 5545 / 26000 = 21.3%
- IRIS avec `bin_count == 0` : 268 / 992 = 27.0%
- IRIS avec `bin_count >= 1` : 724 / 992 = 73.0%
- Lecture : une couverture d'environ 21.3% avec 268 IRIS sans aucun point OSM est difficilement compatible avec un inventaire complet des corbeilles parisiennes.

## Verdict
Le biais OSM est problematique.

Le biais OSM est problematique pour la modelisation car la couverture observee est faible par rapport au stock APUR et une part importante des IRIS restent a zero, ce qui risque de confondre sous-declaration OSM et sous-equipement reel.

## Implications pour le sprint 4
- La variable cible `bin_density` doit etre interpretee comme une densite OSM observee, pas comme l'offre reelle exhaustive.
- Les metriques de performance devront etre analysees avec prudence, surtout dans les IRIS a `bin_count = 0`.
- Un controle explicite de la centralite geographique et de la densite de population est recommande dans la modelisation.

## Recommandation
- Si une source objet officielle devient disponible, il faut pivoter vers cette source pour reconstruire la variable cible.
- Sinon, conserver OSM comme proxy incomplet et ajouter des features de controle (centralite, intensite urbaine, eventuellement arrondissement fixe) ou un cadrage methodologique assumant que l'objectif devient la prediction de la couverture OSM plutot que de l'offre reelle.
