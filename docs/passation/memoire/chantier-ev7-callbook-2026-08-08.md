---
name: chantier-ev7-callbook-2026-08-08
description: "EV-7 16e incrément : fiche CALLBOOK (QRZ/HamQTH/HamDB) extraite vers logx_callbook.js (commit c41f229, branche feat/ev7-extract-callbook) — recommandation n°1 de l'inventaire Workflow, zéro test à adapter, revue adversariale 0 constat"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T19:41:24.428Z
---

Chantier livré sur la branche `feat/ev7-extract-callbook` (commit de
contenu `c41f229`), fusion sur `main` à confirmer une fois la CI verte.

## Contexte

F4GLD, de retour après plusieurs heures d'absence, a validé directement la
recommandation n°1 de [[inventaire-ev7-16e-candidat-2026-08-08]] ("lance
l'extraction du Callbook") — pas d'inventaire relancé, candidat déjà
entièrement caractérisé.

## Ce qui a changé

8 variables/constantes d'état (`_checkTimer`/`_checkSeq`, `_qrzTimer`/
`_qrzSeq`, `_stateAnnuaire`, `CALLBOOK_SOURCE_LABEL`, `_prevTimer`/
`_prevSeq`) + 4 fonctions (`lookupQRZ`, `checkCallStatus`, `fmtDate`,
`checkPrevQsos`) déplacées vers `logx_callbook.js` (175 lignes, extraites
de `logx_logbook.js` L954-1128 — relocalisation exacte confirmée avant
extraction, coïncidait avec l'estimation de l'inventaire malgré 2 incréments
supplémentaires entre-temps, car les extractions 15/fix-fréquence avaient
toutes lieu APRÈS ce bloc dans le fichier).

Seul point de dépendance croisée avec un fichier EV-7 déjà extrait :
`fmtDate()` consommée par `logx_awards.js` (4e incrément) — commentaire
d'en-tête de ce dernier mis à jour pour refléter la nouvelle provenance
(motif déjà appliqué une fois pour `callDB`/`logx_verif_panel.js`, prévu
par l'inventaire comme "point à documenter, pas à corriger").

## Confirmation du "zéro test" annoncé par l'inventaire

Grep exhaustif avant extraction : aucune des 8 variables ni des 4 fonctions
n'apparaît dans `tests/`. Seule adaptation faite par convention établie :
ajout de `'logx_callbook.js'` à `JS_EXTRAITS_EV7` dans
`tests/test_logbook_menu_debut_fin.py` — précaution de cohérence, pas un
correctif requis. Suite ciblée : 92 tests passés. Suite complète : verte.

## Vérification navigateur

Les 4 fonctions confirmées globales et positionnées après `logx_rtty_panel.js`
dans `document.scripts`. `fmtDate('20260808')` → `'08/08/2026'` (pure,
sûre). `checkCallStatus`/`lookupQRZ`/`checkPrevQsos` testées avec des
indicatifs < 3 caractères (garde de court-circuit, aucune requête réseau
déclenchée) — évite tout appel réseau réel pendant la vérification, même
vers les propres endpoints locaux de l'app. `_stateAnnuaire`/
`CALLBOOK_SOURCE_LABEL` confirmés présents.

Un bug préexistant sans rapport (`sbCountdown` null dans
`updateClockAndCountdown()`) reste visible en console — déjà signalé
séparément le même jour (`task_63cef982`, démarrée par F4GLD dans une
session locale distincte), pas retouché ici.

## Revue adversariale

2 dimensions (extraction-fidelity, dependency-integrity) : **0 constat**.

## Suite

`logx_logbook.js` : 6137 → 5966 lignes après ce 16e incrément (6930 avant
le 10e, soit -964 lignes sur 7 incréments consécutifs). Candidats FAIBLE
risque restants de l'inventaire du même jour (non extraits) : Lookup
indicatifs (L4831-5153, 323 lignes, alternative "gros volume"), Widget
jour/nuit + locator, Callbot vocal + ESM, Keyer vocal DVK, Reverse lookup
locator, Thème jour/nuit + raccourcis — détail complet dans
[[inventaire-ev7-16e-candidat-2026-08-08]].

## Incident post-merge : CI rouge, "0 test à adapter" incomplet

Le premier commit (`c41f229`) a fait échouer la CI : `test_macro_cw_serie_bande.py`
(3 tests) construit un contexte V8 en concaténant `HARDWARE_JS_PATH`
(`logx_hardware_cat.js`) + `logx_logbook.js`, puis simule la FRAPPE d'un
indicatif via `__qso()` — ce qui déclenche le vrai gestionnaire d'événement
de `logx_logbook.js`, lequel appelle `checkCallStatus()`/`lookupQRZ()`/
`checkPrevQsos()` (déplacées par ce chantier). Ce fichier de test ne
MENTIONNE JAMAIS ces 3 noms de fonction — la dépendance est indirecte
(frappe simulée → `oninput` réel → ces fonctions), donc invisible à un grep
exhaustif classique. `__done` restait `false` sans qu'aucune exception ne
remonte à pytest (promesse rejetée jamais awaitée côté test).

**Erreur de méthode supplémentaire commise en parallèle** : le premier
lancement de la suite complète en fond utilisait
`pytest ... ; echo DONE_$?` — le "exit code 0" rapporté par la notification
de tâche en fond reflétait `echo` (toujours 0), PAS le vrai code de sortie
de pytest (qui était 1, 3 échecs). Suite verte annoncée à tort avant la
CI. Corrigé pour la suite : écrire le code de sortie réel dans le FICHIER
de sortie lui-même (`echo "EXIT_REEL=$?" >> fichier.txt` après la commande,
sans `;` qui masque le code), et le lire explicitement plutôt que de se
fier au statut de la notification de tâche en fond.

**Réflexe pour tout futur incrément EV-7** : avant de conclure "0 test à
adapter" sur la seule base d'un grep par nom de fonction/variable, chercher
aussi les fichiers de test qui simulent une interaction utilisateur
complète (recherche `HARDWARE_JS_PATH`/`_lire_tout`/motif `__qso`/`__run` —
signe qu'un fichier concatène déjà un autre extrait EV-7 pour une raison
similaire, donc probablement concerné aussi). `HARDWARE_JS_PATH` était déjà
présent dans ce même fichier pour `rigState` (RADIO CAT) — un signal qui
aurait dû alerter avant l'extraction, pas après l'échec CI.

Corrigé par commit `b138b35` sur la même branche (`CALLBOOK_JS_PATH`, même
motif que `HARDWARE_JS_PATH`) — 10/10 passés localement, suite complète
verte confirmée via lecture explicite du code de sortie réel.
