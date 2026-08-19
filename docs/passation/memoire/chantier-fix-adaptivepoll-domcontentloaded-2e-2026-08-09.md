---
name: chantier-fix-adaptivepoll-domcontentloaded-2e-2026-08-09
description: "2e tentative de fix ReferenceError adaptivePoll (09/08/2026, commit b13d5c0, merge fee01e6) — le fix du 08/08 (dc194d6) avait été perdu, jamais fusionné, écrasé par une extraction EV-7 ultérieure repartant de l'ancien code"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T02:43:14.285Z
---

Régression trouvée par hasard le 09/08/2026 pendant la vérification
navigateur du 24e incrément EV-7 (Édition QSO, sans rapport) :
`ReferenceError: adaptivePoll is not defined` reproduit à 100% au
chargement de `logx_logbook.html`. Diagnostic : c'est le MÊME bug déjà
corrigé le 08/08 ([[chantier-fix-adaptivepoll-domcontentloaded-2026-08-08]],
commit `dc194d6`) — mais ce commit vivait sur une branche
(`claude/loving-noyce-c5ded3`) qui n'a **jamais été fusionnée sur main**
(confirmé par `git merge-base --is-ancestor dc194d6 HEAD` → faux). Le
fichier `logx_hardware_cat.js` a ensuite été intégralement régénéré par
l'extraction EV-7 phase 2 (`e2cec50`, RADIO CAT/AMPLI/ROTOR/WSJT-X) à
partir de `logx_logbook.js` — qui contenait encore l'ANCIEN
`setTimeout(fn,0)`, puisque le fix `dc194d6` n'y était jamais arrivé. Le
correctif a donc silencieusement disparu sans qu'aucune régression de test
ne le signale (le bug est un ReferenceError swallowed en console, invisible
à `pytest` sauf test dédié — et ce test dédié
(`test_hardware_cat_script_order.py`) était sur la MÊME branche perdue que
le fix).

**Leçon retenue** : un fix mergé nulle part n'est pas un fix — vérifier
`git merge-base --is-ancestor <commit> HEAD` avant de faire confiance à un
commit cité en mémoire, surtout après un refactor/extraction majeur du
fichier concerné (ici, l'extraction EV-7 phase 2 a régénéré tout le fichier
en repartant du dernier état MERGÉ de logx_logbook.js, pas de la branche de
fix).

## Correctif (identique au 08/08, réappliqué)

`logx_hardware_cat.js` (chargé AVANT `logx_logbook.js`, convention EV-7)
utilisait `setTimeout(fn,0)` pour différer l'appel à `adaptivePoll()`
(définie dans `logx_logbook.js`) — une COURSE, pas une garantie : si le
parseur HTML rend la main en attendant qu'un `<script src>` restant finisse
de charger, le timer peut se déclencher avant que `adaptivePoll()` existe.
Remplacé par `document.addEventListener('DOMContentLoaded', fn)` avec repli
synchrone si `document.readyState !== 'loading'` — garanti par la spec HTML
de ne se déclencher qu'une fois TOUS les `<script>` classiques exécutés.

## Test de non-régression recréé

`concours/tests/test_hardware_cat_script_order.py` (le fichier original du
08/08 n'existe plus sur main, jamais mergé) : rejoue l'ordre RÉEL des
`<script>` via DEUX `ctx.eval()` py_mini_racer séparés (jamais concaténés,
sinon les déclarations `function` seraient hoistées ensemble et le bug
d'ordre deviendrait invisible), avec `document.readyState='loading'` au
1er eval (le pire cas réaliste). Vérifie qu'un écouteur `DOMContentLoaded`
est bien enregistré (pas d'appel direct), puis que le déclencher produit un
VRAI appel `fetch('/hardware/state')` — pas juste l'absence d'exception.
**Pouvoir discriminant vérifié manuellement** (`git stash` du fix, relance
du test, `git stash pop`) : échoue avec le message attendu sur l'ancien
code, passe sur le nouveau.

Piège rencontré en écrivant le test : une 3e assertion prévue (repli
synchrone si `readyState` déjà `'complete'` à l'exécution de
`logx_hardware_cat.js`) s'est révélée IRRÉALISTE pour cette page — dans
l'ordre de chargement réel, `logx_hardware_cat.js` s'exécute TOUJOURS avant
`logx_logbook.js` (qui définit `adaptivePoll`), donc si le document était
déjà "complete" à ce moment, `logx_logbook.js` aurait déjà dû s'exécuter
aussi — contradiction. Retiré plutôt que forcé artificiellement.

## Vérification

Suite pytest complète verte. Vérification navigateur réelle (hard reload) :
`typeof adaptivePoll === 'function'`, journal réseau confirmant des appels
répétés réussis à `/hardware/state` (200 OK) — le polling tourne
réellement, pas juste "pas d'exception". Piège de vérification rencontré :
`read_console_messages` conservait un historique PÉRIMÉ (erreurs de l'ancien
code, lignes 524/525) après le `navigate force:true` — pas fiable seul pour
confirmer un correctif JS après coup ; le journal réseau
(`read_network_requests`) et l'état JS live (`typeof adaptivePoll`,
`document.readyState`) sont la preuve qui compte.

Suite : reprise du 25e incrément EV-7 (Exports EDI + Cabrillo,
candidat n°4 de [[inventaire-ev7-23e-2026-08-09]]).
