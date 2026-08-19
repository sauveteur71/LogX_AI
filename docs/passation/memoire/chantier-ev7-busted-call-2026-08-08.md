---
name: chantier-ev7-busted-call-2026-08-08
description: "EV-7 13e incrément : filet anti-busted call extrait vers logx_busted_call.js (merge ce6846f) — 1er des 4 derniers incréments à nécessiter l'adaptation d'un test dédié (test_busted_call.py, 3 assertions), revue adversariale 0 constat"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T17:13:06.952Z
---

Chantier livré et fusionné sur `main` le 08/08/2026 (commit `ce6846f`, merge
de `feat/ev7-extract-busted-call`, commit de contenu `91edc4f`).

## Contexte

Après épuisement du top 3 initial ([[chantier-ev7-qso-map-2026-08-08]]),
F4GLD a demandé un 4e incrément ("go4"). Plutôt que de relancer un inventaire
Workflow complet, réutilisation directe de l'évaluation détaillée déjà
produite pour le "filet anti-busted call" lors de l'inventaire du 10e
incrément (candidat classé FAIBLE risque, déjà repéré comme propre au 9e
incrément mais laissé de côté à l'époque, cf.
[[chantier-ev7-outils-autonomes-2026-08-08]]).

## Ce qui a changé

`_bcPastille` (état) + `verifierIndicatifApres()`/`afficherPastilleBusted()`/
`fermerPastilleBusted()`/`vieillirPastilleBusted()`/`corrigerBusted()`
déplacés vers `logx_busted_call.js` (96 lignes). Un seul point d'entrée
externe : 2 lignes adjacentes dans `submitQSO()` (le cœur d'enregistrement
d'un QSO), inchangées par l'extraction. Aucun autre fichier n'appelle ces
fonctions (`logx_outils_autonomes.js` ne fait que CITER `corrigerBusted()`
en commentaire — décision assumée du 9e incrément de le laisser en place à
l'époque, pas un appel réel).

## Premier incrément de cette série à toucher un test dédié

Contrairement aux 10e/11e/12e incréments (zéro test référençant les
symboles extraits), `tests/test_busted_call.py` lit `logx_logbook.js`
directement dans CHAQUE fonction de test (pas de convention `_lire_tout()`
préexistante). 3 des 6 fonctions de test lisaient la DÉFINITION des
fonctions déplacées (pas seulement leur site d'appel) et cassaient sans
adaptation :
- `test_l_endpoint_call_near_a_ENFIN_un_appelant` (cherche `/call/near?call=`,
  présent dans le corps de `verifierIndicatifApres()`)
- `test_le_candidat_propose_suit_la_regle_a_deux_detentes` (extrait le corps
  de `verifierIndicatifApres()` par recherche de texte)
- `test_la_pastille_s_efface_toute_seule` (cherche `restant: 2`, dans le
  corps de `afficherPastilleBusted()`)

Corrigé en ajoutant une `_lire_tout()` locale à ce fichier de test (même
motif que `JS_EXTRAITS_EV7`/`_lire_tout()` dans
`test_logbook_menu_debut_fin.py`, mais scoped à ce seul fichier plutôt que
listant tous les modules EV-7 — n'a besoin que de concaténer
`logx_logbook.js` + `logx_busted_call.js`).

**Point de vigilance confirmé exact par la revue adversariale** : une 4e
fonction du même fichier (`test_la_verification_a_lieu_APRES_l_enregistrement_pas_pendant_la_frappe`,
qui compare la position de `qsoLog.push(qso)` et du SITE D'APPEL
`verifierIndicatifApres(qso)`) a été délibérément LAISSÉE INCHANGÉE : les
deux éléments comparés restent tous deux dans `logx_logbook.js`
(`qsoLog.push` dans `submitQSO()`, le site d'appel juste après) — seule la
DÉFINITION a bougé, pas cet appel. Vérifié avant de toucher le fichier
(raisonnement fait AVANT modification, pas découvert après coup par un
test rouge) : la substring `verifierIndicatifApres(qso)` n'existe plus
qu'à un seul endroit dans `logx_logbook.js` seul une fois l'extraction
faite (le site d'appel), donc `js.find(...)` continue de le trouver
correctement sans ambiguïté.

## Vérification navigateur : prudence sur les effets de bord réseau

`corrigerBusted()` appelle normalement `fetch('/log/update', ...)` — une
VRAIE écriture serveur. Vérifié en navigateur avec un `id` synthétique
(`'id-inexistant-jamais-dans-qsoLog'`) absent de `qsoLog` : la branche
`if(!q){ notify(...); return; }` s'arrête AVANT le fetch, permettant de
confirmer que la fonction entière ne plante pas et gère bien le cas
"introuvable" — SANS jamais exécuter le vrai `fetch('/log/update')` contre
le serveur de production. `afficherPastilleBusted()`/`vieillirPastilleBusted()`/
`fermerPastilleBusted()` testés avec des données 100% synthétiques
(aucune lecture/écriture réseau, juste manipulation DOM + variable d'état
locale).

## Suite

`logx_logbook.js` : 6600 → 6507 lignes après ce 13e incrément (6930 lignes
avant le 10e). Chantier repris ensuite pour un 14e incrément (relance d'un
inventaire Workflow complet, RTTY/SSTV et reliquat FAIBLE risque non
encore choisis) — voir mémoire suivante si produite dans la même session.
