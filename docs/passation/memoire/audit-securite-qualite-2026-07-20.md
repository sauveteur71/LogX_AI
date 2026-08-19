---
name: audit-securite-qualite-2026-07-20
description: "Audit exhaustif LogX AI du 20/07/2026 — 113 constats confirmés, clé API réelle exposée à révoquer, 4 critiques"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-30T08:51:03.423Z
---

Audit multi-agents (22 auditeurs + vérification adversariale) mené le 20/07/2026 sur tout le projet. 253 constats bruts → **113 confirmés** : 4 critiques, 26 hautes, 66 moyennes, 17 basses. Rapport HTML : https://claude.ai/code/artifact/c6823520-3fcd-449d-b3d7-3bad17dba1b8

**4 constats CRITIQUES :**
1. `clef API.txt` contient une **vraie clé Anthropic de production** en clair (dupliquée dans `.server_config.json`, dossier synchronisé Synology Drive) → **À RÉVOQUER sur console.anthropic.com**. Aggravé par le fait que des sous-agents de l'audit ont imprimé des fragments partiels dans leurs transcripts.
2. `logx_http.py:2444` — `_NEVER_SERVE = {'clef api.txt'}` ne bloque QUE ce nom ; `_resolve()` sert `.server_config.json`/`.auth_token`/`config.json` sans auth. Serveur sur 0.0.0.0 → `GET /.server_config.json` livre secrets + `GET /.auth_token` annule toute la protection token. Fix : liste blanche d'extensions + bloquer `.*` et fichiers de config.
3. `logx_storage.py:199` — `load_log_from_disk()` avale toute exception et laisse `shared_log` vide ; si logx.db est verrouillé au démarrage (antivirus/Synology), le 1er QSO saisi déclenche DELETE+réécriture → **perte totale du log**. Fix : drapeau `load_failed` interdisant l'écriture destructive + backup avant DELETE.
4. `logx_cloudsync.py:115` — la fusion dépend de la dédup de `add_qso_to_log`, or celle-ci est sautée si `usage_mode='simple'` (commit 3e001b5) → duplication géométrique du log à chaque sync en mode simple. Fix : dédup dans `sync_now` indépendamment du mode.

