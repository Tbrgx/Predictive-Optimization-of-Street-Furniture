# API Exploration Report

Rapport d'inspection des 5 datasets prioritaires du projet `paris-bins-ml`.
Date d'inspection : 2026-03-12.

Perimetre de l'inspection :
- OpenData Paris : metadonnees via `/catalog/datasets/{dataset_id}` et echantillons via `/records?limit=5`
- IRIS : recherche de la source la plus recente sur data.gouv.fr, puis inspection WFS IGN/GeoPF (`DescribeFeatureType`, `GetFeature`, `resultType=hits`)
- Population INSEE : inspection de la page source officielle et lecture en flux du debut de l'archive CSV ZIP pour lire l'entete et 5 lignes sans persistance locale

## Corbeilles de rue / mobiliers urbains

- **Dataset ID** : `plan-de-voirie-mobiliers-urbains-jardinieres-bancs-corbeilles-de-rue`
- **URL source** : `https://opendata.paris.fr/explore/dataset/plan-de-voirie-mobiliers-urbains-jardinieres-bancs-corbeilles-de-rue`
- **URL metadonnees** : `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/plan-de-voirie-mobiliers-urbains-jardinieres-bancs-corbeilles-de-rue`
- **URL echantillon** : `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/plan-de-voirie-mobiliers-urbains-jardinieres-bancs-corbeilles-de-rue/records?limit=5`
- **Nombre total de records** : `273306`
- **Derniere mise a jour** : `2026-02-14T07:26:14+00:00`
- **Champs disponibles** :

