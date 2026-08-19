---
name: cinq-pages-sans-moteur-i18n
description: "5 pages de LogX AI ne chargent PAS logx_i18n.js (bande, mobile, panel, scope, wall) : elles restent en français quelle que soit la langue, et ~40 entrées de dictionnaire déjà écrites y sont inertes"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-30T21:29:33.315Z
---

Constaté le 30/07/2026 en vérifiant l'écran mural en allemand : la page était
intégralement en français, titre d'onglet compris, alors que le dictionnaire contenait
toutes ses clés. Cause : **`logx_wall.html` ne charge pas `logx_i18n.js`**.

Vérification sur les 13 pages : **cinq n'incluent pas le moteur** —
`logx_bande.html`, `logx_mobile.html`, `logx_panel.html`, `logx_scope.html`,
`logx_wall.html`. (Même famille que le constat déjà noté dans
[[fix-modale-awards-et-theme-fenetres-detachees]] : scope/panel/wall/mobile n'incluent
pas non plus `logx_statusbar.js`, d'où l'absence de thème jour/nuit.)

Conséquence : **environ 40 des 93 entrées** ajoutées le 30/07/2026 (commits `4b4e76f`,
`8500349`) visent ces pages. Elles sont écrites, justes, et **inertes** tant que le
moteur n'y est pas chargé.

**Why:** un utilisateur non francophone voit un cinquième de l'application en français
sans qu'aucun test ni aucun inventaire de dictionnaire ne le signale — l'inventaire
mesure les clés, pas le fait que la page charge le moteur.

**How to apply:** ajouter `<script src="logx_i18n.js"></script>` ne suffit PAS. Ces
pages rafraîchissent en continu (écran mural toutes les 3 s, bandscope à chaque spot,
horloges) et n'ont **aucun** marqueur `rc-i18n-live` — sans ce marquage préalable des
nœuds volatils, le MutationObserver retraduit en boucle. Enjeu aggravé par
[[contrainte-expedition-15-jours-continu]] : l'écran mural doit tenir 360 h d'affilée,
donc mesurer la stabilité (pas d'oscillation, pas de dérive mémoire) avant de conclure.
