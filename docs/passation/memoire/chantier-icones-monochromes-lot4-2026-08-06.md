---
name: chantier-icones-monochromes-lot4-2026-08-06
description: "Dernier lot d'icônes monochromes CONFIG/LOGBOOK — 14 vraies conversions sur ~260 emoji restants, le reste est structurellement hors de portée"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-06T08:04:40.818Z
---

Suite de [[chantier-design-graphite-cuivre-2026-08]] (lots 1-3, terminés le
03/08/2026). L'utilisateur a demandé de continuer les "icônes monochromes
restantes" — CLAUDE.md indiquait encore 216 emoji dans CONFIG et 38 dans
LOGBOOK après le lot 3.

**Découverte clé avant tout code** : un recensement fin (pas un simple
comptage) a montré que sur ~260 emoji bruts restants, ~112 sont des flèches
(→←↑↓) utilisées comme connecteurs de prose ("Menu → Sous-menu → Option"),
jamais des icônes décoratives — jamais dans le scope du chantier. Une bonne
partie du reste est techniquement impossible à convertir (`<option>`,
`placeholder="…"`, `title="…"`, `alert(...)` — rendu texte brut forcé par le
navigateur). La majorité de ce qui restait ensuite est du texte de statut
JS posé via `.textContent` (piège déjà documenté au lot 2 : SVG y afficherait
du balisage brut). Seuls **14 candidats étaient de vraies icônes UI
statiques convertibles sans risque** — voir le détail dans CLAUDE.md.

**Bug trouvé en vérification, pas en écrivant le code** : le bouton QTC
(`✉ QTC : 0`) semblait un candidat sûr (statique, pas de `.textContent`
visible dans le premier grep), mais `refreshQTC()` dans `logx_logbook.js`
réécrivait `qtcBtn.textContent` à chaque appel réseau — effaçant le SVG en
silence. Détecté seulement en ouvrant la page dans un navigateur et en
inspectant `.innerHTML` après un cycle de rafraîchissement, PAS en lisant
le code seul. Corrigé proprement (icône fixe + `<span id="qtcCount">`
dédié) plutôt que de revenir à l'emoji.

**Piège de vérification navigateur répété** : `file://` sur ces deux gros
fichiers rend un "instantané statique" dégradé (6 enfants de `<body>` au
lieu de la vraie page, tas d'erreurs JS attendues) — pas fiable pour
vérifier du rendu réel. Retour à l'instance serveur isolée port 8099, cette
fois STRICTEMENT en lecture (jamais `saveConfig()`), voir
[[piege-instance-isolee-partage-server-config]] pour pourquoi cette
prudence est nécessaire sur CE port précis.

Livré : `68265f6` (main), CI verte. CLAUDE.md documente désormais que le
compteur d'emoji brut restant n'est plus un indicateur de travail à faire —
la quasi-totalité de ce qui reste est hors de portée par construction
(technique ou politique établie), pas juste "pas encore fait".
