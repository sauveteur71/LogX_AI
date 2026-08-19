---
name: chantier-ev7-filtre-spots-2026-08-09
description: "EV-7 33e incrément — extraction FILTRE SPOTS + refreshBandMap() vers logx_filtre_spots.js (09/08, merge bb195b3)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T08:33:52.898Z
---

33e incrément de la campagne EV-7 (LogX AI) : extraction contiguë de 208
lignes (_SF_CONTINENTS, _spotFiltre/-EnVol/-Ouvert, toggleSpotFiltre(),
dessinerChipsFiltre(), basculerContinent(), majSpotFiltre(),
appliquerRetourFiltre(), **refreshBandMap()**) depuis `logx_logbook.js` vers
`concours/logx_filtre_spots.js`. Dernier candidat MOYEN du 3e inventaire
(voir [[inventaire-ev7-3e-2026-08-09]]). Fusionné sur main : commit
bb195b3 (merge), b835df5 (contenu).

**Why:** refreshBandMap() était le point de conversion unique kHz→MHz des
spots (voir tests/test_freq_unite_spots.py) — un bloc autonome mais avec un
appel top-level non gardé (`setInterval(refreshBandMap,15000)`) dans le
coeur, donc à charger AVANT logx_logbook.js comme tous les fichiers EV-7.

**Piège local-constant, 4e occurrence confirmée** : `test_freq_unite_spots.py
::test_band_map_convertit_a_l_entree` cherchait littéralement `const
clusterMhz`/`const clusterCles`/`_bmSpots = spots` dans
`_lire('logx_logbook.js')` — ces noms sont des variables LOCALES au corps de
refreshBandMap(), invisibles à un grep du nom de la fonction elle-même. Ce
test avait été vérifié et écarté comme faux positif au 31e incrément (quand
refreshBandMap() n'était pas encore la cible), mais jamais re-vérifié quand
elle EST devenue la cible au 33e — **la clairance d'un faux positif est
scopée à la cible d'extraction du moment, pas permanente : à re-vérifier à
chaque fois que la cible réelle change entre incréments.** Corrigé en
repointant uniquement cette fonction de test vers
`_lire('logx_filtre_spots.js')`.

**Revue adversariale (Workflow, 2 dimensions)** : 3 constats mineurs
confirmés, tous des dérives documentaires dans des commentaires d'en-tête
(`logx_bandscope_waterfall.js` disait encore refreshBandMap() « coeur » ;
`logx_filtre_spots.js` disait « seulement » un site d'appel de
bandmapClick() alors qu'il y en a 3 : logx_filtre_spots.js lui-même,
logx_bandscope_waterfall.js (2e onclick généré par drawBandscope()), et
logx_bandmap_sp.js (appel direct depuis bandmapSaut(), pas via onclick)).
Aucun bug fonctionnel — corrigés dans le même commit.

**15 fichiers de test « hôte entier »** mis à jour avec une constante
FILTRE_SPOTS_JS_PATH insérée avant le chargement de logx_logbook.js.

Vérification fonctionnelle navigateur réelle (serveur prod port 8080, jamais
redémarré) : refreshBandMap() appelée contre les vraies données live (résolue
sans erreur), basculerContinent('spotter_continents','EU') exercée en
aller-retour (ajout puis retrait, état cohérent), dessinerChipsFiltre()/
toggleSpotFiltre()/majSpotFiltre()/appliquerRetourFiltre() toutes appelées
sans exception, panneau remis à l'état fermé après coup.

**How to apply:** avant toute extraction future touchant une fonction déjà
« blanchie » par un incrément précédent (même partiellement, même en tant que
simple appelant non-extrait), re-passer le grep des 4 classes de pièges —
ne jamais se fier à une clairance antérieure dont la cible d'extraction a
changé. Voir [[piege-appel-top-level-casse-tests-hote-entier]] pour la classe
générale, ce chantier documente spécifiquement la sous-classe « constante
locale au corps de la fonction cible ».
