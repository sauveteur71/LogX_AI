---
name: chantier-ev7-daynight-locator-2026-08-08
description: "EV-7 18e incrément : widget jour/nuit + champ locator extraits vers logx_daynight.js (commit 0152192, branche feat/ev7-extract-daynight-locator) — candidat n°3 inventaire, 0 dépendance cachée trouvée (leçons 16e/17e appliquées en amont), revue adversariale 0 constat"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T20:27:48.770Z
---

Chantier livré sur `feat/ev7-extract-daynight-locator` (commit `0152192`),
fusion sur `main` à confirmer une fois la CI verte.

## Contexte

Suite du travail autonome demandé par F4GLD ("lance la suite... ne
t'arrete pas"), 3e candidat de [[inventaire-ev7-16e-candidat-2026-08-08]]
après Callbook (16e) et Lookup indicatifs (17e).

## Ce qui a changé

`_todTimer`/`_todSeq` + `refreshTimeOfDay(dxLocator)`/`onLocatorInput()`
déplacées vers `logx_daynight.js` (94 lignes, extraites de
`logx_logbook.js` L2834-2927 — relocalisation exacte malgré 3 incréments
supplémentaires depuis la cartographie initiale). Chaîne fonctionnelle
cohérente : saisie locator → validation → distance/cap/points → widget
jour/nuit → autocomplete.

## Zéro dépendance cachée cette fois — méthode appliquée en amont

Contrairement aux 16e/17e incréments (bugs trouvés soit par CI rouge soit
in extremis), cette fois la méthode de
[[piege-dependance-cachee-fichier-tiers-deja-extrait]] a été appliquée
AVANT extraction sans rien trouver à corriger : grep des 4 identifiants
dans TOUS les `logx_*.js` déjà extraits (trouvé : `logx_callbook.js`
`lookupQRZ()` et `logx_lookup.js` `applyCallData()` appellent
`onLocatorInput()`, tous deux en corps de fonction) + grep dans `tests/`
(0 résultat) + vérification que `test_macro_cw_serie_bande.py` ne simule
QUE `document.getElementById('inputLocator').value = ...` sans dispatcher
d'événement `input` ni appeler `applyCallData()`/`lookupQRZ()` réellement
— donc aucune adaptation de test nécessaire.

## Vérification

Suite ciblée (112 tests) + suite complète pytest : vertes. Navigateur :
`onLocatorInput('jn18ab')` → majuscule automatique, classe `ok`,
`📏 353 km 🧭 337° NNO → 🏆 353 pts` — aucun appel réseau autre que
GET `/data/timeofday` (informatif). Aucune nouvelle erreur console.

## Revue adversariale

2 dimensions : 0 constat.

## Suite

`logx_logbook.js` : 5647 → 5557 lignes après ce 18e incrément (6930 avant
le 10e, soit -1373 lignes sur 9 incréments consécutifs). Chantier repris
sur le 19e incrément (Callbot vocal + ESM, ~114 lignes, 1 test attendu).
