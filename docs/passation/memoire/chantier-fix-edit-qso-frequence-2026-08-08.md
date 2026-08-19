---
name: chantier-fix-edit-qso-frequence-2026-08-08
description: "Fix : champ FRÉQUENCE ajouté à la modale CORRIGER LE QSO (commit 82298ab, fusionné sur main) — demande F4GLD avec capture d'écran"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T19:09:12.390Z
---

Demande F4GLD en cours de session ("il faut que je puisse rentrer la
frequence!", avec capture d'écran de la modale CORRIGER LE QSO ne montrant
aucun champ fréquence). Livré et fusionné sur `main` (commit `9127c0c`,
merge de `fix/edit-qso-frequence`, commit de contenu `82298ab`).

## Contexte trouvé en explorant le code

`qso.freq` existait déjà comme propriété (renseignée à la saisie via
`#inputFreq` du formulaire principal, utilisée dans l'export ADIF et
affichée en sous-texte de la colonne BANDE du tableau du log) — mais
totalement absente de la modale d'édition (`#editOverlay`/`editQSO()`/
`saveEdit()`), donc invisible et non corrigible une fois le QSO enregistré.

## Ce qui a changé

Nouveau champ `#editFreq` (libellé "FRÉQUENCE (MHz)", placeholder
"144.300", même convention que `#inputFreq`) ajouté dans la case vide du
3e emplacement de la grille (ligne N° REÇU / MODE, grid 3 colonnes).
Peuplé dans `editQSO()` depuis `q.freq`, écrit dans `saveEdit()` dans
l'`Object.assign` envoyé au serveur via `/log/update`.

## Vérification

Testé avec un QSO synthétique (id négatif, jamais persisté côté serveur) :
champ peuplé correctement, éditable, `saveEdit.toString()` confirmé
référencer `editFreq` (vérification statique du branchement plutôt qu'un
vrai POST réseau, pour respecter la règle "jamais de vraie écriture
pendant la vérification"). Incident mineur pendant la vérification (QSO
factice resté visible dans le tableau réel) — voir
[[piege-push-qsolog-live-render-auto]], corrigé avant de continuer.

Suite ciblée (43 tests) + suite complète pytest : vertes. Pas de revue
adversariale Workflow (changement trop petit et localisé pour le justifier).
