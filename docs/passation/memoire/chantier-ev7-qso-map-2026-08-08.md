---
name: chantier-ev7-qso-map-2026-08-08
description: "EV-7 12e incrément : carte QSO Leaflet extraite vers logx_qso_map.js (merge 76797f7) — dernier des 3 candidats identifiés par l'inventaire Workflow ; revue adversariale 0 constat, série de 3 extractions consécutives (10e/11e/12e) sans aucun bug trouvé"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T16:45:05.545Z
---

Chantier livré et fusionné sur `main` le 08/08/2026 (commit `76797f7`, merge
de `feat/ev7-extract-qso-map`, commit de contenu `9c9e5a6`).

## Contexte

Candidat #3, dernier du top 3 identifié par l'inventaire Workflow initial
(voir [[chantier-ev7-contest-picker-2026-08-08]]). F4GLD a enchaîné les 3
candidats l'un après l'autre ("go 1", "go 2", "go 3") sans repasser par une
nouvelle investigation — l'inventaire initial avait suffisamment bien
qualifié les 3 candidats pour ne nécessiter aucune re-vérification
approfondie entre chaque, seulement la vérification standard (lecture du
bloc réel + grep des appelants + tests) avant chaque extraction.

## Ce qui a changé

`qsoMap`/`homeMarker`/`mapLayers`/`BAND_COLORS`/`initMap()`/
`refreshMapLayers()`/`toggleMapView()` (logx_logbook.js lignes 6558-6672,
115 lignes) déplacés vers `logx_qso_map.js`. Bloc confirmé net et complet :
état interne jamais lu ailleurs, un seul point d'entrée HTML
(`onclick="toggleMapView()"`, inchangé par l'extraction) et un seul appel
interne (`refreshMapLayers()` depuis le rendu de la liste des QSO, dans le
corps d'une fonction, jamais au chargement du script).

**Piège de faux positif écarté à la vérification** : `logx_carte.html` (une
page SANS RAPPORT, la carte de propagation/DX) a SA PROPRE fonction
`initMap()` totalement indépendante — un grep naïf sur `initMap` remonte ce
homonyme. Vérifié explicitement que les deux fonctions vivent dans des
pages HTML différentes (portées de script distinctes, jamais chargées
ensemble) avant de conclure à l'absence de conflit réel.

Dépend de la bibliothèque Leaflet globale (`L`, CDN chargé dans le `<head>`
de `logx_logbook.html`, ligne 16-17, bien avant tous les `<script>` locaux)
et de `locLL`/`escHtml`/`BAND_LABELS`/`qsoLog`/`myLocator`/`myCall` (définis
plus haut dans `logx_logbook.js`, lus uniquement à l'intérieur du corps des
fonctions).

Extraction via le même script Python que le 11e incrément (fiabilité pour
le contenu emoji des popups Leaflet : 📍🗺️📋⚠️📡📏🏆). Vérifié en navigateur :
`toggleMapView()` ouvre la carte, `qsoMap` s'initialise (objet Leaflet réel
créé), `mapLayers` se peuple (12276 entrées marqueurs+polylignes pour
l'historique complet du log), le bouton bascule bien vers "📋 TABLEAU",
puis referme proprement. Revue adversariale : **0 constat**.

## Bilan de la série de 3 extractions (10e, 11e, 12e incréments)

Les 3 candidats du top 3 initial sont maintenant tous extraits, chacun avec
0 constat en revue adversariale — une série inhabituellement propre pour
cette campagne EV-7 (comparer aux incréments précédents, qui trouvaient
quasi systématiquement 1 à plusieurs bugs réels avant fusion). Explication
probable : l'investissement initial dans l'inventaire Workflow complet (64
blocs cartographiés + évaluation systématique d'autonomie/risque avant de
choisir) a payé — les 3 candidats retenus avaient déjà été sélectionnés
précisément parce qu'ils étaient les PLUS autonomes du fichier, contrairement
aux incréments précédents où le candidat suivant était souvent découvert
au fil d'investigations plus courtes et ciblées.

`logx_logbook.js` : 6930 lignes (avant le 10e incrément) → 6584 lignes
(après le 12e). ~346 lignes extraites sur ces 3 incréments.

## Suite

Aucun candidat FAIBLE risque restant du top 3/liste de réserve initiale
n'a été traité (RTTY, SSTV, filet anti-busted call — restaient en réserve
sans avoir été formellement choisis). Prochain incrément EV-7 : soit
reprendre un de ces 3, soit relancer un inventaire Workflow pour retrouver
d'autres candidats propres (le fichier contient encore ~85% de son volume
d'origine en dette technique). Décision à prendre avec F4GLD avant de
relancer, comme pour l'inventaire initial.
