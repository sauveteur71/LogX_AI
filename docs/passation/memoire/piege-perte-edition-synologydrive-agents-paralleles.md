---
name: piege-perte-edition-synologydrive-agents-paralleles
description: "PIÈGE — des fichiers édités reviennent silencieusement à leur état d'avant édition dans ce dépôt SynologyDrive (agents parallèles OU édition solo) ; ne jamais faire confiance au rapport d'un agent, toujours re-grepper soi-même juste avant de committer"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T11:21:54.912Z
---

Découvert le 05/08/2026 pendant [[chantier-audit-pre-beta-2026-08-05]] (33
agents Workflow éditant chacun un fichier disjoint du dépôt en parallèle) :
au moins 7 des 33 agents ont vu un fichier qu'ils venaient d'éditer avec
succès **revenir silencieusement à son contenu d'AVANT édition** entre deux
appels d'outils — sans erreur explicite hormis, parfois, le message Edit
« le fichier avait été modifié sur disque depuis la dernière lecture ». La
plupart des agents l'ont détecté eux-mêmes (par `git diff`/relecture) et
réappliqué le correctif, en le documentant. **Mais 2 agents sur 33 (cloudsync,
update) ont RAPPORTÉ un succès complet et des tests verts alors que leur
correctif était en réalité ABSENT du disque** — découvert seulement par une
repasse manuelle de vérification (grep du marqueur attendu de chacun des 58
constats de l'audit, un par un) faite par l'agent orchestrateur.

**Cause probable (non confirmée avec certitude)** : le dépôt de travail est
sous `SynologyDrive\...` — une synchronisation cloud du dossier peut entrer
en course avec une écriture locale très récente et la faire disparaître
transitoirement.

**Règle à appliquer systématiquement** (pas seulement pour ce chantier) :
après tout chantier impliquant des agents (Workflow ou `Agent`) qui éditent
des fichiers de ce dépôt — a fortiori en parallèle — NE JAMAIS se contenter
du `testsResult`/rapport final d'un agent, même détaillé, même quand il
affirme avoir lui-même repéré et corrigé un incident similaire en cours de
route. Toujours, avant de committer :
1. `git status --short` pour confirmer que TOUS les fichiers attendus
   apparaissent modifiés (un fichier manquant de la liste = piste immédiate).
2. Pour chaque changement censé avoir été appliqué, un grep indépendant du
   marqueur/motif exact attendu contre le fichier RÉEL sur disque — pas une
   confiance dans le rapport texte de l'agent.
3. Si un correctif manque, le réappliquer directement soi-même plutôt que de
   relancer l'agent (plus rapide, et on a déjà toute l'info nécessaire).

Voir aussi [[piege-artefacts-perimes-verification]] (lire un artefact sans
contexte = affirmations fausses) — même famille de piège, cause différente.

**Récidive confirmée SANS agents parallèles (08/08/2026)** : le piège n'est
pas limité aux chantiers Workflow multi-agents — reproduit en solo, un seul
agent, une seule édition, sur `concours/logx_logbook.js` (correctif largeur
de barre négative dans `drawHourChart`, commit `7002539`). Edit confirmé
appliqué immédiatement après l'outil Edit, puis disparu du disque au moment
de préparer le commit quelques minutes plus tard (grep du marqueur ajouté :
aucune correspondance). Réappliqué, re-grepé pour confirmer AVANT de
`git add`/`git commit` (pas seulement après l'Edit) — c'est ce deuxième
re-grep, juste avant le commit, qui a révélé la perte. **Renforce la règle** :
re-vérifier juste avant de committer, pas seulement juste après avoir édité —
la fenêtre de course peut s'ouvrir n'importe quand entre les deux, même sans
autre agent actif en parallèle dans la conversation. Piste : `concours/` est
un « additional working directory » partagé entre plusieurs worktrees/sessions
Claude Code sur ce même dépôt SynologyDrive — une autre session peut écrire
sur le même fichier à tout moment, pas seulement des agents Workflow lancés
depuis la session courante.
