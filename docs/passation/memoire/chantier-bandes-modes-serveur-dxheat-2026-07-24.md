---
name: chantier-bandes-modes-serveur-dxheat
description: CONFIG bandes/modes pilotés par le vrai règlement serveur (plus de CONTEST_FILTERS dupliqué) + ajout DXHeat comme source cluster
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-24T16:40:23.146Z
---

Commits 86731fb, ef687e3, b8a1135 (24/07/2026) : deux chantiers menés en parallèle via Workflow (celui-ci + [[chantier-feedback-batch2-2026-07-24]] simultanément, tous deux touchant `logx_configuration.html` — gérés sans collision en évitant de toucher ce fichier pendant que l'autre workflow tournait encore).

**1) Bandes/modes CONFIG = règlement serveur.** `CONTEST_FILTERS` (objet client dupliqué à la main, ~35 concours, jamais synchronisé avec `CONTEST_DEFINITIONS`) est remplacé par `SERVER_CONTEST_RULES` rempli depuis `/data/calendar` (déjà appelé au chargement via `mergeServerContests()`). `LEGACY_CONTEST_FILTERS` ne sert plus que de repli pour les ~25 concours absents de `CONTEST_DEFINITIONS` (CCD mensuelles, Marconi, F8TD, 50 MHz REF/IARU, UFT...).

PIÈGE trouvé en revue adversariale (corrigé en b8a1135) : `_resolveContestFilters()` traitait bandes/modes avec un OR unique (`bands.includes('all') || modes.includes('all')` → lève TOUTE restriction) — un concours `bands:['all'], modes:['CW']` (CW-only, toutes bandes) laissait SSB/FT8 cochables. Corrigé pour résoudre chaque axe INDÉPENDAMMENT (`{bands: null|[...], modes: null|[...]}`, `null` = axe libre). Vérifié en direct : REF_RPH→2m/70cm+SSB, CQ_WW_SSB→160-10m+SSB, WWA_2027_JAN→FT2/PSK bien traduits en mode_ft8/mode_rtty, SOTA→aucune restriction, REF_MARCONI→repli legacy.

**2) DXHeat (dxheat.com) ajouté comme 6e source cluster HF** (`fetch_dxheat()` dans `logx_clusters.py`, toggle `src_dxheat` actif par défaut). API JSON publique sans auth, ramène HF+VHF/UHF en un seul appel avec un vrai locator structuré (`DXLocator`) au lieu d'un regex sur commentaire.

PIÈGES trouvés en revue adversariale (corrigés en b8a1135) :
- Le locator structuré de DXHeat n'était jamais lu dans `build_ranked_spots` (`logx_scoring.py`) — seul le commentaire libre était reparsé, vide dans l'échantillon réel → corrigé pour prioriser le champ structuré s'il a un format Maidenhead plausible.
- Doublons : le lot générique 'HF' (qui contient aussi les spots VHF/UHF de DXHeat reclassés via fréquence) et les caches dédiés 144/432/50 tournent en parallèle sans dédup croisée → même station affichée deux fois sur un concours mixte HF+VHF. Corrigé par un `seen_station_band` set sur (indicatif, bande réelle).

Note technique : dans `build_ranked_spots`, le champ `source` de chaque spot classé est normalisé en `'cluster'` (pas `'dxheat'`/`'dxsummit'`/etc.) — comportement PRÉEXISTANT partagé par toutes les sources cluster, pas un bug de cette intégration (a pu induire en erreur lors de la vérification).

**Vérification indépendante effectuée** (au-delà de la revue adversariale du workflow lui-même) : relance serveur propre + tests live navigateur sur 5 concours réels, appel direct `fetch_dxheat()` en Python (100 spots réels, bandes 7/14/18/21/24/28/50/144 MHz correctement classées via fréquence, filtre digital 100→66 spots), `/data/spots_ranked` 0→40 après refresh. Suite complète : 1073 tests, 0 échec (reproduit indépendamment deux fois). Aucune occurrence réelle de "QSO Director".
