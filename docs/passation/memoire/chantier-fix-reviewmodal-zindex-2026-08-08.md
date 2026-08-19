---
name: chantier-fix-reviewmodal-zindex-2026-08-08
description: "Fix livré — #reviewModal (résultat analyse IA du règlement) z-index:1000 caché derrière .cat-modal:9000, passé à 9600 ; signale un piège de stacking pertinent pour le chantier sidebar CONFIG en cours"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T11:45:00.077Z
---

Correctif livré et fusionné sur `main` le 08/08/2026 (commit `dd3cd47`, branche
`fix/review-modal-zindex-derriere-popup-ai`).

## Bug signalé par F4GLD

« lorsque je lance une analyse de règlement de concours par IA, une fois
l'analyse fini je ne vois pas le résultat je le vois uniquement en fermant
le popup ». `analyzeRules()` (`logx_configuration.html`) est appelé DEPUIS
le popup `catmodal_ai` (Assistant IA), qui reste ouvert pendant les 30-90s
d'analyse. Le résultat (`#reviewModal`, propositions IA à relire avant
validation) avait `z-index:1000`, très inférieur au `z-index:9000` de
`.cat-modal` — le modal de résultat s'ouvrait bien (`display:block`) mais
restait rendu DERRIÈRE le fond noir du popup encore affiché. Fermer le
popup le révélait, laissant croire à tort qu'il fallait fermer pour voir
le résultat.

## Correctif

`z-index:1000` → `9600` (> `.cat-modal:9000` et `.config-sidebar:9500`).
Test de non-régression textuel ajouté (`test_review_modal_zindex.py`,
compare les 3 valeurs par regex, pas de DOM/py_mini_racer nécessaire).
Vérifié en navigateur par manipulation DOM pure : `openCategoryPopup('ai')`
(safe, pas de réseau) puis affichage manuel de `#reviewModal` avec contenu
factice — `analyzeRules()` n'a JAMAIS été invoqué pour de vrai pendant la
vérification (aurait déclenché un vrai `quickSave()` + un vrai appel réseau/
IA coûteux contre le serveur de production — cf. leçon déjà écrite dans
[[chantier-n1mm-rename-masterscp-fetch-2026-08-08]]).

## Pertinence pour le chantier sidebar CONFIG (RÉSOLU)

[[chantier-config-sidebar-nav-2026-08-08]] (fusionné) a bien gardé
`.cat-modal-box` à `z-index:9000` (panneau docké, plus de backdrop mais même
z-index) et `.config-sidebar` à `9500` — `#reviewModal:9600` reste donc
correctement au-dessus des deux, vérifié après fusion. Pas de régression.
