---
name: chantier-ev7-shortcut-offer-2026-08-09
description: "EV-7 34e incrément — extraction RACCOURCI BUREAU vers logx_shortcut_offer.js (09/08, merge e4b8573)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T09:42:42.606Z
---

34e incrément de la campagne EV-7 (LogX AI) : extraction contiguë de 41
lignes (checkShortcutOffer(), hideShortcutOffer(), createDesktopShortcut(),
dismissShortcutOffer()) depuis `logx_logbook.js` vers
`concours/logx_shortcut_offer.js`. Premier candidat FAIBLE du 4e inventaire
(voir [[inventaire-ev7-4e-2026-08-09]] si écrit, sinon rapport du Workflow
`ev7-4e-inventaire`). Fusionné sur main : commit e4b8573 (merge), ecb476b
(contenu).

**Why:** bandeau d'offre de création de raccourci bureau au premier
lancement de l'exécutable figé — fonctionnalité isolée, seul appelant
`init()` lui-même déclenché uniquement via
`window.addEventListener('DOMContentLoaded', ...)`.

**Nouveau : le plus « sûr » de toute la campagne à ce jour — 0 fichier de
test hôte-entier à mettre à jour.** Contrairement à presque tous les
incréments précédents (qui nécessitaient d'ajouter une constante
`*_JS_PATH` dans 5 à 15 fichiers de test « hôte entier » à cause d'un appel
top-level non gardé type `setInterval(fn,...)`), ce bloc n'a AUCUN appel
top-level : son seul point d'entrée (`init()`) n'est invoqué qu'après
`DOMContentLoaded`, qui est un no-op stub dans le DOM minimal simulé des
tests py_mini_racer (`window.addEventListener = function(){};`). Confirmé
par grep exhaustif (aucune des 4 fonctions n'était référencée nulle part
dans `concours/tests/` avant l'extraction) et par la revue adversariale, qui
a explicitement vérifié cette affirmation en lisant 2-3 fichiers de test
représentatifs.

**How to apply:** avant de supposer qu'un candidat nécessite une mise à
jour des tests hôte-entier (motif systématique depuis le 30e incrément),
vérifier D'ABORD si son seul chemin d'entrée passe par un événement
`DOMContentLoaded`/équivalent stubé dans le DOM de test — si oui, le
candidat est structurellement plus sûr qu'il n'y paraît et le motif
"ajouter *_JS_PATH partout" est superflu. Voir aussi
[[piege-appel-top-level-casse-tests-hote-entier]] pour le cas inverse (celui
qui NÉCESSITE la mise à jour).

Revue adversariale (Workflow, 2 dimensions) : 0 constat confirmé (1 brut
soumis, réfuté). Suite pytest 100% verte du premier coup (aucun fichier de
test modifié à part JS_EXTRAITS_EV7). Vérification navigateur réelle :
`checkShortcutOffer()` exercée contre le vrai serveur (lecture seule),
`hideShortcutOffer()` exercée (pure UI). `createDesktopShortcut()` et
`dismissShortcutOffer()` volontairement NON exercées en conditions réelles
(effets de bord définitifs : création d'un vrai raccourci Windows, pose
d'un marqueur serveur irréversible) — seul leur `typeof` vérifié.
