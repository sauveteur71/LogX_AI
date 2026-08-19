---
name: piege-echo-exit-masque-code-sortie-reel
description: "PIÈGE Bash : 'cmd ; echo DONE_$?' rapporte l'exit code de echo (toujours 0), pas celui de cmd — a fait annoncer une suite pytest verte alors qu'elle avait 3 échecs (08/08/2026, incrément EV-7 Callbook)"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T19:41:44.657Z
---

## Le piège

Pour lancer la suite pytest complète en tâche de fond et connaître son
résultat, la commande utilisée était :

```
pytest concours/tests -q > /tmp/sortie.txt 2>&1; echo DONE_$?
```

La notification de complétion de la tâche en fond rapporte le code de
sortie de la DERNIÈRE commande de la chaîne — ici `echo DONE_$?`, qui
réussit TOUJOURS (exit 0), quel que soit le code de sortie de pytest qu'il
vient d'afficher. Le `$?` est bien évalué correctement (il capture le vrai
code de pytest dans le texte imprimé), mais c'est le code de sortie de la
commande `echo` elle-même, pas la valeur qu'elle affiche, qui remonte à la
notification de tâche.

**Conséquence réelle (08/08/2026, 16e incrément EV-7, Callbook)** : la
notification a annoncé "completed (exit code 0)", lu comme "suite verte",
et le commit du 16e incrément a été poussé sur la base de cette fausse
confirmation. La CI GitHub Actions a échoué juste après (3 tests réels en
échec dans `test_macro_cw_serie_bande.py`) — l'échec existait déjà en
local au moment du push, invisible faute d'avoir vérifié le contenu réel
du fichier de sortie avant de committer.

## Correctif appliqué

Écrire le VRAI code de sortie DANS le fichier de sortie lui-même, sans `;`
qui romprait la chaîne de code de sortie :

```
pytest concours/tests -q > /tmp/sortie.txt 2>&1
echo "EXIT_REEL=$?" >> /tmp/sortie.txt
```
(deux commandes Bash séparées, pas jointes par `;` sur la même ligne — la
deuxième s'exécute dans tous les cas puisqu'elle ne dépend pas du code de
sortie de la première).

Puis lire explicitement la ligne `EXIT_REEL=` en fin de fichier avant de
conclure quoi que ce soit — jamais se fier au seul statut/résumé de la
notification de tâche en fond pour une commande composée de plusieurs
étapes reliées par `;`, `&&` ou `||`.

## Réflexe pour toute suite de tests lancée en fond

- Ne jamais chaîner `cmd ; echo ...` ou `cmd ; autre_cmd` si le code de
  sortie de `cmd` doit rester exploitable — soit ne pas chaîner du tout
  (laisser le process se terminer sur son propre code), soit écrire le
  code de sortie réel dans le fichier de log lui-même en deux commandes
  séparées.
- Après toute suite de tests en fond, greper `FAILED`/`ERROR` (ou vérifier
  la ligne de résumé `N passed`) dans le fichier de sortie AVANT de
  committer/pousser — ne jamais se contenter du statut "completed" de la
  notification, qui ne dit rien sur le contenu réel de la commande.
