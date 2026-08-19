---
name: robustesse-reseau-diffusion-publique
description: "Audit + corrections réseau pour que LogX AI ne bloque jamais (IP, antivirus, ou hors connexion) en vue d'une diffusion publique"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-21T10:39:30.797Z
---

L'utilisateur a explicitement cadré (20-21/07/2026) : LogX AI sera à terme diffusé publiquement à des inconnus, donc le logiciel ne doit JAMAIS bloquer à cause d'une IP figée, d'un antivirus spécifique, ou d'une absence de connexion Internet (usage terrain /P en zone blanche est un cas d'usage central, pas un cas limite).

**Why:** un audit réseau dédié (Workflow 10 agents, sauvegardé dans `scratchpad/audit_reseau.json` de la session — probablement expiré depuis) a trouvé 46 constats serveur + 14 côté polling client. Root cause récurrente : des appels réseau externes (QRZ/HamQTH/HamDB, cluster telnet, RBN, PSK Reporter, solaire/MUF N0NBH/KC2G, HRDLog, LoTW, Cloud Sync) s'exécutaient en synchrone DANS le thread qui sert la requête HTTP du navigateur, avec des timeouts cumulables jusqu'à 76-80s, voire un blocage potentiellement INDÉFINI pour Cloud Sync (open() sur un dossier cloud en mode placeholder/à la demande — OneDrive/Synology Drive/Dropbox — n'est pas couvert par un timeout Python, ce n'est pas un socket).

Commit `d45b592` (branche `feat/aide-config-websdr-guide`) a corrigé les 4 critiques + 9 hauts de l'audit serveur + les 2 critiques/3 hauts du polling client :
- `fetch_url()` (logx_utils.py) enveloppé dans un ThreadPoolExecutor + `.result(timeout=...)` — pattern maintenant établi dans le code pour border un appel réseau dont `urlopen(timeout=)` ne couvre PAS la résolution DNS (getaddrinfo, bloquant hors socket). Réutilisé tel quel dans logx_rbn.py, logx_qsl.py (sync_lotw), logx_cloudsync.py (sync_now).
- Disjoncteurs (circuit breaker) ajoutés : logx_callbook.py (cascade QRZ→HamQTH→HamDB), logx_qsl.py upload_hrdlog (boucle par QSO×2 hôtes).
- logx_clusters.py : `get_solar_cached()`/`get_muf_cached()` ajoutées — lecture seule côté handler HTTP, le refresh réseau part dans un thread de fond. Les handlers appelaient AVANT `fetch_solar_data()`/`fetch_muf()` directement (bloquant jusqu'à 30s cumulés sur cache expiré).
- Deadline socket recalculée à chaque `recv()` dans les boucles telnet (logx_clusters.py cluster/self-spot/ON4KST, logx_rbn.py) : `s.settimeout(timeout)` posé UNE fois ne borne pas la boucle, un seul recv() peut à lui seul dépasser le budget de la phase.
- `/hardware/state` (logx_http.py) fusionne rig+amp+wsjtx+rotor en 1 requête (logx_logbook.js pollait les 4 séparément à cadence rapide) ; endpoints individuels conservés (utilisés par logx_propagation.html/logx_scope.html). Chat en poll adaptatif selon l'ouverture du panneau plutôt qu'en continu.

**How to apply:** toute future modification touchant un appel réseau externe dans ce projet doit suivre ce même schéma (thread jetable + timeout dur, jamais de blocage synchrone dans un handler HTTP pollé). Si un nouveau module fait du réseau, vérifier s'il doit utiliser `fetch_url()` (déjà borné) plutôt que `urllib.request.urlopen()` en direct. Voir aussi [[qso-director-parity]] et [[radiocontest-phase0-done]] pour le contexte produit général.

**Piège rencontré cette session** : un serveur `python logx_serveur.py` tournait déjà sur le port 8080 (PID vérifié via `netstat`), lancé manuellement par l'utilisateur en dehors de mes outils — je ne l'ai PAS redémarré moi-même (processus que je ne contrôle pas, état en mémoire potentiellement important) et j'ai laissé à l'utilisateur le soin de le relancer pour charger les changements. Ne pas tuer/redémarrer un process sur un port qu'on n'a pas soi-même lancé via preview_start sans vérifier d'abord à qui il appartient.
