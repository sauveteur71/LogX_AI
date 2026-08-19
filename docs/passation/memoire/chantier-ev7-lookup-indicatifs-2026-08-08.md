---
name: chantier-ev7-lookup-indicatifs-2026-08-08
description: "EV-7 17e incrément : résolution d'indicatif (HamQTH/cluster/calldb/autocomplete) extraite vers logx_lookup.js (commit 5a2f721, branche feat/ev7-extract-lookup-indicatifs) — 2 dépendances cachées trouvées et corrigées PROACTIVEMENT (avant tout échec CI), revue adversariale 1 constat mineur (drift pré-existant)"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T20:08:58.584Z
---

Chantier livré sur la branche `feat/ev7-extract-lookup-indicatifs` (commit
de contenu `5a2f721`), fusion sur `main` à confirmer une fois la CI verte.

## Contexte

F4GLD, après avoir validé Callbook (16e incrément), a dit
"lance la suite je te laisse travailler rendez vous dans 6h ne t'arrete
pas" — travail autonome enchaîné sur les candidats FAIBLE risque suivants
de [[inventaire-ev7-16e-candidat-2026-08-08]]. Ce 17e incrément est
l'alternative "gros volume" listée en 2e position (Lookup indicatifs,
323 lignes, même profil "0 test obligatoire" que Callbook selon
l'inventaire initial).

## Ce qui a changé

6 variables/constantes d'état (`clusterCache`, `clusterLastRefresh`,
`callLookupTimer`, `callDB`, `acResults`, `acSelected`) + 13 fonctions
(`remoteCallLookup`, `refreshCluster`, `loadCallDB`, `lookupCall`,
`lookupCluster`, `searchCalls`, `showAC`, `hideAC`, `highlightAC`,
`selectAC`, `onCallKeydown`, `applyCallData`, `updateCallDB`) déplacées
vers `logx_lookup.js` (323 lignes, extraites de `logx_logbook.js`
L4660-4982 — relocalisation confirmée exacte malgré 2 incréments
supplémentaires entre-temps).

## Deux dépendances cachées trouvées et corrigées AVANT tout échec CI

Contrairement au 16e incrément (bug découvert par la CI rouge), cette fois
les deux dépendances ont été identifiées en amont, en appliquant le
réflexe appris la veille — voir
[[piege-dependance-cachee-fichier-tiers-deja-extrait]] (écrit pendant CE
chantier, avant le commit) :

1. `submitQSO()` (reste dans `logx_logbook.js`) appelle `updateCallDB()`.
   `tests/test_macro_cw_serie_bande.py` exerce `submitQSO()` via son
   scénario `__qso()`/`__run()` sans jamais nommer `updateCallDB` dans son
   propre texte — trouvé en lisant le VRAI code de `submitQSO()` plutôt
   qu'en se fiant au grep initial (0 résultat dans `tests/`).
2. `showChecklist()` (dans `logx_verif_panel.js`, 4e incrément EV-7 déjà
   fusionné) lit `callDB` directement (`Object.keys(callDB).length`).
   `tests/test_peer_version_xss.py` charge et exécute
   `logx_verif_panel.js` sans jamais nommer `callDB` dans son propre
   texte — la dépendance vivait dans un TROISIÈME fichier, invisible à un
   grep sur le fichier de test lui-même. Trouvé en grepant les 19
   identifiants du bloc dans TOUS les `logx_*.js` déjà extraits (pas
   seulement `tests/`), qui a remonté `logx_verif_panel.js`.

Les deux tests chargent désormais `logx_lookup.js` (`LOOKUP_JS_PATH`, même
convention que `HARDWARE_JS_PATH`/`CALLBOOK_JS_PATH`). Commentaire d'en-tête
de `logx_verif_panel.js` mis à jour (callDB vient maintenant de
`logx_lookup.js`, pas `logx_logbook.js`).

## Vérification

Suite ciblée (112 tests, incluant les 2 fichiers corrigés) + suite
complète pytest : vertes (code de sortie réel vérifié explicitement, cf.
[[piege-echo-exit-masque-code-sortie-reel]]). Vérifié en navigateur : 13
fonctions globales, `showAC()`/`hideAC()` testées avec données
synthétiques (pure DOM). Aucune nouvelle erreur console (seuls les 2 bugs
préexistants déjà connus : `sbCountdown`, `adaptivePoll`).

## Revue adversariale

2 dimensions : 1 constat MINEUR confirmé (`custom_contests.json` modifié,
drift pré-existant sans rapport — exclu du commit, comme à chaque
incrément précédent). Aucun constat sur l'extraction elle-même.

## Suite

`logx_logbook.js` : 5966 → 5647 lignes après ce 17e incrément (6930 avant
le 10e, soit -1283 lignes sur 8 incréments consécutifs). Chantier repris
immédiatement sur le 18e incrément (Widget jour/nuit + champ locator, 94
lignes, 0 test attendu) sans interruption, conformément à l'instruction
"ne t'arrete pas" de F4GLD.
