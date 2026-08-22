---
name: projet-doublon-isdup-mycall-non-corrige
description: "F4GLD a décliné le correctif isDup()/my_call pour le faux doublon TM6KJS/F4OQU — ne pas l'implémenter sans nouvelle demande"
metadata: 
  node_type: memory
  type: project
  originSessionId: e5854853-072f-4b5f-895a-57c4ab0111d2
  modified: 2026-08-21T19:01:28.479Z
---

Le 21/08/2026, un faux avertissement DOUBLON a été signalé (F4OQU déjà
loggé alors qu'il s'agissait du log TM6KJS, indicatif actif différent).
Cause identifiée : `isDup()` dans `logx_logbook.js` ne tient pas compte du
champ `my_call` du QSO (qui distingue les identités de station), contrairement
aux fonctions d'export qui le font déjà. Un correctif a été proposé (faire
tenir compte de `my_call` dans `isDup()` et l'équivalent serveur
`_find_dup()`/`qso_scope_id` dans `logx_http.py`) mais **explicitement refusé
par F4GLD** : « ne corrige pas j'ai effacé » — il a supprimé le doublon
manuellement plutôt que de vouloir un changement de comportement.

**Pourquoi** : pas de demande de fond derrière le signalement initial, juste
un signalement ponctuel réglé par un geste manuel — pas une confirmation que
le comportement actuel est jugé correct pour l'avenir.

**Comment appliquer** : ne pas réimplémenter ce correctif de soi-même dans une
session future. Si le même symptôme (faux doublon entre deux indicatifs actifs
différents sur le même correspondant) revient et que F4GLD le signale à
nouveau, proposer le correctif à ce moment-là plutôt que de le déclencher
préventivement.
