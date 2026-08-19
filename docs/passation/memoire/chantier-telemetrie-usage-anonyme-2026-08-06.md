---
name: chantier-telemetrie-usage-anonyme
description: "Télémétrie d'usage anonyme livrée (#162, 06/08/2026, merge ce3347d) — seul toggle réseau du projet activé par défaut (opt-out) ; piège de fuite de fichiers de test + 2 pannes runner GitHub dans la même session"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-06T19:18:01.864Z
---

Livré juste après le chantier CAT propriétaire, dans la foulée de la même
session (06/08/2026). Nouveau module `concours/logx_telemetry.py` : heartbeat
QUOTIDIEN minimal (identifiant d'installation aléatoire, version, OS) —
jamais de callsign/QSO.

## Décisions prises avec F4GLD (AskUserQuestion)

- **Opt-out, pas opt-in** : activée par défaut, désactivable en un clic dans
  CONFIG (section 19) — SEUL toggle réseau du projet dans ce cas ; tous les
  autres (scoreboard/ClubLog Live/RBN...) restent désactivés par défaut.
  Nécessite un traitement spécial partout où l'absence du champ doit valoir
  "activé" plutôt que "désactivé" (`cfg.get('telemetry_enabled', True)`,
  restauration CONFIG UI avec 3 cas distincts absent/true/false explicites).
- **Endpoint volontairement vide** : aucune infrastructure serveur n'existe
  encore côté F4GLD pour recevoir ce heartbeat. Le module est complet et
  fonctionnel côté client, mais `send_heartbeat()` ne tente RIEN tant que
  `telemetry_endpoint` n'est pas renseigné — prêt à brancher dès qu'une
  destination existera, sans code à ajouter côté LogX AI.

## Piège trouvé PENDANT le chantier (pas avant)

**Fuite de fichiers dans le dépôt partagé** (même famille que
[[piege-tests-ecrivent-dans-le-depot]]) : les 2 tests HTTP de bout en bout
(`test_http_telemetry_test_*`) appellent le VRAI handler `/telemetry/test`
via un serveur réel — celui-ci exécute `send_heartbeat()` pour de vrai, qui
appelle `_stamp()`/`_install_id()`, qui écrivent dans les constantes
MODULE-LEVEL `_STAMP_FILE`/`_ID_FILE` (chemins relatifs au cwd = `concours/`).
Tous les tests UNITAIRES du même fichier isolaient bien ces chemins via
`_isole_fichiers(monkeypatch, tmp_path)` — mais les 2 tests HTTP, ajoutés en
dernier, ont été oubliés. Résultat : `git status` a montré
`telemetry_id.json`/`telemetry_sync.json` comme fichiers non suivis dans
`concours/` après un run de la suite complète. Détecté en vérifiant `git
status` avant de committer (réflexe déjà établi dans ce projet) — jamais par
un test qui aurait échoué, puisque le comportement testé restait correct.
Réflexe pour la prochaine fois : dans un fichier de test mêlant unitaire et
HTTP-de-bout-en-bout sur un module à état persisté sur disque (`_STAMP_FILE`/
équivalent), vérifier que CHAQUE test qui exerce le vrai handler (pas juste
les tests unitaires directs) isole aussi les chemins de fichiers.

## 2 pannes runner GitHub Actions dans cette même session (après le chantier CAT)

En plus de la panne déjà notée dans la mémoire du chantier CAT, 2 nouvelles
occurrences distinctes du même symptôme (« job not acquired by Runner of
type hosted even after multiple attempts ») :
1. Le run PUSH-déclenché sur `main` pour le commit de fusion CAT est resté
   `queued` ~15 min avant d'échouer avec ce message — alors qu'un run
   MANUEL (workflow_dispatch) sur le MÊME commit avait déjà réussi entre
   temps. `gh run rerun` a suffi à le faire repasser au vert.
2. Le run manuel sur `feat/telemetrie-usage-anonyme` est lui-même resté
   `queued` 12+ minutes avant d'être annulé et redéclenché avec succès au
   2e essai.
3. Le tag `v0.9-beta23` poussé n'a déclenché AUCUN run automatique du
   workflow "Build multi-OS (release)" (pourtant `on: push: tags: 'v*'`
   confirmé dans le fichier, tag confirmé présent sur le remote via
   `git ls-remote --tags`) — contournement : `gh workflow run "Build
   multi-OS (release)" -f tag=v0.9-beta23` (workflow_dispatch, le workflow
   accepte bien un input `tag` pour ce cas).
Conclusion : période d'engorgement notable des runners hébergés gratuits de
GitHub ce jour-là (06/08/2026 fin d'après-midi/soirée), pas un problème du
dépôt. Réflexe déjà noté dans la mémoire CAT, confirmé une 2e/3e fois : ne
jamais interpréter un `queued` anormalement long ou un run manqué sur push
comme un signe d'échec du code — vérifier via un déclenchement manuel avant
de creuser le code.
