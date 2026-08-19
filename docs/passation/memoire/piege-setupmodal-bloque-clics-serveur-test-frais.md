---
name: piege-setupmodal-bloque-clics-serveur-test-frais
description: "Sur un serveur de test LOGBOOK fraîchement démarré, #setupModal (overlay plein écran, z-index 1000) intercepte silencieusement tous les clics tant qu'il n'est pas complété — aucune erreur, juste rien qui se passe"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-16T09:41:35.843Z
---

En vérification navigateur d'une fonctionnalité LOGBOOK sur un serveur de
test fraîchement démarré (sans config préalable), un clic sur un champ du
formulaire QSO (`#inputCall` etc.) via `computer{action:"left_click", ref:
...}` **n'échoue pas** mais ne fait rien non plus : `document.activeElement`
reste `BODY`, le texte tapé ensuite part dans le vide. `read_page`/`find` ne
signalent rien d'anormal (les champs listés semblent normaux) — le piège est
invisible tant qu'on ne pense pas à vérifier `document.elementFromPoint(x,y)`
à la position du clic.

**Cause réelle** : `#setupModal` (`.modal-overlay`, `z-index:1000`,
`display:flex` par défaut sur un poste jamais configuré — texte "Configure
ton poste avant de commencer la saisie") recouvre TOUTE la page et intercepte
le clic AVANT qu'il n'atteigne le champ visé en dessous. Les champs de CE
modal (`#setupCallsign`, `#setupLocator`, `#setupOperator`) apparaissent bien
dans `read_page` — c'est un piège de LECTURE : on peut confondre son champ
indicatif (`#setupCallsign`, placeholder "F6KQJ/P") avec celui du VRAI
formulaire LOGBOOK (`#inputCall`, placeholder "INDICATIF CORRESPONDANT") si
on ne regarde pas l'id exact.

**How to apply** : avant toute interaction navigateur avec le formulaire
LOGBOOK sur un serveur de test frais, fermer ce modal en premier :
```js
document.getElementById('setupCallsign').value = 'F4GLD';
document.getElementById('setupLocator').value = 'JN18';   // n'importe quel locator valide 4+ car.
document.getElementById('setupOperator').value = 'OP1';
setupDone();   // exige les 3 champs non vides (logx_logbook.js), sinon no-op silencieux + notify()
```
Si un clic sur un champ censé être visible ne produit aucun effet observable
(pas d'erreur, juste rien), réflexe : vérifier `document.activeElement` puis
`document.elementFromPoint(x, y)` à la position ciblée AVANT de suspecter le
code fraîchement modifié — un overlay qui capte silencieusement les clics est
indiscernable d'un bug de câblage réel sans cette vérification. Voir aussi
[[piege-service-worker-perime-fetch-failed]] pour un autre piège de la même
famille (symptôme identique à un bug produit, cause en fait environnementale).
