---
name: piege-push-qsolog-live-render-auto
description: "PIÈGE vérification navigateur : pousser un QSO synthétique dans qsoLog (in-memory) sur logx_logbook.html peut apparaître dans le tableau réel SANS appeler renderLog() soi-même — un cycle de rafraîchissement automatique le fait à la place"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T19:08:17.881Z
---

Découvert en vérifiant le fix du champ FRÉQUENCE dans la modale d'édition
QSO (08/08/2026, commit `82298ab`).

## Le piège

Pour tester `editQSO(id)` avec des données réalistes sans écrire sur le
serveur (motif déjà établi : jamais de vraie action réseau destructive
pendant une vérification), le réflexe est de faire
`qsoLog.push({id: idFactice, ...})` directement en JS dans le navigateur,
sans jamais appeler `saveEdit()` (qui seul fait le `fetch('/log/update')`).

**Ce qui a été supposé, à tort** : que `qsoLog.push(...)` seul, sans appel
explicite à `renderLog()`, resterait invisible dans le tableau du log tant
qu'aucun rendu n'est déclenché.

**Ce qui s'est réellement passé** : sur `localhost:8080` (l'instance de
PRODUCTION réelle de F4GLD, cf. [[piege-serveur-8080-sert-depot-principal-pas-worktree]],
9876 vrais QSO), le QSO factice (indicatif `PY4JW`, copié depuis la capture
d'écran de l'utilisateur pour rendre le test réaliste) est apparu comme
ligne `#9876` en tête du tableau « DERNIERS QSO SAISIS » — visible dans le
DOM réel — alors qu'aucun `renderLog()` n'avait été appelé explicitement
dans le code de test. Un mécanisme de rafraîchissement automatique déjà
présent sur la page (probablement le polling adaptatif documenté ailleurs,
`adaptivePoll`/`updateStats`/une resynchronisation périodique) a fini par
re-rendre le tableau et a repris l'état local `qsoLog` tel quel, factice
compris.

## Correctif appliqué

Nettoyage immédiat : `qsoLog = qsoLog.filter(q => q.id !== idFactice)` +
`renderLog()` + `updateStats()` explicites pour forcer le retour à l'état
propre, puis **rechargement serveur complet** (`navigate` + Ctrl+Shift+R)
pour confirmer que rien n'avait été persisté côté serveur (`qsoLog.length`
revenu à 9876, aucun id négatif résiduel).

## Réflexe pour toute vérification future sur cette page

- Ne JAMAIS supposer qu'un `qsoLog.push(...)` restera silencieux jusqu'au
  prochain appel manuel à `renderLog()` — le tableau peut se re-rendre tout
  seul à tout moment sur cette page (polling actif en permanence).
- Après tout `qsoLog.push(...)` de test, **toujours** `filter()` + explicite
  `renderLog()`/`updateStats()` dans la MÊME séquence d'appel JS, avant de
  rendre la main — ne pas compter sur un futur nettoyage différé.
- Confirmer par un rechargement serveur dur (pas juste une relecture de
  `qsoLog` en mémoire) que rien n'a fui côté persistant, même quand aucun
  `fetch()` n'a été appelé consciemment.
- Préférer, quand c'est possible, un indicatif et des données clairement
  fictives (`TEST1AW` plutôt qu'un indicatif réel copié d'une capture
  d'écran de l'utilisateur) pour qu'un résidu visible soit immédiatement
  identifiable comme test, pas confondu avec un vrai QSO.
