---
name: chantier-mysql-sync-radioclub-2026-08-07
description: "Synchro MySQL partagée (#163) livrée après revue adversariale — 2 bugs critiques de résurrection/perte silencieuse de QSO trouvés et corrigés avant fusion"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T05:48:32.322Z
---

Chantier #163 (MySQL partagé / profils multiples, demandé après #162
télémétrie) livré et fusionné sur main le 07/08/2026 (merge `7183a38`,
commits `618fa8a` implémentation + `05e0cc9` correctifs). Nouveau module
`concours/logx_mysql_sync.py`, 4e mécanisme de sync multi-poste du projet
(après Cloud Sync, LAN sync, MAJ résiliente) — architecture délibérément
alignée sur `logx_cloudsync.py` (boucle de fond, tombstone `deleted_at`
plutôt que suppression réelle) plutôt que sur le système `_make_driver()`
brand de `logx_amp.py`, car le protocole (SQL) n'a rien à voir avec CAT/CI-V.

**Revue adversariale AVANT fusion (Workflow, 4 dimensions, 17 agents,
~18 minutes)** a trouvé 11 constats confirmés dont 2 bugs critiques réels :
1. Le PUSH réinitialisait inconditionnellement `deleted_at=NULL` (ON
   DUPLICATE KEY UPDATE sans clause WHERE) — ressuscitait silencieusement
   une suppression posée par un AUTRE poste tant que celui-ci gardait
   encore le QSO en shared_log local. Le commentaire du code prétendait à
   tort qu'une clause WHERE protégeait ce cas.
2. Les suppressions distantes n'étaient appliquées que par ID seul, jamais
   par la clé (call+band+mode+date+heure) — comme l'id est `Date.now()`
   côté client SANS coordination inter-poste, une collision d'id entre
   deux postes pouvait supprimer à tort le QSO LOCAL d'un poste qui n'a
   rien à voir (y compris son scan QSL attaché).
Plus : docstring qui affirmait faussement que MySQL empêche toute collision
d'id (faux, corrigé pour documenter honnêtement la même limite déjà admise
par `logx_cloudsync.py`), absence de `read_timeout`/`write_timeout` pymysql
(un gel réseau après connexion bloquait le socket indéfiniment, gardant
`_sync_serial_lock` acquis pour toujours), et `mysql_password` absent de
`SECRET_FIELDS`/`SECRET_CONFIG_FIELDS` (seul mot de passe du projet resté
en clair dans `.server_config.json` ET localStorage).

**Correctifs délégués à un agent en arrière-plan** (prompt très détaillé,
chaque décision de conception déjà tranchée dans le prompt — pas de marge
d'interprétation laissée à l'agent) : 5 bugs corrigés + 13 tests ajoutés,
8639 tests verts. Vérifié moi-même ligne par ligne (diff du commit de
correctif) avant fusion plutôt que de faire confiance au seul rapport —
tout correspondait exactement à ce qui avait été demandé.

**Flake rencontré en vérifiant** : `test_backup_pick_folder_http.py` a
échoué une fois sur la suite complète (8600+ tests) avec un
`TimeoutError` socket, sans rapport avec les fichiers touchés par ce
commit — repassé au vert immédiatement en isolation. Traité comme un flake
d'environnement (contention sous charge), pas une régression — cohérent
avec [[suite-tests-flakes-sous-charge]].
