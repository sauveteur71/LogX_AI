---
name: fix-portee-concours-annee
description: "Le mode CONCOURS affichait tout le log (import ADIF, autres concours/années) au lieu de l'édition active — corrigé par une portée \"concours#année\""
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-21T11:38:35.027Z
---

Commit `4d91f6a` (branche `feat/aide-config-websdr-guide`, 21/07/2026). Rapporté par l'utilisateur : "quand je passe en mode concours le logiciel reprend le log de base au lieu d'un log vierge ou du dernier log de ce concours ; la carte est toute en vert dès le début".

**Root cause** : `shared_log` est UN SEUL log global (pas de fichier séparé par concours). Un motif bogué répété dans 9 endroits indépendants (`logx_departments.py`, `logx_countries.py`, `logx_coach.py`, `logx_scoreboard.py`, `logx_storage.py`) traitait un QSO SANS tag concours (`contest == ''` — import ADIF générique, WSJT-X sans concours actif) comme un JOKER comptant pour N'IMPORTE QUEL concours filtré (`q.get('contest','') in ('', contest_id)`). En plus, l'identifiant de concours (`REF_CDF_HF_SSB`) ne portait pas l'année, donc une édition annuelle non purgée se confondait avec la suivante.

**Fix** : `logx_storage.py` a maintenant 3 fonctions de portée — `qso_scope_id(qso)` (dérive `'concours#année'` des champs PROPRES du QSO, jamais de la config), `active_scope_id(cfg)` (portée de la config active), `cfg_scope_id(cfg)` (comme active_scope_id mais `''` si `usage_mode == 'simple'` — jamais de filtrage en logbook simple). Tout le code qui filtrait par concours a été corrigé pour comparer des portées (contest+année), pas juste le nom brut. **`/log/list` filtre désormais par portée active** — c'est le coeur du correctif visible pour l'utilisateur (le logbook/carte/score en mode concours ne montrent QUE l'édition active).

**Why (piège découvert en cours de route)** : une revue adversariale après le premier passage a trouvé 7 endroits où j'avais laissé passer le nom BRUT du concours (sans année) à des fonctions déjà corrigées pour attendre une portée — `/log/archive` (clear=true SANS concours actif effaçait TOUT shared_log, vraie perte de données), `/log/check`, `/qtc/add`, `build_debrief`, `/qsl/upload`, `/log/reset` (fusionnait deux éditions annuelles dans un seul Cabrillo). Tous corrigés. **Leçon** : quand une même correction de fond doit être répétée dans plusieurs call sites, greper le pattern AVANT de considérer le travail fini, et faire relire par un agent indépendant qui exécute réellement le code (pas juste qui le lit) — la review adversariale a effectivement exécuté chaque fonction avec des cas de repro, ce qui a trouvé des bugs que la simple lecture aurait manqués.

**How to apply** : toute future modification touchant le filtrage de `shared_log` par concours dans ce projet DOIT passer par `qso_scope_id`/`active_scope_id`/`cfg_scope_id` (logx_storage.py), jamais une comparaison directe de `q.get('contest','')`. `logx_wall.py` (écran mural) fait exception DÉLIBÉRÉE : par défaut il montre tout (mode expédition), le filtrage par portée n'est actif que si un contest_id est explicitement passé. `logx_awards.py` (`spotted_new_ones`) reste intentionnellement lifetime-unscoped (coaching "jamais travaillé à VIE").

463 tests passent (26 nouveaux, dont `tests/test_http_scope_endpoints.py` — premier banc de tests HTTP de bout en bout sur serveur réel de ce projet, `http.server.HTTPServer` sur port éphémère + `urllib.request`, nécessaire car les endpoints concernés vivent dans le dispatch monolithique `do_GET`/`do_POST` sans découpage testable autrement).

Voir aussi [[rebrand-logx-ai]] pour la convention de nommage des fichiers.
