---
name: chantier-ev7-qtc-2026-08-07
description: "6e incrément EV-7 livré — QTC (WAE) extrait vers logx_qtc.js, candidat trouvé par un agent Explore lancé en tâche de fond pendant la vérification du 5e incrément"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T21:09:53.820Z
---

Chantier livré et fusionné sur `main` le 07/08/2026 (commit `eadd9f3`, merge
de `feat/ev7-refactor-qtc`, commits de contenu `76c5744` + `2078c4b`).

## Contexte

6e incrément du refactor EV-7, enchaîné directement après
"[[chantier-ev7-popout-selfspot-2026-08-07]]" sur consigne explicite de
F4GLD de continuer sans s'arrêter pendant ~7h (message avant de se coucher :
« je vais me coucher tu as 7h devant toi pour avancer donc go ne t'arrete
pas »). Ultracode non explicitement réactivé — méthodologie solo rigoureuse
(2 passes pytest + vérification navigateur + auto-relecture du diff),
identique au 5e incrément.

Cible trouvée par un **agent Explore lancé en tâche de fond** pendant
l'attente de la CI du 5e incrément (parallélisation du temps mort). Lui
avait été donnée la liste complète des candidats déjà écartés comme piégés
(vocal/audio, chat/partner, carte Leaflet, compas inline, bandscope/
waterfall/filtre spots, WSJT-X/wait-and-pounce, rappel ON4KST, raccourci
bureau, broadcast channel) pour ne pas les re-proposer. A identifié le bloc
QTC (WAE) — saisie et historique des séries QTC du règlement WAEDC — comme
propre, avec un audit exhaustif des appelants de chacune de ses 11
fonctions (zéro trouvé hors du bloc).

## Ce qui a été livré

`concours/logx_qtc.js` (nouveau, 172 lignes) : `refreshQTC`, `showQTCPanel`,
`closeQTCPanel`, `resetQTCFields`, `suggestQTCSeriesNumber`,
`renderQTCRows`, `addQTCRow`, `removeQTCRow`, `saveQTCSeries`,
`renderQTCList`, `deleteQTCSeries` + `QTC_BANDS`/`qtcEntries`/`qtcRows`.
`logx_logbook.js` : 7893 → 7721 lignes (6 incréments cumulés depuis 9193).

## Aucune régression trouvée cette fois (contrairement aux incréments 4 et 5)

`tests/test_qtc_panel_js.py` avait déjà été identifié comme le seul test à
mettre à jour (l'agent Explore avait aussi vérifié `test_logbook_menu_debut_fin.py`,
`test_i18n_dialogues.py`, `test_notify_dynamic_i18n.py` et plusieurs autres
fichiers Python purs, tous confirmés sans impact). Corrigé avant la
première exécution pytest — 2 passes complètes vertes du premier coup,
aucune surprise. Confirme que le grep exhaustif par un agent dédié (plutôt
que mes propres greps rapides) attrape mieux ce genre de piège que
l'approche manuelle des incréments précédents.

## Vérification

Suite pytest complète (2 passes vertes). Navigateur réel sur les vraies
données de production : `refreshQTC()` confirmé contre 1 série QTC
existante réelle ; `showQTCPanel()`/`addQTCRow()`/`removeQTCRow()`/
`closeQTCPanel()` testés en conditions réelles (comptage de lignes
correct). `saveQTCSeries()`/`deleteQTCSeries()` volontairement PAS
appelées en conditions réelles (écriture réelle dans le log de production)
— vérifiées uniquement par diff strict (extraction byte-identique).

## Revue adversariale (Ultracode réactivé en cours de route)

Un system-reminder a signalé Ultracode actif APRÈS le commit initial (pas
demandé explicitement par F4GLD dans cette fenêtre, mais un signal système à
respecter). Lancé une revue adversariale Workflow (3 agents) sur la branche
déjà poussée, avant fusion : **équivalent** (diff strictement vide, la
1re tentative d'un agent avait cru trouver des écarts à cause d'un artefact
de scratchpad périmé — corrigé en re-vérifiant) ; **2 constats mineurs** —
commentaire pointeur obsolète dans `logx_http.py` (`logx_logbook.js:
saveQTCSeries` → `logx_qtc.js:saveQTCSeries`) et `JS_EXTRAITS_EV7` dans
`test_logbook_menu_debut_fin.py` qui avait pris du retard sur 2 incréments
(`logx_popout_selfspot.js` du 5e, `logx_qtc.js` lui-même — trou silencieux
sans conséquence actuelle mais qui aurait laissé passer une future faute de
frappe) ; **aucune dépendance problématique**. Les 2 constats corrigés dans
un commit séparé (`2078c4b`) avant fusion, re-testés, CI reconfirmée verte.
**Leçon** : penser à étendre `JS_EXTRAITS_EV7` à CHAQUE incrément qui ajoute
un nouveau fichier, même si aucune entrée de menu n'y pointe encore — sinon
la liste dérive silencieusement.

## Reliquat

~7721 lignes restent dans `logx_logbook.js`. IMPORT ADIF (~96 lignes,
propre, déjà validé par 2 agents Explore différents) reste le candidat le
plus évident pour un 7e incrément — probablement à combiner avec un voisin
non contigu (GPS→LOCATOR MAIDENHEAD, PRÉREMPLISSAGE MODAL) pour atteindre
une taille plus confortable. AUTOCOMPLETE INDICATIF et CACHE CLUSTER
soupçonnés piégés (liés au chemin critique SAISIE via `onCallInput`) mais
pas encore vérifiés en détail — à explorer avant tout futur incrément.