| Nom du champ | Type | Description | Utile pour le projet ? |
|---|---|---|---|
| `objectid` | `int` | Identifiant technique de ligne | Oui - dedoublonnage et tracabilite |
| `num_pave` | `text` | Code PVP / pave graphique. L'investigation complementaire montre qu'il ne s'agit pas d'une classe objet exploitable | Non pour le ciblage corbeilles |
| `igds_level` | `int` | Niveau technique interne | Peu - champ metier non documente |
| `lib_level` | `text` | Niveau thematique (`ENVIRONNEMENT` sur tout l'echantillon/agregat) | Faiblement - confirme seulement la famille globale |
| `lib_classe` | `text` | Classe metier | Non en l'etat - null sur `273306/273306` lignes |
| `geo_shape` | `geo_shape` | Geometrie GeoJSON. Type observe : `LineString` | Oui - jointure spatiale possible |
| `geo_point_2d` | `geo_point_2d` | Point simplifie avec `lat` / `lon` | Oui - point WGS84 pratique pour l'analyse |

- **Champ geographique** : `geo_point_2d` (lat/lon) et `geo_shape` (GeoJSON `LineString` observe sur les 5 premieres lignes). Le format de sortie API est compatible `EPSG:4326`, meme si la description du PVP rappelle une chaine historique de reprojections dans les SI de la Ville.
- **Echantillon** :

| objectid | num_pave | igds_level | lib_level | lib_classe | geo_point_2d | geo_shape |
|---|---|---|---|---|---|---|
| `79987` | `161N` | `15` | `ENVIRONNEMENT` | `null` | `48.854433, 2.241983` | `LineString` |
| `80022` | `163G` | `15` | `ENVIRONNEMENT` | `null` | `48.872234, 2.278859` | `LineString` |
| `80034` | `162N` | `15` | `ENVIRONNEMENT` | `null` | `48.866998, 2.239536` | `LineString` |
| `80069` | `122F` | `15` | `ENVIRONNEMENT` | `null` | `48.826116, 2.419734` | `LineString` |
| `80100` | `204A` | `15` | `ENVIRONNEMENT` | `null` | `48.856486, 2.403154` | `LineString` |

- **Observations** :
  - Le titre et la description du dataset indiquent explicitement un regroupement de `Jardinieres`, `Bancs` et `Corbeilles de rue`.
  - Le champ qui devrait permettre le filtrage fin (`lib_classe`) n'est pas exploitable car il est vide sur tout le dataset inspecte.
  - Tous les enregistrements inspectes possedent `geo_point_2d` et `geo_shape`.
  - La geometrie exposee est une `LineString` tres courte, pas un `Point` pur ; `geo_point_2d` sera plus simple pour la phase descriptive.
  - Le dataset ne permet pas, a lui seul, de compter de facon fiable les seules corbeilles.
- **Filtre a appliquer** : aucun filtre fiable n'est disponible dans le schema API courant. La source est consideree comme **bloquante** pour la variable cible tant qu'une source objet ou une table de correspondance fiable n'a pas ete trouvee.

### Investigation complementaire du bloqueur corbeilles

- **Recherche catalogue Paris Data** :
  - La recherche `https://opendata.paris.fr/api/v2/catalog/datasets?search=corbeille`
  - ainsi que les variantes `corbeilles`, `poubelle`, `borne de proprete`
  - ne remontent qu'un seul dataset : le PVP mixte `plan-de-voirie-mobiliers-urbains-jardinieres-bancs-corbeilles-de-rue`
- **Documentation PVP** :
  - L'attachement PDF `Plan_Voirie_Paris_Cahier_Des_Normes_PartieA_20170616.pdf`
  - documente bien des symboles de corbeilles / bornes de proprete (`POU`, `POUP`, `PRE`)
  - mais ne fournit pas de table liant ces symboles aux valeurs publiees dans `num_pave`
- **Service ArcGIS source** :
  - Couche inspectee : `https://capgeo2.paris.fr/opendata/rest/services/ECHANGES/DU_PLUb_PlanDetaille/MapServer/66?f=json`
  - Champs supplementaires exposes : `igds_basename`, `igds_style`, `igds_element_type`, `igds_symbology`
  - Aucun de ces champs n'est documente comme une classe metier "corbeille / banc / jardiniere"
- **Conclusion sur `num_pave`** :
  - `num_pave` ne ressemble pas a un type de mobilier
  - le meme code est spatialement tres localise, ce qui suggere plutot un code de pave / source graphique
  - dans un petit emprise autour d'un point `011A`, le service renvoie plusieurs primitives quasi superposees avec des `igds_element_type` differents
  - cela indique que la couche represente un dessin vectoriel du plan de voirie, pas un inventaire 1 ligne = 1 objet
- **Confrontation avec les ordres de grandeur officiels** :
  - La Ville de Paris communique sur environ `30 000` corbeilles de rue : `https://www.paris.fr/pages/agir-pour-la-proprete-de-ma-ville-2015`
  - Le PVP ouvert contient `273306` lignes dans l'API OpenData Paris et `275570` primitives dans le service ArcGIS source
  - L'ecart d'ordre de grandeur confirme qu'un comptage brut des lignes PVP n'est pas exploitable comme cible ML
- **Fallback teste** :
  - OpenStreetMap / Overpass (`amenity=waste_basket` sur Paris) retourne `5545` objets au `2026-03-12`
  - La structure est propre et point a point, mais la couverture apparait tres incomplete par rapport aux `~30000` corbeilles annoncees par la Ville
- **Decision de sprint** :
  - ne pas utiliser la couche PVP comme variable cible brute
  - ne pas lancer l'ingestion `street_bins` officielle tant qu'une source corbeilles objet ou une correspondance fiable n'est pas disponible
  - conserver OSM uniquement comme fallback methodologique explicite, pas comme equivalent officiel

## Stations Trilib'

> **Note (post-reorientation)** : Cette source n'est plus utilisee dans le pipeline primaire. Elle est conservee ici uniquement comme trace de l'exploration initiale. Le pipeline pedagogique utilise les stations de transport OSM (`X3`) a la place.

- **Dataset ID** : `dechets-menagers-points-dapport-volontaire-stations-trilib`
- **URL source** : `https://opendata.paris.fr/explore/dataset/dechets-menagers-points-dapport-volontaire-stations-trilib`
- **URL metadonnees** : `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/dechets-menagers-points-dapport-volontaire-stations-trilib`
- **URL echantillon** : `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/dechets-menagers-points-dapport-volontaire-stations-trilib/records?limit=5`
- **Nombre total de records** : `439`
- **Derniere mise a jour** : `2026-03-12T06:00:13+00:00`
- **Champs disponibles** :

| Nom du champ | Type | Description | Utile pour le projet ? |
|---|---|---|---|
| `identifiant` | `text` | Identifiant de station | Oui - cle technique |
| `adr` | `text` | Adresse de la station | Oui - QA et restitution |
| `arrdt` | `text` | Code arrondissement / code postal (`750xx`) | Oui - controle geographique rapide |
| `emplacement_statut` | `text` | Statut de l'emplacement | Oui - permet de filtrer les stations actives |
| `geo_shape` | `geo_shape` | Geometrie GeoJSON, type observe `Point` | Oui - jointure spatiale |
| `geo_point_2d` | `geo_point_2d` | Coordonnees `lat` / `lon` | Oui - point WGS84 directement exploitable |

- **Champ geographique** : `geo_shape` (`Point`) et `geo_point_2d` (`lat` / `lon`). Format compatible `EPSG:4326`.
- **Echantillon** :

| identifiant | adr | arrdt | emplacement_statut | geo_point_2d | geo_shape |
|---|---|---|---|---|---|
| `4618` | `52 BOULEVARD EDGAR QUINET` | `75014` | `Mobilier en service` | `48.841040, 2.325639` | `Point` |
| `4681` | `156 RUE DE PICPUS` | `75012` | `Mobilier en service` | `48.834932, 2.403847` | `Point` |
| `5509` | `48 RUE SAINT LAZARE` | `75009` | `Mobilier en service` | `48.876922, 2.334683` | `Point` |
| `5490` | `203 RUE DE LOURMEL` | `75015` | `Mobilier en service` | `48.836709, 2.280924` | `Point` |
| `4922` | `19 RUE POLONCEAU` | `75018` | `Mobilier en service` | `48.885687, 2.353263` | `Point` |

- **Observations** :
  - Les `439` lignes inspectees sont toutes en `Mobilier en service`.
  - Les 20 arrondissements de Paris sont representes dans l'agregat par `arrdt`.
  - Les coordonnees sont propres et immediatement exploitables pour la jointure spatiale.
  - Le schema est compact et stable, avec peu de risques de nettoyage lourd.
- **Filtre a appliquer** : conserver `emplacement_statut = "Mobilier en service"` ; ce filtre est aujourd'hui neutre sur l'extract inspecte mais reste prudent pour les mises a jour futures.

## Espaces verts et assimiles

- **Dataset ID** : `espaces_verts`
- **URL source** : `https://opendata.paris.fr/explore/dataset/espaces_verts`
- **URL metadonnees** : `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/espaces_verts`
- **URL echantillon** : `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/espaces_verts/records?limit=5`
- **Nombre total de records** : `2527`
- **Derniere mise a jour** : `2026-03-12T14:25:22+00:00`
- **Champs disponibles** :

| Nom du champ | Type | Description | Utile pour le projet ? |
|---|---|---|---|
| `nsq_espace_vert` | `int` | Identifiant espace vert | Oui - cle technique |
| `nom_ev` | `text` | Nom de l'espace vert | Oui - QA et restitution |
| `type_ev` | `text` | Typologie d'espace vert | Oui - filtre metier |
| `categorie` | `text` | Categorie | Oui - filtre metier |
| `adresse_numero` | `int` | Adresse - numero | Peu - information de restitution |
| `adresse_complement` | `text` | Adresse - complement | Peu |
| `adresse_typevoie` | `text` | Type de voie | Peu |
| `adresse_libellevoie` | `text` | Libelle de voie | Peu |
| `adresse_codepostal` | `text` | Code postal | Oui - controle geographique |
| `poly_area` | `int` | Surface calculee | Oui - variable surfacique utile |
| `surface_totale_reelle` | `int` | Superficie totale reelle | Oui - variable principale |
| `surface_horticole` | `int` | Surface horticole | Oui - variable secondaire pertinente |
| `presence_cloture` | `text` | Presence cloture | Peut-etre - proxy d'accessibilite |
| `perimeter` | `double` | Perimetre | Peu - utile seulement pour analyses morphologiques |
| `annee_ouverture` | `date` | Annee d'ouverture | Peu - hors package 1 |
| `annee_renovation` | `date` | Annee de renovation | Peu |
| `ancien_nom_ev` | `text` | Ancien nom | Non |
| `annee_changement_nom` | `date` | Annee de changement de nom | Non |
| `nb_entites` | `int` | Nombre d'entites | Peut-etre - utile pour QA |
| `ouvert_ferme` | `text` | Ouverture 24h/24h | Oui - proxy d'accessibilite |
| `id_division` | `int` | Identifiant division | Non - technique |
| `id_atelier_horticole` | `int` | Identifiant atelier horticole | Non - technique |
| `ida3d_enb` | `text` | Identifiant interne | Non - technique |
| `site_villes` | `text` | Code interne site | Non - technique |
| `id_eqpt` | `text` | Identifiant equipement | Non - technique |
| `competence` | `text` | Competence de gestion | Peu - peut aider a filtrer |
| `geom` | `geo_shape` | Geometrie polygonale (`Polygon` / `MultiPolygon`) | Oui - base des intersections spatiales |
| `url_plan` | `text` | Lien plan | Non |
| `geom_x_y` | `geo_point_2d` | Centroide `lat` / `lon` | Oui - QA rapide |
| `last_edited_user` | `text` | Dernier editeur | Non |
| `last_edited_date` | `datetime` | Derniere edition | Non - vide sur l'agregat inspecte |

- **Champ geographique** : `geom` (GeoJSON `Polygon` / `MultiPolygon`) et `geom_x_y` (centroide `lat` / `lon`). Les coordonnees observees sont compatibles `EPSG:4326`.
- **Echantillon** :

| nsq_espace_vert | nom_ev | type_ev | categorie | adresse_codepostal | surface_totale_reelle | geom_x_y | geom |
|---|---|---|---|---|---|---|---|
| `13077` | `JARDINIERES DU SQUARE DE LA SALAMANDRE` | `Décorations sur la voie publique` | `Jardiniere` | `75020` | `731` | `48.857902, 2.405861` | `MultiPolygon` |
| `11769` | `PROMENADE PC 12 - DAUMESNIL - SAHEL` | `Promenades ouvertes` | `Promenade` | `75012` | `11886` | `48.838469, 2.406751` | `MultiPolygon` |
| `237` | `SQUARE GUSTAVE MESUREUR` | `Promenades ouvertes` | `Square` | `75013` | `3200` | `48.833741, 2.362371` | `Polygon` |
| `13147` | `JARDINS DES CHAMPS ELYSEES- SQUARE DE BERLIN- WILLY BRANDT` | `Promenades ouvertes` | `Jardin` | `75008` | `1096` | `48.867149, 2.310672` | `Polygon` |
| `103` | `JARDIN DE KYIV` | `Promenades ouvertes` | `Jardin` | `75008` | `6489` | `48.865376, 2.314655` | `Polygon` |

- **Observations** :
  - Le jeu n'est pas limite aux parcs/jardins : il contient aussi `Jardiniere`, `Murs vegetalises`, `Talus`, `Decoration`, `Cimetiere`, etc.
  - `categorie = Jardiniere` est la premiere categorie (`866` lignes), ce qui peut biaiser un indicateur de "surface d'espaces verts" si on garde tout sans filtre.
  - Des valeurs manquantes sont visibles sur les champs surfaciques : `poly_area` renseigne `1944/2527` lignes, `surface_totale_reelle` `1928/2527`, `surface_horticole` `1853/2527`.
  - `geom` et `geom_x_y` sont renseignes sur `2525/2527` lignes.
  - `last_edited_date` est vide sur tout l'agregat inspecte.
- **Filtre a appliquer** : a minima, exclure les objets purement decoratifs si la feature cible est la surface d'espaces verts accessibles ou structurants. Premier filtre recommande a tester :
  - exclure `categorie = 'Jardiniere'`
  - exclure `type_ev = 'Decorations sur la voie publique'`
  - evaluer ensuite le maintien ou non de `Murs vegetalises`, `Talus`, `Decoration`

## Contours IRIS (source retenue)

- **Dataset ID** : `iris-ge` sur data.gouv.fr, couche WFS `STATISTICALUNITS.IRISGE:iris_ge`
- **Page source** : `https://www.data.gouv.fr/fr/datasets/iris-ge/`
- **URL WFS capabilities** : `https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetCapabilities`
- **URL schema** : `https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=DescribeFeatureType&TYPENAMES=STATISTICALUNITS.IRISGE:iris_ge`
- **URL echantillon Paris** : `https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=STATISTICALUNITS.IRISGE:iris_ge&OUTPUTFORMAT=application/json&COUNT=5&SRSNAME=EPSG:4326&CQL_FILTER=code_insee%20like%20%2775%25%27`
- **Nombre total de records** : `992` apres filtre `code_insee like '75%'`
- **Derniere mise a jour** : `2026-03-12T14:22:17+00:00` sur la page data.gouv
- **Champs disponibles** :

| Nom du champ | Type | Description | Utile pour le projet ? |
|---|---|---|---|
| `cleabs` | `string` | Cle absolue IGN technique | Peu - identifiant technique |
| `code_insee` | `string` | Code commune / arrondissement | Oui - filtre Paris et QA |
| `nom_commune` | `string` | Nom de la commune / arrondissement | Oui - restitution |
| `iris` | `string` | Numero IRIS court | Peu - moins robuste que `code_iris` |
| `code_iris` | `string` | Code IRIS complet | Oui - cle de jointure principale |
| `nom_iris` | `string` | Libelle IRIS | Oui - restitution et controle |
| `type_iris` | `string` | Type IRIS | Oui - variable de contexte |
| `geometrie` | `MultiSurfacePropertyType` | Geometrie polygonale | Oui - support de la jointure spatiale |

- **Champ geographique** : `geometrie`, type observe `MultiPolygon`. En WFS, le `SRSNAME=EPSG:4326` permet d'obtenir directement un flux compatible WGS84.
- **Echantillon** :

| code_insee | nom_commune | iris | code_iris | nom_iris | type_iris | geometrie |
|---|---|---|---|---|---|---|
| `75108` | `Paris 8e Arrondissement` | `3006` | `751083006` | `Faubourg du Roule 6` | `A` | `MultiPolygon` |
| `75109` | `Paris 9e Arrondissement` | `3307` | `751093307` | `Saint-Georges 7` | `H` | `MultiPolygon` |
| `75110` | `Paris 10e Arrondissement` | `4009` | `751104009` | `Hôpital Saint-Louis 9` | `H` | `MultiPolygon` |
| `75109` | `Paris 9e Arrondissement` | `3608` | `751093608` | `Rochechouart 8` | `H` | `MultiPolygon` |
| `75105` | `Paris 5e Arrondissement` | `1706` | `751051706` | `Saint-Victor 6` | `A` | `MultiPolygon` |

- **Observations** :
  - La source `iris-ge` est plus recente que le fallback `contours-iris-r` actuellement reference dans `config.py`.
  - Le filtre `code_insee like '75%'` retourne exactement `992` IRIS pour Paris.
  - Les `20` arrondissements sont couverts (`75101` a `75120`).
  - `code_iris` est la cle de jointure naturelle avec les donnees de population INSEE.
- **Filtre a appliquer** : `code_insee like '75%'`.

## Population INSEE par IRIS

- **Dataset ID** : `base-ic-evol-struct-pop-2022`
- **Page source** : `https://www.insee.fr/fr/statistiques/8647014`
- **URL fichier CSV ZIP** : `https://www.insee.fr/fr/statistiques/fichier/8647014/base-ic-evol-struct-pop-2022_csv.zip`
- **Format** : archive ZIP contenant un CSV delimite par `;`
- **Nombre total de records** : non expose par un endpoint de metadonnees. Le fichier est national et couvre l'ensemble des IRIS / pseudo-IRIS du perimetre diffuse.
- **Derniere mise a jour** : page INSEE 2022 la plus recente identifiee pour cette base ; version 2022 diffusee en 2025
- **Champs disponibles** :

| Nom du champ | Type | Description | Utile pour le projet ? |
|---|---|---|---|
| `IRIS` | `text` | Code IRIS | Oui - cle de jointure avec `code_iris` |
| `COM` | `text` | Code commune / arrondissement | Oui - filtre Paris (`75xxx`) |
| `TYP_IRIS` | `text` | Type IRIS | Oui - variable de contexte |
| `LAB_IRIS` | `text` | Libelle IRIS | Oui - restitution |
| `P22_POP` | `double` | Population totale 2022 | Oui - feature principale |
| `P22_POP0002` a `P22_POP80P` | `double` | Population par classes d'age fines | Oui - demande potentielle |
| `P22_POP0014` a `P22_POP65P` | `double` | Population par classes d'age agregees | Oui - alternatives plus compactes |
| `P22_POPH`, `P22_H0014` ... `P22_H65P` | `double` | Population masculine par classes d'age | Peut-etre - enrichissement |
| `P22_POPF`, `P22_F0014` ... `P22_F65P` | `double` | Population feminine par classes d'age | Peut-etre - enrichissement |
| `C22_POP15P` et sous-variables `STAT_GSEC*` | `double` | Structure socio-professionnelle des 15 ans ou plus | Peut-etre - utile en sprint ML |
| `C22_H15P` et sous-variables `STAT_GSEC*` | `double` | Structure socio-professionnelle hommes 15+ | Peu a ce stade |
| `C22_F15P` et sous-variables `STAT_GSEC*` | `double` | Structure socio-professionnelle femmes 15+ | Peu a ce stade |
| `P22_POP_FR` | `double` | Population francaise | Peut-etre |
| `P22_POP_ETR` | `double` | Population etrangere | Peut-etre |
| `P22_POP_IMM` | `double` | Population immigree | Peut-etre |
| `P22_PMEN` | `double` | Nombre moyen de personnes du menage | Oui - indicateur de structure |
| `P22_PHORMEN` | `double` | Population hors menages ordinaires | Peut-etre |

- **Entete exacte observee (76 colonnes)** :

```text
IRIS;COM;TYP_IRIS;LAB_IRIS;P22_POP;P22_POP0002;P22_POP0305;P22_POP0610;P22_POP1117;P22_POP1824;P22_POP2539;P22_POP4054;P22_POP5564;P22_POP6579;P22_POP80P;P22_POP0014;P22_POP1529;P22_POP3044;P22_POP4559;P22_POP6074;P22_POP75P;P22_POP0019;P22_POP2064;P22_POP65P;P22_POPH;P22_H0014;P22_H1529;P22_H3044;P22_H4559;P22_H6074;P22_H75P;P22_H0019;P22_H2064;P22_H65P;P22_POPF;P22_F0014;P22_F1529;P22_F3044;P22_F4559;P22_F6074;P22_F75P;P22_F0019;P22_F2064;P22_F65P;C22_POP15P;C22_POP15P_STAT_GSEC11_21;C22_POP15P_STAT_GSEC12_22;C22_POP15P_STAT_GSEC13_23;C22_POP15P_STAT_GSEC14_24;C22_POP15P_STAT_GSEC15_25;C22_POP15P_STAT_GSEC16_26;C22_POP15P_STAT_GSEC32;C22_POP15P_STAT_GSEC40;C22_H15P;C22_H15P_STAT_GSEC11_21;C22_H15P_STAT_GSEC12_22;C22_H15P_STAT_GSEC13_23;C22_H15P_STAT_GSEC14_24;C22_H15P_STAT_GSEC15_25;C22_H15P_STAT_GSEC16_26;C22_H15P_STAT_GSEC32;C22_H15P_STAT_GSEC40;C22_F15P;C22_F15P_STAT_GSEC11_21;C22_F15P_STAT_GSEC12_22;C22_F15P_STAT_GSEC13_23;C22_F15P_STAT_GSEC14_24;C22_F15P_STAT_GSEC15_25;C22_F15P_STAT_GSEC16_26;C22_F15P_STAT_GSEC32;C22_F15P_STAT_GSEC40;P22_POP_FR;P22_POP_ETR;P22_POP_IMM;P22_PMEN;P22_PHORMEN
```

- **Champ geographique** : aucun champ geometrique. La localisation se fait via la cle `IRIS` / `COM`.
- **Echantillon** :

| IRIS | COM | TYP_IRIS | LAB_IRIS | P22_POP | P22_POP0002 | P22_POP0305 | P22_POP0610 |
|---|---|---|---|---|---|---|---|
| `010010000` | `01001` | `Z` | `5` | `859` | `33` | `28` | `56` |
| `010020000` | `01002` | `Z` | `5` | `273` | `6` | `12` | `19` |
| `010040101` | `01004` | `H` | `1` | `2057.93753915075` | `98.5714870259099` | `56.9778679537102` | `139.534470146303` |
| `010040102` | `01004` | `H` | `1` | `3986.92009810392` | `147.358644172228` | `164.785678281558` | `239.997490548488` |
| `010040201` | `01004` | `H` | `1` | `4520.66663670346` | `194.195738943017` | `196.752408241776` | `281.247669410446` |

- **Observations** :
  - La source est un fichier statique, pas une API ; il n'y a donc pas de compteur de lignes expose.
  - L'entete a pu etre lue sans persister le dataset localement ; elle confirme `76` colonnes.
  - Les variables de population totale et par age sont directement exploitables pour le modele.
  - La cle attendue pour le join avec les contours est `IRIS` = `code_iris`.
  - Le filtre Paris devra se faire sur `COM like '75%'` et/ou `IRIS like '75%'`.
- **Filtre a appliquer** : conserver les lignes dont `COM` commence par `75`, puis joindre sur `IRIS`.

## Reponses critiques

1. **Le dataset "mobiliers urbains" contient-il uniquement des corbeilles ? Quel filtre appliquer ?**  
   Non. Le titre et la description indiquent un regroupement `Jardinieres + Bancs + Corbeilles de rue`. L'API inspectee ne fournit pas de filtre exploitable pour isoler les corbeilles : `lib_classe` est vide sur `273306/273306` lignes. L'investigation complementaire montre en plus que `num_pave` ne peut pas etre interprete de facon fiable comme type de mobilier. Il n'existe donc **aucun filtre robuste** a appliquer dans le schema public actuel.

2. **Les coordonnees sont-elles en WGS84 (EPSG:4326) ?**  
   Oui pour les sorties d'API inspectees : `geo_point_2d` est en `lat/lon`, les GeoJSON renvoient des coordonnees `lon,lat`, et la couche IRIS WFS peut etre demandee explicitement en `SRSNAME=EPSG:4326`. Il faudra toutefois fixer/verifier le CRS lors du chargement.

3. **Combien de corbeilles y a-t-il au total dans Paris ?**  
   Impossible a determiner de maniere fiable avec le dataset inspecte. `273306` correspond au total de primitives du jeu PVP exporte, pas au nombre de seules corbeilles. Les communications Ville accessibles publiquement parlent d'environ `30000` corbeilles, ce qui confirme l'incoherence du comptage brut du PVP.

4. **Les contours IRIS couvrent-ils bien les 20 arrondissements ?**  
   Oui. Le filtre `code_insee like '75%'` renvoie `992` IRIS et couvre les codes `75101` a `75120`, soit les 20 arrondissements parisiens.

5. **Y a-t-il des champs communs entre les datasets ou faut-il passer par la jointure spatiale ?**  
   Il y a une cle directe entre `Contours IRIS` et `Population INSEE` : `code_iris` <-> `IRIS`. Pour les jeux OpenData Paris (mobiliers, Trilib', espaces verts), il n'existe pas de code IRIS natif ; il faudra passer par jointure spatiale sur les polygones IRIS. Les champs d'arrondissement / code postal peuvent seulement servir de controle qualitatif.
