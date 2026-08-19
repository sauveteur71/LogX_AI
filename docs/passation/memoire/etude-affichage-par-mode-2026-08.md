---
name: etude-affichage-par-mode-2026-08
description: "Étude complète de ce qui doit s'afficher selon usage_mode (simple/club/expédition/concours) — docs/ETUDE_AFFICHAGE_PAR_MODE_2026-08.md, demandée 05/08/2026"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-05T06:35:29.046Z
---

F4GLD a demandé le 05/08/2026 une étude logique de l'affichage selon les 4
`usage_mode` (simple/contest/expedition/radioclub) — exemple donné : en mode
expédition on ne chasse théoriquement pas, donc l'affichage CHASSE est
secondaire (mais reste accessible, pas bloqué) ; si CW n'est pas dans les
modes activés, décoder du CW reste possible exceptionnellement mais
inutile à afficher en permanence.

**Distinction centrale à ne jamais confondre** : `usage_mode` (config —
simple/contest/expedition/radioclub) est un axe TOTALEMENT SÉPARÉ du MODE
RADIO courant (SSB/CW/FT8/etc., piloté par `renderModeButtons()`/
`updateKeyerPanels()`). Le premier dit « quel type d'activité fait
l'utilisateur aujourd'hui », le second « quel signal est actuellement sur
l'air ». Facile à mélanger dans le code, source des deux écarts trouvés.

**Principe retenu pour toute décision d'affichage** : masquer ≠ bloquer
l'accès. Un élément jugé secondaire dans un mode donné reste accessible
(bouton/lien discret), jamais totalement supprimé — l'utilisateur peut
toujours vouloir l'usage exceptionnel.

Résultat de l'étude (document complet livré + envoyé via SendUserFile) :
état des lieux montrant que la plupart du conditionnel existant était déjà
correct, et seulement 2 vrais écarts trouvés — tous deux corrigés dans
[[chantier-cw-hors-mode-bandeau-expedition-2026-08]] : bandeau discret
CHASSE en expédition, bouton de forçage manuel du décodeur CW hors mode CW.
Le hub CONFIG (toujours visible) et le multi-op/écran mural ont été jugés
déjà corrects, explicitement recommandé de NE PAS les changer.
