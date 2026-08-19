---
name: piege-min-width-vs-max-width-css
description: "min-width posé sur une règle CSS générique gagne TOUJOURS sur un max-width inline plus spécifique en cas de conflit — la spécificité ne s'applique pas entre propriétés différentes"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-04T14:51:53.234Z
---

En corrigeant `.form-row` dans `logx_configuration.html` (04/08/2026,
voir [[chantier-panadapter-introuvable-form-row-ce-concours-2026-08]]), mon
premier jet de fix a écrit :

```css
.form-row{display:flex;flex-wrap:wrap;gap:16px}
.form-row>.form-group{flex:1;min-width:150px}
```

avec pour commentaire (faux) que ce `min-width` par défaut serait « toujours
annulé par un style inline plus spécifique (max-width/flex) déjà posé sur
des instances individuelles ». C'est FAUX et je l'ai écrit moi-même dans un
tour de session précédent sans le vérifier.

**La règle réelle** : `min-width` et `max-width` sont deux propriétés
DIFFÉRENTES — la cascade CSS (spécificité, ordre, `!important`) ne
départage jamais deux propriétés différentes entre elles, seulement deux
règles qui visent LA MÊME propriété. Une fois que `min-width` (feuille de
style) et `max-width` (inline) sont TOUTES LES DEUX appliquées, c'est
l'algorithme de calcul de largeur qui les combine : si elles sont en
conflit (min > max), **min-width gagne toujours**, quelle que soit la
spécificité de la règle qui l'a posé.

Conséquence concrète trouvée AVANT de committer (repérée en relisant mon
propre raisonnement, pas par un test) : le bouton supprimer d'une ligne de
transverter a `style="max-width:60px"` en ligne — avec mon `min-width:150px`
par défaut, ce bouton se serait retrouvé forcé à 150px de large (un simple
icône ✕ dans une colonne aussi large que le champ OSCILLATEUR à côté).

**Fix retenu** : ne PAS poser de min-width par défaut du tout —
`.form-row>.form-group{flex:1}` suffit. Le "minimum automatique" de
flexbox (spec moderne : un enfant flex avec `flex-basis:0%` et
`min-width:auto` ne descend pas sous sa taille min-content) empêche déjà
les champs sans taille propre (CAT2/SO2R, aucun style inline) de
s'effondrer à 0 — vérifié en direct : ces champs se répartissent
proprement (204px/278px selon la ligne) sans qu'aucun min-width explicite
ne soit nécessaire.

**Comment appliquer** : avant d'ajouter un `min-width` par défaut à une
règle CSS générique dans ce projet (ou tout projet), lister TOUTES les
instances qui en héritent et vérifier si l'une d'elles pose déjà un
`max-width` inline plus petit — si oui, le `min-width` par défaut le
CASSERA silencieusement (pas d'erreur, juste un élément trop large), quelle
que soit la spécificité de l'inline. Se méfier en particulier de son propre
raisonnement passé sur la cascade CSS : « c'est écrasé par plus
spécifique » n'est vrai qu'entre règles ciblant LA MÊME propriété.
