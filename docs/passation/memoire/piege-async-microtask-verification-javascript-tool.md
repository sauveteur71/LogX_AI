---
name: piege-async-microtask-verification-javascript-tool
description: "PIÈGE vérification navigateur : tester une async function (dispatchEvent/.click()) puis lire le résultat (location.href) dans le MÊME appel javascript_tool renvoie un état périmé — la continuation après un await tourne en microtask APRÈS la fin du bloc synchrone"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-16T12:19:41.551Z
---

Trouvé le 16/08/2026 en vérifiant `closeCategoryPanel()` (devenue `async
function` lors de [[chantier-config-panel-plein-ecran-fermeture-uniforme-secrets-2026-08-16]])
dans le navigateur de test via `mcp__Claude_Browser__javascript_tool`.

## Le piège

```js
document.getElementById('someCloseBtn').click(); // déclenche une async function
location.href // lu DANS LE MÊME appel javascript_exec
```
Renvoie l'URL AVANT navigation, laissant croire que `closeCategoryPanel()` ne
navigue pas — alors que le code est correct. La continuation d'une fonction
`async` après un premier `await` s'exécute comme une microtask, ordonnancée
APRÈS que tout le bloc synchrone du script `javascript_exec` courant se soit
terminé (y compris le `location.href` qui suit sur la ligne d'après). Le
`click()` lance bien l'exécution de la fonction jusqu'au premier `await`,
mais la suite (et donc la navigation) n'a pas encore eu lieu au moment où le
script se termine et renvoie sa valeur.

## Contournement vérifié

Scinder en DEUX appels `javascript_exec` séparés : un pour déclencher le
clic/l'événement, un second (appel d'outil distinct, donc après un vrai
aller-retour) pour lire `location.href`/l'état résultant. Confirmé : le
second appel voit bien la navigation effectuée.

## Comment l'appliquer

Réflexe pour toute vérification navigateur d'un handler `async` (ou d'un
handler synchrone qui appelle en interne une fonction `async` sans l'attendre
de façon bloquante côté test) : ne JAMAIS lire l'état résultant dans le même
`javascript_exec` que celui qui déclenche l'action. Si le comportement semble
absent alors que le code parait correct à la lecture, vérifier d'abord si la
fonction déclenchée est `async`/contient un `await` avant de suspecter un bug
réel dans le code produit.
