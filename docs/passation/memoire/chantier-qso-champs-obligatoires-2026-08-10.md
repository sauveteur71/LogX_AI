---
name: chantier-qso-champs-obligatoires-2026-08-10
description: "Champs obligatoires de la saisie QSO — indicatif+fréquence bloquants, locator bloquant selon le barème du concours (contestRequiresLocator), auto-proposition du locator déjà existante"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-10T05:56:29.393Z
---

Demande F4GLD du 10/08/2026 (en pleine vérification du chantier 2, message
interrompant le tour en cours — traité à la suite) : « les points obligatoire
de la saisie qso sont l'indicatif et la frequence [...] la bande doit etre
deduite de facon automatique, regarde sil est possible de recupérer de facon
automatique le locator et le proposer automatiquement. pour certain concours
seul la bande peux suffire, et parfois le locator peux etre obligatoire [...]
variable selon le concours. » PR #10 (branche feat/qso-champs-obligatoires),
`concours/logx_logbook.js` uniquement.

**Investigation AVANT d'écrire du code — 2 des 3 demandes étaient déjà
faites** (piège à répétition dans ce projet : ne jamais supposer qu'une
fonctionnalité manque sans grep d'abord) :
- Bande auto-déduite de la fréquence : déjà câblé de longue date
  (`onFreqInput()` → `bandFromFreq()`, restreint aux bandes actives via
  `_currentVisibleBands`). Rien à faire.
- Proposition auto du locator par indicatif : déjà câblé de longue date
  (`onCallInput()` → `lookupCall()`/`lookupCluster()`/`applyCallData()`,
  repli distant HamQTH via `remoteCallLookup()` avec debounce 600 ms — ne
  jamais écraser une valeur déjà saisie sauf source cluster temps réel).
  Rien à faire non plus, y compris en logbook simple (aucun garde
  `usageMode==='simple'` sur ce chemin).

**Le vrai gap** : `submitQSO()` ne bloquait que sur l'indicatif manquant ;
la fréquence était postée vide en silence, et le locator n'était jamais
qu'un avertissement (0 pt), même pour les concours où son absence rend le
QSO structurellement nul.

**Implémenté** :
1. `if(!freq){ notify(...); return; }` juste après le check indicatif,
   universel (pas de branche simple/contest — cohérent avec l'indicatif,
   déjà universel).
2. `contestRequiresLocator()` : dérivé du barème serveur déjà présent
   (`contestScoringDefs[currentContest].type`/`.bricks`, le même objet que
   lit déjà `calcPoints()`/`evalPointsFromDef()`) — teste si une des règles
   `points` du barème vaut `'per_km'` (couvre les 3 types connus
   `km`/`km_x_locators`/`km_x_large_locator_squares` ET tout barème
   custom/IA généré avec la même brique, sans liste d'identifiants de
   concours écrite à la main — piège déjà documenté
   [[piege-liste-identifiants-ecrite-a-la-main]]). Utilisé dans
   `submitQSO()` : locator vide + `contestRequiresLocator()` vrai → bloque
   (message dédié) ; sinon comportement inchangé (avertissement, 0 pt).
   Le check est imbriqué dans `if(!expeditionMode)`, donc jamais déclenché
   quand le champ est masqué (mode expédition).

**Piège de test rencontré (2 fois, corrigés avant de committer)** :
harnais JS (py_mini_racer) copié de `test_macro_cw_serie_bande.py`, deux
omissions distinctes :
1. `_DOM_PREAMBLE` copié à la main sans la ligne `function fetch(){...}`
   → `ReferenceError: fetch is not defined` au PARSE de `logx_logbook.js`
   (appel top-level `initShareLink();` qui appelle `fetch()` immédiatement,
   ligne ~2686 — piège de la classe
   [[piege-appel-top-level-casse-tests-hote-entier]], mais ici c'est une
   VARIABLE globale manquante avant le parse, pas un fichier JS entier).
2. En définissant explicitement `contestScoringDefs[id] = {type:...}` pour
   tester `contestRequiresLocator()`/`calcPoints()`, `evalPointsFromDef()`
   appelle `_brickCtx()` → `lookupDXCC()` (fichier `logx_dxcc_lookup.js`,
   PAS chargé par `test_macro_cw_serie_bande.py` car ce test-là ne peuple
   jamais `contestScoringDefs`, donc ne descend jamais dans cette branche).
   Diagnostiqué en ajoutant un `.catch()` explicite sur la Promise de
   `submitQSO()` plutôt qu'en devinant — `console.warn` stubbé en no-op
   avale silencieusement les erreurs async, `__logged.length===0` seul ne
   dit pas POURQUOI le POST n'a jamais eu lieu.

**Git — faux départ corrigé** : le nouveau travail a été fait par erreur
directement sur la branche `fix/chantier2-bandeaux-non-bloquants` alors que
sa PR #9 était déjà créée/mergée entre-temps — voir
[[piege-continuer-nouveau-chantier-sur-branche-pr-deja-creee]].

13 tests py_mini_racer (`test_qso_champs_obligatoires.py`), suite complète
verte, vérification navigateur réelle des 3 comportements (blocage
fréquence, bande sur frappe réelle via `onFreqInput()`, blocage/déblocage
locator selon barème injecté en direct dans la page).
