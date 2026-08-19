---
name: piege-deux-depots-github-distincts-logx-ai
description: Il existe DEUX dépôts GitHub séparés sous le compte sauveteur71 — le code (radioaamateur-program-Contest) et un site de présentation (LogX_AI) — à ne jamais confondre
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T05:48:00.037Z
---

Le compte GitHub `sauveteur71` héberge DEUX dépôts distincts, sans lien de
fork ni de rename entre eux :

- **`sauveteur71/radioaamateur-program-Contest`** — le dépôt de CODE (celui
  cloné localement dans `C:\Users\parri\SynologyDrive\RADIOAMATEUR\Programme
  pour contest`, remote `origin`). Toute la description CLAUDE.md, les
  chantiers, les PR, les Actions CI concernent CE dépôt.
- **`sauveteur71/LogX_AI`** — un second dépôt séparé, description « Site de
  présentation de LogX AI — logbook radioamateur intelligent », créé le
  2026-08-05, ~500 Ko. Pas de remote git local vers lui dans ce poste de
  travail.

**Piège vérifié en le faisant (07/08/2026)** : demande F4GLD « fais-moi le
wiki », avec une capture d'écran de la page wiki vide de GitHub. `gh repo
view` (sans argument, résolu depuis le remote `origin` local) donne
`radioaamateur-program-Contest` — mais la capture d'écran montrait bien
`sauveteur71 / LogX_AI` en haut de page. Cloner
`radioaamateur-program-Contest.wiki.git` échoue silencieusement avec
« Repository not found » (message trompeur : ce n'est PAS un problème
d'authentification ni de wiki vide, juste le MAUVAIS dépôt). Confirmé par
`gh api user/repos --jq '.[] | select(.name | test("(?i)logx|radioam"))'`
qui liste bien les deux séparément.

**Comment vérifier avant toute action GitHub future** : ne jamais déduire le
dépôt cible d'une capture d'écran utilisateur à partir du remote git local
seul — lister les repos via `gh api user/repos` (ou demander confirmation)
dès qu'un nom affiché à l'écran (« LogX_AI ») diffère du nom du remote local
(« radioaamateur-program-Contest »). Voir aussi
[chantier-wiki-logx-ai-2026-08-07](chantier-wiki-logx-ai-2026-08-07.md) pour
le wiki lui-même.
