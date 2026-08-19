---
name: piege-double-arriere-plan-detache-log-incomplet
description: "PIÈGE : combiner run_in_background:true (harness) avec un `&` interne au script bash rend le vrai processus détaché — la notification 'completed exit 0' concerne le wrapper, pas la commande réelle, et le log peut sembler tronqué (09/08)"
metadata: 
  node_type: memory
  type: project
  modified: 2026-08-09T06:00:34.415Z
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
---

Découvert en lançant la suite pytest du 30e incrément EV-7
([[chantier-ev7-cw-panel2-audio-2026-08-09]]) : commande passée à Bash avec
`run_in_background: true` ET contenant elle-même `... > log 2>&1 &` (mise en
arrière-plan shell explicite) suivie d'un `echo $!`. Résultat : le harness
reçoit une notification "completed (exit code 0)" quasi immédiate — mais
c'est la commande WRAPPER (`echo $!`) qui s'est terminée, pas pytest
lui-même, qui continue de tourner en tâche VRAIMENT détachée (process orphelin
côté OS, plus suivi par le harness). Le fichier de log semblait figé à un
stade intermédiaire (`9963` octets, arrêté à "4%" lors d'une première lecture)
alors que le process réel (confirmé par `ps aux | grep python`) tournait
encore.

**Symptôme reconnaissable** : la notification de fin arrive anormalement
vite pour une suite de 8000+ tests, et relire le fichier de log immédiatement
après montre un contenu qui semble s'arrêter en plein milieu (pourcentage
partiel), sans ligne de résumé finale.

**Corrigé** en attendant activement la fin du VRAI PID via une commande
`until ! ps -p <PID> > /dev/null; do sleep 5; done` elle-même lancée avec
`run_in_background: true` (cette fois sans `&` interne, donc pas de double
détachement) — la notification de CETTE commande arrive au bon moment. Puis
confirmé en relançant la suite une seconde fois PROPREMENT (`run_in_background:
true` SEUL, sans `&` ni `echo $!`) : résultat identique (8792 tests, 0 échec,
même taille de fichier octet pour octet) — preuve que ce n'était pas une
troncature mais juste un rapport de progression prématuré.

**Réflexe pour toute suite pytest/commande longue future** : ne JAMAIS
combiner `run_in_background: true` avec un `&` shell interne à la même
commande. Utiliser SOIT l'un SOIT l'autre :
- `run_in_background: true` sur une commande simple (pas de `&` final) —
  cas normal, le harness gère tout, notification fiable à la vraie fin.
- Un `&` shell interne UNIQUEMENT si on reste au premier plan (pas de
  `run_in_background: true`) et qu'on veut nous-même gérer le PID.

Voir aussi [[piege-echo-exit-masque-code-sortie-reel]] pour un piège
apparenté (masquage de code de sortie, cause différente).
