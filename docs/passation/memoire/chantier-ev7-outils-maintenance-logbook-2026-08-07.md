---
name: chantier-ev7-outils-maintenance-logbook-2026-08-07
description: "2e incrément EV-7 livré — 4 outils de maintenance LOGBOOK (filtre avancé, dédup, re-résolution, net control) extraits ; dépendance à l'envers trouvée et corrigée en revue adversariale"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T18:53:50.557Z
---

Chantier livré et fusionné sur `main` le 07/08/2026 (commit `dbee36d`, merge
de `feat/ev7-refactor-outils-maintenance-logbook`, commit de contenu `4ed6a7f`).

## Contexte

Suite directe de "[[chantier-ev7-pilote-cwpanel-2026-08-07]]" — F4GLD a dit
« continu » après le pilote CwPanel. Contrairement au pilote (élimination
d'une duplication radio1/2 via une classe), ce 2e incrément est un simple
DÉPLACEMENT : 4 fonctionnalités auto-contenues (~635 lignes) déjà repérées
dans l'audit UX du 07/08 (`chantier-ux-mode-debutant-partout`) — constructeur
de filtre avancé, recherche de doublons dédiée, re-résolution en masse,
contrôle de net — extraites telles quelles de `logx_logbook.js` vers 4
nouveaux fichiers (`logx_filter_builder.js`, `logx_dup_finder.js`,
`logx_bulk_resolve.js`, `logx_net_control.js`).

## Deux vrais problèmes trouvés et corrigés (aucun via l'audit final — l'un pendant l'écriture, l'autre via la revue adversariale)

1. **`test_logbook_menu_debut_fin.py::test_chaque_entree_du_menu_pointe_sur_une_fonction_REELLE`**
   — assertion purement TEXTUELLE (`'function %s(' % fn in src`, `src` =
   contenu de `logx_logbook.js` seul) : cassait dès que les 4 fonctions
   ouvrant les popups (`openFilterBuilder` etc.) ont quitté ce fichier.
   Corrigé en élargissant la recherche aux 4 nouveaux fichiers — même
   principe que le correctif de `test_cw_panel_consolidation.py` au chantier
   précédent, mais cette fois une simple lecture de source, pas un
   chargement `py_mini_racer`.
2. **Dépendance à l'envers** trouvée par la revue adversariale (workflow) :
   `matchesAdvancedFilter()`/`FILTER_FIELDS`/`FILTER_OPS` avaient été
   déplacées dans `logx_filter_builder.js`, mais `renderLog()` (chemin
   critique, resté dans `logx_logbook.js`) en dépend directement pour
   appliquer le filtre au tableau. Résultat : le CŒUR du logiciel aurait
   dépendu d'un fichier « fonctionnalité optionnelle ». Aucun test actuel ne
   cassait (`advancedFilter` vaut `null` par défaut, `&&` court-circuite),
   mais c'était un piège latent pour tout futur test positionnant
   `advancedFilter` avant d'appeler `renderLog()` en isolation. Corrigé en
   laissant le MOTEUR de correspondance dans `logx_logbook.js` (à côté de la
   déclaration de `advancedFilter`) et en ne déplaçant que l'UI du popup
   (rendu des groupes/conditions, préréglages) vers `logx_filter_builder.js`.

## Principe retenu pour la suite du refactor EV-7

Quand une fonctionnalité "optionnelle" à extraire partage un bout de logique
avec le CHEMIN CRITIQUE (ex. un moteur de filtrage utilisé par le rendu du
tableau), ce bout partagé doit rester du CÔTÉ du chemin critique, pas suivre
la fonctionnalité optionnelle — la dépendance doit toujours pointer de
l'optionnel vers le cœur, jamais l'inverse. Vérifier ce sens de dépendance
AVANT de committer un futur incrément, pas seulement après coup en revue.

## Vérification (même patron que le pilote)

Suite pytest complète (3 passes — 1re avec le bug du test menu → 1 échec,
2e après correctif → verte, 3e après le déplacement du moteur de filtre →
verte), navigateur réel sur les vraies données de production en lecture/
écriture locale seulement (684 QSO filtrés réellement appliqués au tableau
puis réinitialisés, 3013 groupes de doublons détectés, roster de net
ajouté/retiré proprement, aucun effet de bord laissé sur le serveur
partagé), revue adversariale par workflow (2 agents : complétude du
déplacement + références oubliées dans tout le dépôt).

## Reliquat

Toujours ~17000 lignes à traiter pour EV-7 (macro CW/vocal/RTTY, station
control, popups de CONFIG). `logx_logbook.js` est passé de 9193 à ~7800
lignes sur ces deux incréments cumulés.
