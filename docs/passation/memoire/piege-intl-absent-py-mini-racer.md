---
name: piege-intl-absent-py-mini-racer
description: "PIÈGE tests JS : le V8 embarqué par py_mini_racer n'a AUCUN objet Intl global (pas juste des données ICU manquantes) — new Intl.DateTimeFormat(...) lève ReferenceError, alors que toLocaleDateString()/toLocaleTimeString() s'exécutent sans erreur (repli non-ICU)"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T15:50:17.643Z
---

Trouvé le 08/08/2026 pendant [[chantier-ev7-contest-picker-2026-08-08]], par
un agent de revue adversariale qui prototypait un test JS pour
`updateContestTiming()` (logx_contest_picker.js).

## Le piège

`updateContestTiming()` a une fonction interne `fmtLocal()` qui fait :
```js
new Intl.DateTimeFormat('fr-FR',{timeZone:'Europe/Paris',timeZoneName:'short'})
  .formatToParts(new Date(iso)).find(p=>p.type==='timeZoneName').value
```
Exécutée dans un `py_mini_racer.MiniRacer()` (moteur utilisé par tous les
tests JS du projet, ex. `test_logbook_menu_debut_fin.py`,
`test_qtc_panel_js.py`), cette ligne lève
`Uncaught ReferenceError: Intl is not defined` — vérifié directement :
`typeof Intl` renvoie `undefined` dans ce contexte. Ce n'est PAS un manque
de données de locale (ICU) comme sur certains runtimes Node minifiés :
l'objet global `Intl` lui-même n'existe pas dans ce binaire V8.

**Piège plus subtil** : juste avant, `fmtUTC()` utilise
`toLocaleDateString()`/`toLocaleTimeString()` (méthodes `Date.prototype`,
PAS `Intl` direct) — celles-ci s'exécutent SANS erreur (V8 a un repli
non-ICU pour ces deux méthodes précises). Un test qui ne couvrirait que la
partie UTC semblerait donc passer, en cachant le vrai problème sur la
partie locale/fuseau horaire.

## Ce que ça n'est PAS

Un bug du code produit. Dans un vrai navigateur, `Intl` existe toujours et
`updateContestTiming()` fonctionne normalement (vérifié en navigateur réel
pendant le même chantier). C'est une limite de l'infrastructure de test
seulement.

## Contournement vérifié

Stub minimal à ajouter au préambule DOM d'un futur test qui toucherait une
fonction avec `Intl.DateTimeFormat` :
```js
var Intl = { DateTimeFormat: function(){ return {
  formatToParts: function(){ return [{type:'timeZoneName', value:'CET'}]; }
}; } };
```
Testé et vérifié : neutralise le `ReferenceError`, renvoie `'CET'` comme
attendu.

## Comment l'appliquer

Recherché `grep -rn "Intl" tests/` avant ce chantier : zéro occurrence dans
tout le projet — aucun test EV-7 existant n'a encore rencontré ni contourné
ce piège, ce qui explique probablement en partie pourquoi aucune fonction
de formatage de date de la série EV-7 (ex. dans `logx_hardware_cat.js`,
`logx_wall.py` côté serveur) n'a de test JS dédié à ce jour côté client.
Avant d'écrire un futur test `py_mini_racer` touchant une fonction qui fait
du formatage de date/heure localisé, vérifier d'abord si elle utilise
`Intl` directement (pas seulement `toLocaleDateString`/`toLocaleTimeString`,
qui n'ont pas ce problème) — si oui, inclure ce stub dans le préambule DOM
dès le départ plutôt que de découvrir l'erreur en cours de rédaction.
