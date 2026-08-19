---
name: piege-continuer-nouveau-chantier-sur-branche-pr-deja-creee
description: Ne jamais démarrer un nouveau chantier sur une branche dont la PR a déjà été créée/mergée — gh pr merge --delete-branch échoue et il faut reconstruire une branche propre après coup
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-10T15:26:20.753Z
---

Le 10/08/2026 : une nouvelle demande utilisateur (« continu » interrompu par
un vrai message mi-tour) est arrivée alors que le chantier en cours
(bandeaux non bloquants, [[chantier-bandeaux-non-bloquants-chantier2-2026-08-10]])
avait déjà sa PR #9 créée. Au lieu d'ouvrir une nouvelle branche pour le
nouveau chantier, le travail a été fait directement sur
`fix/chantier2-bandeaux-non-bloquants` (déjà poussée, PR ouverte) — commit,
puis tentative de `gh pr merge 9 --squash --delete-branch` qui a échoué :
« Your local changes to the following files would be overwritten by
checkout... Aborting » (le nouveau commit local n'était pas sur la PR #9,
`gh pr merge` a besoin de checkout la branche cible pour la supprimer).

**Symptôme à reconnaître** : `gh pr merge` échoue avec une erreur de
checkout alors que la PR elle-même a bien mergé côté GitHub (vérifiable via
`gh pr view <n> --json state,mergedAt` — l'échec est PUREMENT local, sur
l'étape de suppression de branche).

**Correctif appliqué (à refaire à l'identique la prochaine fois)** :
1. Committer le travail en cours sur la branche polluée (sûr, réversible).
2. `git push origin --delete <branche>` (la PR est déjà mergée, sans
   risque).
3. `git checkout -B <nouvelle-branche> origin/main` (repart d'un main à
   jour, PAS de l'ancien commit local).
4. `git cherry-pick <hash-du-nouveau-commit>` — ne prend QUE le vrai
   nouveau travail, pas l'ancien commit déjà fusionné (qui existe déjà côté
   main sous un autre hash, via squash).
5. `git diff origin/main --stat` pour confirmer que seul le nouveau travail
   apparaît avant de pousser.
6. `git branch -D <ancienne-branche>` en local.

**Règle pour la prochaine fois** : dès qu'un nouveau sujet de travail
(pas un correctif du chantier en cours) démarre, vérifier `git branch
--show-current` et, si la branche a déjà une PR ouverte/mergée, créer une
NOUVELLE branche AVANT le premier `Edit`/`Write` — pas après coup. Le
réflexe « je continue là où j'étais » est correct pour poursuivre le MÊME
chantier, faux dès que le sujet change (nouveau message utilisateur avec
une demande distincte).

**Récidive le même jour** ([[chantier-lint-ruff-ci-2026-08-10]]) : cette
fois PAS de nouveau message utilisateur — juste un enchaînement autonome
"chantier terminé → chercher le prochain chantier" où la vérification de
branche a été oubliée par automatisme (l'attention était sur *quoi* faire
ensuite, pas sur *où* le faire). Repéré cette fois AVANT le commit
(`git status`/`git branch --show-current` par réflexe juste avant de
committer) plutôt qu'après — corrigé par `git stash push -u` + nouvelle
branche + `git stash pop`, sans le cherry-pick de la 1re occurrence
puisque rien n'avait encore été poussé/mergé. Coût quasi nul cette fois,
mais confirme que la vérification doit devenir un réflexe SYSTÉMATIQUE
en tout début de chaque nouveau sujet de travail — y compris (surtout)
quand c'est moi-même, pas l'utilisateur, qui décide d'enchaîner sur un
nouveau chantier.
