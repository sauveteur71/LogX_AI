---
name: chantier-fix-adaptivepoll-domcontentloaded-2026-08-08
description: "Fix cause racine ReferenceError adaptivePoll (08/08/2026, commit dc194d6, branche claude/loving-noyce-c5ded3) : setTimeout(fn,0) remplacé par DOMContentLoaded dans logx_hardware_cat.js -- l'ancien correctif EV-7 était une course contre le réseau, pas une garantie"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0fb18354-9d18-4afb-bdc8-1de32a1b06df
  modified: 2026-08-08T16:35:38.861Z
---

Investigation demandée par F4GLD après que `ReferenceError: adaptivePoll is
not defined` (logx_hardware_cat.js:524) soit réapparue en boucle sur
logx_logbook.html, malgré un correctif déjà appliqué lors d'un chantier
précédent ([[chantier-ev7-radio-cat-2026-08-08]]) et repérée entre-temps
« au passage » lors d'un autre chantier ([[chantier-fix-rect-negatif-graphe-heure-2026-08-08]],
qui avait créé une tâche de fond dédiée pour cette investigation).

## Cause racine

`logx_hardware_cat.js` (chargé AVANT `logx_logbook.js`, convention EV-7)
utilisait `setTimeout(fn, 0)` pour différer l'appel à `adaptivePoll()`
(définie dans `logx_logbook.js`) après l'exécution synchrone de tous les
`<script>` classiques. Ce n'est PAS une garantie mais une course : si le
parseur HTML doit rendre la main à la boucle d'événements en attendant
qu'un des `<script src>` restants (`contest_picker.js`, `dxcc_lookup.js`,
`logx_logbook.js` -- ~9000 lignes) finisse de charger depuis le réseau, le
timer (déjà en attente depuis l'exécution de `logx_hardware_cat.js`) peut se
déclencher AVANT que `logx_logbook.js` n'ait fini de s'exécuter.

Les deux extractions EV-7 suivantes (10e et 11e incrément, `contest_picker.js`
et `dxcc_lookup.js`, mergées le même jour APRÈS le premier correctif) ont
allongé la file de `<script>` restants entre `logx_hardware_cat.js` et
`logx_logbook.js` -- rendant cette course perdue de façon systématique là où
elle passait auparavant (au moins lors de la vérification qui avait validé
le premier correctif).

## Correctif

Remplacé le `setTimeout(fn, 0)` par un listener `DOMContentLoaded`
(`document.addEventListener('DOMContentLoaded', fn)`, avec repli synchrone
si `document.readyState !== 'loading'`) -- garanti par la spec HTML de ne se
déclencher qu'une fois le document ENTIÈREMENT parsé, ce qui inclut
l'exécution synchrone de TOUS les `<script>` classiques quel que soit leur
temps de récupération réseau. Élimine la course structurellement plutôt que
d'élargir un délai empirique.

## Piège rencontré pendant la vérification

[[piege-serveur-8080-sert-depot-principal-pas-worktree]] -- le serveur déjà
lancé sur `localhost:8080` sert le DÉPÔT PRINCIPAL, pas ce worktree ; même un
Ctrl+Shift+R ne pouvait pas faire apparaître le correctif. Contourné en
montant une instance statique isolée (`python -m http.server --directory
concours`, port 8099, config ajoutée à `.claude/launch.json` local, non
trackée) -- confirmé : plus de `ReferenceError` après correctif.

## Test de non-régression

`concours/tests/test_hardware_cat_script_order.py` -- rejoue l'ordre réel
des `<script>` via DEUX `ctx.eval()` py_mini_racer séparés (pas concaténés
en un seul, sinon toutes les déclarations `function` seraient hoistées et le
bug d'ordre invisible -- motif déjà documenté dans
[[chantier-ev7-radio-cat-2026-08-08]]). Contre-vérifié manuellement que ce
test échoue bien avec la même `ReferenceError` sur l'ancien code
(`setTimeout(fn,0)`) avant de le committer, pour confirmer son pouvoir
discriminant réel.

## Vérification

Suite pytest complète verte (1 skip sans rapport, index CW local absent sur
ce poste). Commit `dc194d6` sur la branche `claude/loving-noyce-c5ded3`
(déjà dédiée, aucun commit préexistant au-dessus de `main`).
