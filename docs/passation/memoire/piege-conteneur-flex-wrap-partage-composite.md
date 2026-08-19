---
name: piege-conteneur-flex-wrap-partage-composite
description: KEYER VOCAL (LOGBOOK) affiché en mosaïque désordonnée — un conteneur flex-wrap partagé conçu pour des boutons uniques recevait des lignes composites (2 boutons) sans largeur propre
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-04T05:18:49.856Z
---

`.macro-btns{display:flex;gap:5px;flex-wrap:wrap}` + `.macro-btn{min-width:76px;
flex:1;max-width:110px}` est conçu pour des **boutons UNIQUES** qui doivent
former une grille qui s'enroule (macros F1-F8, CALLBOT B1-B4). `renderVoicePanel()`
(KEYER VOCAL, `concours/logx_logbook.js`) empilait à la place un `<div>`
composite (bouton lecture + bouton ⏺ enregistrement) PAR message, sans lui
donner de largeur propre — le navigateur le traitait comme une tuile qui se
redimensionne à son contenu et en plaçait plusieurs par ligne au lieu
d'empiler CQ/RÉPONSE/REPORT/MERCI verticalement. Retour F4GLD 04/08/2026
(capture d'écran) : « ce n'est pas du tout fonctionnel ».

**Symptôme** : boutons et ronds d'enregistrement dispersés en mosaïque,
labels et durées difficiles à associer à leur bouton.

**Cause** : un conteneur flex-wrap partagé entre deux usages différents
(grille de boutons simples vs liste de lignes composites) sans que les
lignes composites ne reçoivent leur propre largeur — et sans override des
`min-width`/`max-width` hérités de `.macro-btn` sur les boutons internes.

**Correctif** (`concours/logx_logbook.js`, `renderVoicePanel()`) :
- `width:100%;box-sizing:border-box` sur le `<div>` de chaque ligne — force
  une seule ligne par tuile dans le conteneur `flex-wrap`.
- `min-width:0;max-width:none` en inline style sur les boutons internes pour
  écraser les bornes de `.macro-btn` (110px de large max sinon).

**Comment l'attraper avant l'utilisateur** : ce genre de bug de mise en page
JS-générée est invisible à la lecture du CSS seul et invisible aux tests
`py_mini_racer` existants (ils vérifient la logique JS, pas la géométrie
rendue). Vérifié en navigateur réel via `getBoundingClientRect()` sur les
enfants du conteneur après injection de données factices — pas de
screenshot nécessaire, juste comparer `rowTop`/`x`/`w` de chaque ligne.
Réflexe pour toute suite : avant de considérer un panneau JS-généré fini,
vérifier si son conteneur CSS est PARTAGÉ avec un autre usage aux
contraintes différentes (voir aussi [[piege-verifier-sur-donnees-reelles]]).
