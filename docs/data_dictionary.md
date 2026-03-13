# Data Dictionary

Ce document decrit la voie primaire du projet apres la reorientation pedagogique vers un pipeline `arrondissements + KMeans + regression lineaire`.

## 1. street_bins_osm_arr

- Nom : Corbeilles de rue OSM
- Source : OpenStreetMap via Overpass API
- URL : `https://overpass-api.de/api/interpreter`
- Licence : ODbL
- Format : JSON Overpass
- Granularite : points
- Usage : variable cible `Y`
- Definition metier : objets `amenity=waste_basket` sur Paris
- Champs exploites :
  - `type` : type d'objet OSM (`node`, `way`, `relation`)
  - `id` : identifiant OSM
  - `lat`, `lon` : coordonnees des noeuds
  - `center.lat`, `center.lon` : centre des objets surfaciques ou lineaires quand disponible
  - `tags.*` : attributs OSM optionnels
- Transformation :
  - parsing JSON en GeoDataFrame de points `EPSG:4326`
  - jointure spatiale avec les 20 arrondissements
  - comptage par arrondissement -> `y_bin_count`
- Limitation :
  - fallback non exhaustif, car la source officielle PVP n'est pas exploitable comme inventaire objet

## 2. commerce_restaurants_osm

- Nom : Commerces et restaurants OSM
- Source : OpenStreetMap via Overpass API
- URL : `https://overpass-api.de/api/interpreter`
- Licence : ODbL
- Format : JSON Overpass
- Granularite : points
- Usage : variable explicative `X2`
- Definition metier :
  - `shop=*`
  - ou `amenity in {restaurant, fast_food, cafe, bar, pub}`
- Champs exploites :
  - `type`, `id`
  - `lat`, `lon`
  - `center.lat`, `center.lon`
  - `tags.shop`
  - `tags.amenity`
- Transformation :
  - parsing JSON en GeoDataFrame de points `EPSG:4326`
  - jointure spatiale avec les arrondissements
  - comptage par arrondissement -> `x2_commerce_restaurant_count`

## 3. transport_stations_osm

- Nom : Stations de transport OSM
- Source : OpenStreetMap via Overpass API
- URL : `https://overpass-api.de/api/interpreter`
- Licence : ODbL
- Format : JSON Overpass
- Granularite : points
- Usage : variable explicative `X3`
- Definition metier :
  - `railway in {station, halt, tram_stop}`
  - ou `public_transport=station`
  - ou `amenity=bus_station`
  - exclusion explicite de `subway_entrance`
- Champs exploites :
  - `type`, `id`
  - `lat`, `lon`
  - `center.lat`, `center.lon`
  - `tags.railway`
  - `tags.public_transport`
  - `tags.amenity`
- Transformation :
  - parsing JSON en GeoDataFrame de points `EPSG:4326`
  - jointure spatiale avec les arrondissements
  - comptage par arrondissement -> `x3_transport_station_count`

## 4. roads_osm

- Nom : Routes OSM
- Source : OpenStreetMap via Overpass API
- URL : `https://overpass-api.de/api/interpreter`
- Licence : ODbL
- Format : JSON Overpass
- Granularite : lignes
- Usage : variable explicative `X5`
- Definition metier :
  - `highway in {motorway, trunk, primary, secondary, tertiary, unclassified, residential, living_street, service, pedestrian}`
  - exclusion de `footway`, `path`, `cycleway`, `steps`
- Champs exploites :
  - `type`, `id`
  - `geometry` : sequence de coordonnees
  - `tags.highway`
- Transformation :
  - parsing JSON en GeoDataFrame de `LineString`
  - intersection spatiale avec les arrondissements
  - calcul de longueur en Lambert-93
  - somme par arrondissement -> `x5_road_length_km`

## 5. iris_population