**Motifs systémiques** (voir [[rebrand-logx-ai.md]]) : (A) bind 0.0.0.0 sans auth + do_DELETE sans `_require_auth` + écouteurs UDP WSJT-X/ADIF-net ; (B) XSS généralisé sur données cluster/QRZ/ADIF/IA injectées en innerHTML/onclick alors qu'esc() existe ; (C) persistance fragile (réécriture intégrale à chaque QSO, verrous disjoints) ; (D) connexions CAT/TCI/rigctld/WSJT-X sans purge d'entrée morte ni reprise ; (E) polling + O(n²) permanents côté client + appel IA payant toutes les 10 min 24h/24 (`logx_carte.html:1304`) ; (F) **CI cassée** (`check.yml` appelle `radiocontest_validate.py`/`radiocontest_eval.py` qui n'existent plus post-renommage) + 422 tests pytest jamais exécutés + aucune dépendance épinglée.

Ordre de correction recommandé : révoquer la clé → C (données) → B (XSS) → D (matériel). Détail ligne par ligne dans la sortie complète de l'audit (task w3b8mb417).

## Corrections appliquées (20/07/2026, mêmes session)
24 fichiers modifiés + `concours/requirements.txt` créé. **422 tests pytest passent, validator OK, pages front vérifiées sans SyntaxError.** NON commité (attente de l'utilisateur).
- **Sécurité serveur** : `_resolve` (logx_http.py) bloque désormais les dotfiles (`.server_config.json`/`.auth_token`) + liste noire config/données ; nouvelle route `/config.json` qui retire la section `server` ; `do_DELETE` exige `_require_auth` ; plafond 32 Mo sur le corps POST.
- **Données** : `load_failed` dans logx_storage.py gèle la persistance si la base est illisible au démarrage ; dédup explicite (call+bande+mode+date+heure) dans logx_cloudsync.sync_now indépendante d'usage_mode.
- **Matériel** : purge d'entrée morte (disconnect_persistent) dans cat/tci/amp sur exception ; TCI socket bloquant après handshake + test is_alive ; WSJT-X parsing entièrement try-wrappé + drapeau écouteur sous verrou ; keyer vocal PTT relâchement vérifié+retry+verrou ; injection newline rigctld CW filtrée ; verrou I/O ampli.
- **Correction métier** : bandes WARC 30/17/12 m mappées '10.1'/'18'/'24' (wsjtx+scoring+export) ; worldmap ISO_A3 "-99" ; departments plus de troncature 3→2 chiffres ; qsl sync_lotw détecte l'échec sur `<eoh>` ; prompts locator None + q.get() + `{call}` au lieu de f4gld ; scoring `.format()` try/except.
- **XSS** : escHtml/esc partout (logbook.js band map/showAC/renderLog/callbook, wall/propagation/carte/configuration) + jsCall/jsId pour les args onclick + safeUrl (http/https only) ; validation ADIF côté serveur (logx_import : regex indicatif + _clean_text).
- **Qualité** : CI (check.yml) pointe sur logx_* + lance pytest ; requirements.txt épinglé ; SSL fallback CERT_NONE supprimé (logx_utils).
Reste surtout des constats moyens/bas non traités (perf : polling/O(n²) côté client, caches ; bind 0.0.0.0 laissé par défaut car multi-op WiFi assumé — l'exposition réelle des secrets/DELETE est corrigée).

## Suite (21/07/2026) : VÉRIFIER portable + lot performance
Toujours NON commité. 425 tests pytest (+ nouveau test_validator.py). Syntaxe front validée par esprima (portage ES2019 : neutraliser `?.`/`??`/`catch{` avant parse — ne PAS conclure à un bug sur ces features).
- **Bug utilisateur VÉRIFIER** : `logx_validator.CALL_RE` n'acceptait qu'un suffixe portable (`F4GLD/P`), pas un préfixe (`EA/F4GLD` = F4GLD depuis l'Espagne) → signalé « busted call ». Remplacé par `_plausible_call()` (préfixe de lieu + suffixe). Lookup DXCC passe désormais l'indicatif COMPLET (`dxcc.lookup(call)`, pas `base`) → bon pays d'émission. Chaque constat porte l'`id` du QSO → boutons **Corriger** (fixFromValidation) / **Supprimer** (delFromValidation) dans la modale VÉRIFIER (showValidation, logx_logbook.js).
- **Performance** : détection doublons client O(n²)→O(n) (renderLog Maps dupCounts/posOf ; updateStats+exportEDI via helper `countDupes`) ; cache mémoire `dxcc.lookup` (vidé au reload cty.dat) ; cache mtime `logx_departments._load_calldb` réutilisé par `/calldb/lookup` ; polling matériel adaptatif (`adaptivePoll` rig/amp/wsjtx : 3-4 s si actif, 20 s si absent) ; veille IA carte.html suspendue après 30 min d'onglet masqué (économie ~144 appels IA/jour).
- Outil réutilisable : `scratchpad/jscheck.py` (esprima + neutralisation ES2020) pour valider la syntaxe JS/HTML sans navigateur — utile quand le classifieur navigate est en panne.

## PÉRIMÈTRE RÉEL de la clé API, vérifié le 30/07/2026 (ne pas refaire l'enquête)
Question de l'utilisateur : « la clef anthropique est en local aujourd'hui plus sur le github c'est bien ca ? » — **oui, et ça n'a JAMAIS été sur GitHub.** Méthode : balayage des **1472 blobs** via `git cat-file --batch-all-objects` (couvre les objets qu'aucune branche ne référence plus, contrairement à `git log -S`). Aucune forme longue `sk-ant-…{60,}` dans un seul objet ; seuls les placeholders `sk-ant-` / `sk-ant-api03-` existent, dans 3 fichiers suivis (`concours/check.bat`, `concours/logx_configuration.html`, `docs/GUIDE_UTILISATEUR.md`).

PIÈGE de méthode, qui m'a fait annoncer « absent » à tort : les fichiers sont dans **`concours/`**, pas à la racine — `concours/clef API.txt` et `concours/.server_config.json`. Chemins exacts obligatoires pour `git ls-files` / `check-ignore`. Les deux sont gitignorés aujourd'hui, présents sur disque, et contiennent **DEUX clés différentes** (préfixes `sk-ant-api03-D…` et `…-M…`, 108 car. chacune) — donc une possiblement périmée.

Le vecteur d'exposition n'était donc pas git mais le **service de fichiers statiques sur le LAN**, et il est fermé : `_NEVER_SERVE` + refus de tout segment commençant par `.` + `_interdit()` appliqué au chemin **réellement résolu** (`realpath`), parce que tester `basename` avant normalisation laissait passer `/.auth_token/` et `/x/../.auth_token/` (basename vide). Voir [[contrainte-expedition-15-jours-continu]] : c'est ce garde-fou qui compte pour 360 h de serveur exposé.
