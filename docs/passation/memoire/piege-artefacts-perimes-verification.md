---
name: piege-artefacts-perimes-verification
description: "Cinq affirmations fausses, même cause : un artefact lu sans vérifier son CONTEXTE (serveur de la veille, rapport de la veille, git log sur une autre branche, CI verte d'un autre run, inventaire de grep périmé par une branche parallèle)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-01T07:23:09.432Z
---

Le 27/07/2026, **quatre** affirmations fausses en une session, **même cause racine** : un artefact lu comme s'il reflétait l'état actuel, sans vérifier son contexte. À chaque fois l'information était plausible, bien formée, et fausse.

1. **Serveur laissé tourner par moi.** J'avais lancé `python logx_serveur.py` via `nohup` le 26/07 à 06:48 et je ne l'avais jamais arrêté. Le lendemain, l'utilisateur démarrait son .bat et voyait la **0.9-beta5** alors que la 0.9-beta7 était installée : mon processus servait le code chargé en mémoire la veille. Ce n'est pas un désagrément interne — ça a fait **mentir le logiciel à l'utilisateur sur sa propre version**, et lui a fait croire que la mise à jour avait échoué.

2. **Rapport de tests périmé.** J'ai parsé un `full.xml` et annoncé « la suite est verte, 1378 tests » alors que le fichier datait **de la veille 09:57** et que la vraie passe tournait encore (elle était à 40 %). Le vrai résultat (1710 tests, 0 échec) n'est arrivé que 9 minutes plus tard.

3. **`git log` lu sur une autre branche que celle que je croyais.** Une session parallèle avait checkouté `fix/i18n-prefixe-emoji-attributs` **dans le même répertoire de travail**. J'ai commité, lu `git log` (qui montrait bien mes commits), et annoncé « poussé sur main ». En réalité `git push origin main` était un no-op : mes commits étaient sur leur branche. J'ai ensuite cru à une perte de données et à un reset de `main`, alors que rien n'avait bougé. `git reflog show main` l'a prouvé : main n'a jamais contenu ces commits.

4. **CI verte réutilisée pour un autre run.** J'ai fusionné sur `main` en me fiant à une CI verte obtenue sur un arbre Git **identique** (même SHA d'arbre, vérifié). `main` est quand même passé au rouge : un test réseau non déterministe sur Linux (`BrokenPipeError` après un 413 qui ferme la connexion). Un arbre identique ne garantit pas un résultat identique quand un test dépend d'une course.

**Why:** dans tous les cas l'artefact existait, était lisible, et répondait plausiblement — rien ne signalait qu'il était vieux. Un fichier `--junitxml` n'est pas effacé au lancement de pytest : il n'est réécrit qu'à la FIN. Tant que la passe tourne, on lit donc le rapport de la passe PRÉCÉDENTE, avec un contenu parfaitement bien formé. Même piège pour un serveur : il répond en HTTP 200, sans rien indiquer de son âge.

**How to apply:**
- Avant de croire un rapport de tests, **regarder son horodatage** (`ls --time-style=full-iso`) et le comparer à l'heure de lancement. Mieux : nom de fichier unique par passe, ou supprimer le rapport avant de lancer.
- Ne jamais conclure « vert » sur la seule existence du rapport — vérifier aussi que le processus pytest est terminé (`pgrep`), pas seulement que le fichier est là.
- **Arrêter tout serveur que j'ai lancé** dès que la vérification est finie. Un serveur de test qui survit à la session devient un serveur fantôme qui sert du vieux code.
- Pour savoir à qui appartient un process sur un port : le **processus parent** tranche. `nohup.exe` / Git bash = lancé par mes outils, donc je peux l'arrêter ; `cmd.exe` issu du .bat = lancé par l'utilisateur, voir [[robustesse-reseau-diffusion-publique]] qui dit de ne pas y toucher sans vérifier.
  `Get-CimInstance Win32_Process -Filter "ProcessId = N"` donne `ParentProcessId`, `CreationDate` et `CommandLine`.
- **`git branch --show-current` AVANT chaque commit**, et `git reflog show main` avant de conclure qu'un commit a disparu. Une autre session peut checkouter une branche dans le MÊME répertoire de travail — un `git log` reste alors parfaitement cohérent tout en décrivant une branche qui n'est pas celle qu'on croit. Voir [[piege-workflow-audit-committe-dans-mon-worktree]] : un répertoire partagé, pas seulement un dépôt partagé.
- **Une CI verte ne vaut que pour SON run**, même à SHA d'arbre identique. Un test qui dépend d'une course réseau peut passer puis tomber sur le même code. Ne pas présenter une CI verte antérieure comme une garantie pour la fusion — le seul verdict qui compte est celui du run déclenché par la fusion elle-même.
- Corollaire produit trouvé le même jour : un test « quelque chose répond-il sur le port ? » ne répond JAMAIS à « est-ce la bonne version qui répond ? ». Voir [[piege-faux-dom-stub-et-passes-paires]] pour la même famille d'erreur côté tests, et [[suite-tests-flakes-sous-charge]] pour la question à se poser devant un test qui tombe : testait-il le mécanisme ou l'invariant ?

**5e cas, 01/08/2026 — l'INVENTAIRE de départ périme pendant le chantier.** Migration de `datetime.utcnow()` : grep exhaustif au début = 59 sites, tous traités, suite verte, CI verte, annoncé complet. Or `main` avait avancé pendant ce temps (fusion `feat/websdr-refonte`) et introduit **3 nouveaux appels** dans un module qui n'existait pas dans mon inventaire : 59 → 62. Un chantier « éliminer tous les X » a donc une cible MOBILE dès qu'une branche parallèle vit en même temps.
- Avant d'annoncer un chantier de ce type complet : `git fetch` puis **refaire le grep sur `origin/main`**, pas seulement sur sa propre base. `git log --oneline base..origin/main` dit si le sol a bougé.
- Ce qui a sauvé le coup : un **garde-fou anti-régression par AST** ajouté dans la même passe, qui aurait fait tomber la suite dès la fusion. Pour tout chantier « plus jamais ce motif », écrire le test qui l'interdit — c'est lui qui rattrape ce que l'inventaire manque. L'AST plutôt qu'un grep textuel : insensible aux docstrings qui CITENT le motif éliminé.
- Vérifier aussi qu'un garde-fou échoue vraiment : **le saboter** (réintroduire la régression), voir la suite rougir, restaurer. Un test qui ne peut pas échouer ne protège rien — voir [[piege-faux-dom-stub-et-passes-paires]].