- Nom : Base infracommunale - evolution et structure de la population 2022
- Source : INSEE
- URL page : `https://www.insee.fr/fr/statistiques/8647014`
- URL fichier : `https://www.insee.fr/fr/statistiques/fichier/8647014/base-ic-evol-struct-pop-2022_csv.zip`
- Licence : Licence Ouverte / Open Licence
- Format : ZIP contenant un CSV delimite par `;`
- Granularite : IRIS
- Usage : variable explicative `X1`
- Champs utilises :
  - `IRIS` : code IRIS
  - `COM` : code commune / arrondissement
  - `P22_POP` : population totale 2022
  - `P22_PMEN` : population des menages 2022
- Transformation :
  - filtre `COM` commencant par `75`
  - extraction `arrondissement_code = COM[-2:]`
  - somme de `P22_POP` par arrondissement -> `x1_population`

## 6. green_spaces

- Nom : Espaces verts et assimiles
- Source : OpenData Paris
- URL : `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/espaces_verts/exports/csv`
- Licence : ODbL
- Format : CSV
- Granularite : polygones
- Usage : variable explicative `X4`
- Filtres metier :
  - exclure `categorie = Jardiniere`
  - exclure `type_ev = Decorations sur la voie publique`
- Champs utilises :
  - `nom_ev`
  - `categorie`
  - `type_ev`
  - `geom` : geometrie polygonale
  - `geom_x_y`
- Transformation :
  - conversion en GeoDataFrame `EPSG:4326`
  - intersection avec les arrondissements
  - calcul d'aire en Lambert-93
  - somme par arrondissement -> `x4_green_area_m2`

## 7. iris_contours

- Nom : IRIS GE Paris
- Source : IGN / GeoPF
- URL technique : `https://data.geopf.fr/wfs/ows`
- Licence : Licence Ouverte / Open Licence
- Format : GeoJSON via WFS
- Granularite : IRIS
- Usage : construction des arrondissements
- Champs utilises :
  - `code_insee`
  - `nom_commune`
  - `code_iris`
  - `nom_iris`
  - `geometry`
- Transformation :
  - filtre `code_insee like '75%'`
  - dissolution par `code_insee` et `nom_commune`
  - sortie : 20 polygones arrondissement

## 8. master_arrondissements

- Nom : Table maitre arrondissement
- Fichiers produits :
  - `data/processed/master_arrondissements.csv`
  - `data/processed/master_arrondissements.geojson`
- Granularite : `1 ligne = 1 arrondissement`
- Volume attendu : `20` lignes
- Role : table primaire pour l'exploration, le clustering, la regression et la priorisation

### Colonnes

| Colonne | Type | Description |
| --- | --- | --- |
| `arrondissement_code` | texte | code `01` a `20` |
| `arrondissement_name` | texte | libelle de l'arrondissement |
| `geometry` | geometrie | polygone arrondissement en `EPSG:4326` |
| `y_bin_count` | entier | nombre brut de corbeilles OSM observees |
| `x1_population` | entier | population INSEE totale |
| `x2_commerce_restaurant_count` | entier | nombre OSM de commerces/restaurants |
| `x3_transport_station_count` | entier | nombre OSM de stations de transport |
| `x4_green_area_m2` | flottant | surface totale d'espaces verts en m2 |
| `x5_road_length_km` | flottant | longueur totale des routes en km |
| `cluster_label` | entier | cluster KMeans brut (`0`, `1`, `2`) |
| `cl_2` | entier | dummy de cluster, categorie 2 |
| `cl_3` | entier | dummy de cluster, categorie 3 |
| `y_predicted` | flottant | prediction de la regression lineaire |
| `residual` | flottant | `y_observed - y_predicted` |
| `priority_score` | flottant | `y_predicted - y_observed` |

## 9. Legacy artifacts kept for audit

Les artefacts `master_iris`, `top50_priority_iris` et la voie `IRIS + RandomForest/XGBoost` ont ete deplaces dans le dossier `_legacy/` comme historique d'audit. Ils ne font plus partie du pipeline primaire ni des livrables officiels.
