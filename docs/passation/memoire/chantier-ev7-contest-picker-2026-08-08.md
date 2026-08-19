---
name: chantier-ev7-contest-picker-2026-08-08
description: "EV-7 10e incrément : sélecteur concours (modale de démarrage) extrait vers logx_contest_picker.js (merge 087ccee) — 1er incrément lancé après un inventaire Workflow complet du fichier plutôt qu'une recherche ad hoc de candidat"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T15:49:57.789Z
---

Chantier livré et fusionné sur `main` le 08/08/2026 (commit `087ccee`, merge
de `feat/ev7-extract-contest-picker`, commit de contenu `89cad14`).

## Origine : premier inventaire EV-7 exhaustif de la campagne

F4GLD a demandé "ou en est on exactement qui a t il a revoir pour finir le
grand chantier" (référence à EV-7, le refactor frontend en cours depuis
plusieurs jours). Contrairement aux 9 incréments précédents où le candidat
suivant était cherché par une investigation ciblée à chaque fois, celui-ci a
démarré par un Workflow de cartographie COMPLÈTE du fichier restant
(logx_logbook.js, 6930 lignes) : 1 agent de cartographie (64 blocs
identifiés) → agents d'évaluation en parallèle (autonomie/dépendances
croisées/risque) pour chaque bloc ≥80 lignes → synthèse d'un top 3.
F4GLD a choisi le candidat #1 ("go 1") : sélecteur concours UI (~90 lignes).

## Ce qui a changé

`csToggle`/`csFilter`/`csSelect`/`csSetValue`/`updateContestTiming` +
le listener `document.addEventListener('click', ...)` de fermeture au clic
extérieur (lignes ~6836-6925 de `logx_logbook.js`) déplacés tels quels vers
`logx_contest_picker.js` — extraction MÉCANIQUE (motif des incréments 1-9 et
RADIO CAT/AMPLI/ROTOR/WSJT-X, pas le bus d'événements du pilote SCAN QSL
PAPIER). `<script src="logx_contest_picker.js">` ajouté dans
`logx_logbook.html` juste avant `<script src="logx_logbook.js">`.
`JS_EXTRAITS_EV7` (tests/test_logbook_menu_debut_fin.py) mis à jour.

`CS_DATA` et `CONTEST_SCHEDULE` (données lues par le bloc) restent
VOLONTAIREMENT dans `logx_logbook.js` : `CONTEST_SCHEDULE` est partagée avec
d'autres parties du fichier (dates par défaut au chargement, nom du concours
affiché en score) — la déplacer aurait cassé ces autres usages. Seul un
appelant externe réel : `csSetValue()` depuis `prefillSetupFromConfig()`,
comme prédit par l'évaluation préalable.

## Revue adversariale : extraction propre, 0 constat structurel

3 dimensions (fidélité de l'extraction, intégrité des dépendances,
couverture de test) + vérification indépendante. **0 constat** sur les 2
premières dimensions (git diff confirmé octet-pour-octet identique, ordre
de script correct, aucun appelant manqué). 2 constats mineurs sur la
couverture de test, tous deux CONFIRMÉS mais non bloquants :

1. **Aucun test dédié** — cohérent avec la politique de fait du projet :
   sur les 13 modules déjà extraits par EV-7, seuls 3 ont un test dédié
   (`logx_awards.js`, `logx_qtc.js`, `logx_import_adif.js`), et uniquement
   parce qu'ils contiennent de la LOGIQUE MÉTIER testable (calcul de score,
   backfill d'ID, règles de fusion) — pas de la plomberie DOM
   (getElementById/classList/innerHTML). `logx_contest_picker.js` (5
   fonctions, ~90% plomberie DOM) est dans la même catégorie que les 10
   autres modules sans test dédié, dont certains bien plus complexes (ex.
   `logx_hardware_cat.js`, 19 fonctions, vraie logique CAT/ampli/rotor).
   Conclusion utile pour la suite : ne plus rouvrir cette question à chaque
   futur incrément EV-7 mécanique tant que le fichier reste de la plomberie
   DOM pure — c'est un choix de politique assumé, pas un oubli à corriger.
2. Voir [[piege-intl-absent-py-mini-racer]] — piège d'infrastructure de
   test découvert en PROTOTYPANT un test qui n'a finalement pas été ajouté.

## Vérification navigateur

Serveur de production (port 8080, jamais redémarré) : `csToggle`/
`csFilter`/`csSelect`/`csSetValue`/`updateContestTiming` toutes définies
depuis le nouveau fichier (`typeof === 'function'` + vérif network
`logx_contest_picker.js` chargé avant `logx_logbook.js`). Interactions
réelles testées via simulation DOM (ouverture panneau, filtre, clic sur une
option → `#setupContest.value` mis à jour + panneau fermé + libellé
affiché, fermeture au clic extérieur, `updateContestTiming` avec un
concours réel → horaires UTC/local + durée correctement rendus).

**Piège de vérification évité** : des erreurs console pré-existantes
(`<rect> attribute width: A negative value is not valid`, `adaptivePoll is
not defined`) sont apparues au chargement — pas de panique immédiate,
vérifié en STASHANT mes changements (`git stash push -u`) et en rechargeant
: les MÊMES erreurs apparaissent sur `main` sans mon changement → confirmé
pré-existant, pas une régression de cette extraction. `adaptivePoll is not
defined` flaggé en tâche séparée (`task_787432f5`) plutôt que traité ici,
pour ne pas mélanger deux sujets sans rapport sur cette branche. Réflexe à
retenir : avant de conclure qu'une erreur console est une régression
introduite par SON propre changement, la reproduire (ou pas) sur l'état
`main` via `git stash` — plus fiable que de deviner à la lecture du message
d'erreur.

## Suite

`docs/LogX_AI_PRD.md` section 7 (EV-7) reste au niveau principe — aucun
document ne liste les prochaines cibles. Le top 2/3 non retenus par F4GLD
restent disponibles pour un futur 11e incrément : table préfixes DXCC +
lookup (`CTY_PREFIX`, `lookupDXCC`, ~134 lignes, autonomie totale) et carte
QSO Leaflet (`initMap`/`refreshMapLayers`/`toggleMapView`, ~115 lignes).
RTTY, SSTV et le filet anti-busted call classés FAIBLE risque en réserve.
À ÉVITER sans raison nouvelle : tout ce qui touche le chemin critique
(`submitQSO`, `renderLog`, `setupDone`), et les "faux candidats" repérés qui
semblent autonomes mais mélangent plusieurs sujets (sélecteur concours
DONNÉES — différent de ce chantier qui n'a pris que les FONCTIONS —, macros
CW+i18n, décodeur CW+RTTY+SSTV, broadcast channel, horloge).
