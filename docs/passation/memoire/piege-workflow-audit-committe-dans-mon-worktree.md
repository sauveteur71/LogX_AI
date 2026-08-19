---
name: piege-workflow-audit-committe-dans-mon-worktree
description: "Un Workflow d'audit qui tourne en parallele committe dans le worktree ET la branche ou je travaille — isoler ne suffit pas, il faut le verifier avant chaque commit/rebase"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-26T18:11:15.357Z
---

Un Workflow d'audit lance en arriere-plan (agents de correction autonomes) **ecrit dans le
worktree git ou je travaille**, pas seulement dans le repertoire principal. Constate le
26/07/2026 : cree un worktree isole `fix/points-si-concours` precisement pour eviter la
collision, et un agent de l'audit y a quand meme committe `96e843c` (pastille orage) —
le reflog de MA branche le montrait en `fix/points-si-concours@{2}`. Plus tard, le meme
audit a laisse 3 fichiers modifies non committes dans ce worktree, ce qui a fait echouer
`git rebase` avec « You have unstaged changes ».

**Why:** un worktree separe isole le repertoire de travail, pas le depot. Les agents
resolvent le depot et peuvent choisir n'importe quel worktree. Croire l'isolation acquise
mene a committer le travail d'un autre sous son propre message, ou a le detruire.

Pire : l'audit a ecrit **DEUX implementations concurrentes du meme correctif** (unicite des
id de QSO), dans deux repertoires de travail differents, par deux agents differents. L'une
ignorait les tombstones et la numerotation dense. Elles n'etaient pas deux versions
successives d'un meme travail — il fallait comparer et TRANCHER, pas empiler. Et pendant
que je committais la mienne, l'agent a affine la sienne puis l'a posee sur main tout seul :
ma branche est devenue un doublon dont seuls mes tests supplementaires avaient de la valeur.

**How to apply:**
- Avant `git commit`, verifier `git status --short` ET relire `git log --oneline -3` :
  un commit inconnu entre ma base et mon HEAD = l'audit est passe par la.
- Avant `git rebase`, verifier qu'il n'y a pas de modifications non committees qui ne
  sont pas de moi — ne jamais les stash/jeter, elles peuvent valoir 300 lignes de tests.
- `git merge-tree --write-tree main <branche>` fait une fusion A BLANC (aucune ecriture) :
  sortie vide + code 0 = aucun conflit. Ideal pour verifier sans toucher a un depot que
  d'autres agents ecrivent.
- Ne PAS fusionner pendant que des agents ont des modifications non committees dans le
  repertoire principal ; verifier `git status --porcelain` juste avant, et abandonner
  si non vide.
- Dire clairement a l'utilisateur quels commits ne sont pas de moi.
- Devant deux versions d'un meme correctif, les DIFFER (apres `tr -d '\r'` : les fins de
  ligne CRLF/LF font passer `diff` pour « tout le fichier differe ») et choisir sur
  criteres, pas prendre la premiere trouvee. Puis re-verifier juste avant de fusionner :
  l'autre agent a pu poser la sienne sur main entre-temps.

Voir [[feedback-branche-avant-main-gros-chantiers]] pour la regle branche + CI avant main.
