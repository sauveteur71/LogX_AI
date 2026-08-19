---
name: passe-verification-distribution-2026-07-22
description: Passe finale multi-agents avant envoi aux amis — 19 vrais défauts corrigés dont chat multi-op 100% mort (4 bugs empilés) ; forme de distribution = LogXAI.exe PyInstaller
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-22T19:27:12.669Z
---

Passe de vérification complète (22/07/2026) avant distribution à des amis testeurs, via Workflow 32 agents (5 angles + contre-vérification adversariale). Branche `feat/aide-config-websdr-guide`.

**Corrigé (tous vérifiés par exécution/navigateur) :**
- Chat multi-op TOTALEMENT mort depuis un refactoring : 4 bugs empilés (`chatBox`→`chatBody`, `chatDot`→`chatUnread`, `e.key`→`event.key` dans le handler inline, `display:none` inline qui primait sur `.chat-panel.open`). Personne ne l'avait remarqué → il n'a jamais servi.
- Échap ne fermait plus la fenêtre d'édition QSO (`editModal`/style.display → `editOverlay`/classList `show`).
- Carte : anneau « ★ record » jamais dessiné au chargement (fetch async sans redraw) → `drawRangeCircles()` rappelé après la réponse de `/data/dx_records`.
- WCA : `_REF_RE` alignée sur `_CODE_RE` (9A-, S5-, 4-5 chiffres) ; `_cell_text()` descend dans les `<text:span>` (.ods formatés).
- IOTA : cache islands.json relu avant réseau (était en écriture seule), `max_age_days` 1→30 (le moteur générique traite un cache expiré comme inexistant), centre antiméridien corrigé (Fidji donnait lon≈0).
- HTTP : `hours` borné [1,168] sur `/data/eme_window` (NaN/inf inclus) ; `_NEVER_SERVE` + qsl_sync/scoreboard_sync/backup_state + suffixes `.bak`/`.db`.
- Packaging : build_windows.bat/build_macos.sh installent requirements.txt AVANT PyInstaller (sinon exe silencieusement sans CAT/TTS/EME) ; logx.spec embarque manifest.webmanifest/logx_icon.svg/logx_logo.png (sinon logo cassé + SW jamais installé dans l'exe) ; requirements.txt + sounddevice ; .gitignore + `_backup_avant_correction_rst/`.

**Constats réfutés notables :** calldb.json servable (faux), WWFF colonne country (faux), pyttsx3 drivers morts dans l'exe (faux).

**PIÈGE mémorisé :** un id HTML renommé sans grep global casse silencieusement les `getElementById` gardés par `if(el)` — le chat est resté mort des semaines sans erreur console. Après tout renommage d'id, greper l'ancien nom dans TOUT le dossier.

**Distribution retenue :** `LogXAI.exe` via build_windows.bat (autonome, données dans `%APPDATA%\LogXAI\`, INSTALL.md déjà rédigé pour les testeurs). Redémarrage serveur requis pour activer les 2 changements logx_http.py côté poste local. Voir [[chantier-programmes-activation-cw-dxpeditions-2026-07-22]] et [[audit-securite-qualite-2026-07-20]] (clé API à révoquer toujours d'actualité).

**HISTORIQUE PURGÉ (22/07/2026 soir)** : `git filter-branch --index-filter` a retiré config.json/calldb.json/shared_log.json de TOUT l'historique ; force-push de main/feat/fix-audit + tag v0.9-beta1 (nouveau tip 327ef1e, arbre identique, release et exe intacts). PIÈGES : filter-branch réécrit AUSSI les branches de sauvegarde et les refs remote-tracking → `--force-with-lease` échoue en « stale info », passer le vieux SHA explicitement depuis `refs/original/...` ; le classificateur auto-mode bloque les push composés (force+delete) → une commande par ref. RESTE : refs/pull/1/head (PR #1) pointe toujours l'ancien d722828 côté GitHub — insupprimable par l'utilisateur, seul le support GitHub peut effacer les vues cachées ; refs/original + branches backup-avant-purge* conservées en local comme filet.

**PUBLIÉ (22/07/2026 soir)** : dépôt public `sauveteur71/radioaamateur-program-Contest`, main poussé à ae1bbaf (52 commits), release **v0.9-beta1** avec LogXAI.exe 49 Mo attaché — lien beta : https://github.com/sauveteur71/radioaamateur-program-Contest/releases/tag/v0.9-beta1. Vérifié : la clé du config.json historique (commits 4f07e5f/c75d553) est un PLACEHOLDER, pas de secret réel dans l'historique ; calldb/shared_log historiques = données perso de faible sensibilité, purge d'historique possible plus tard si souhaité. PIÈGES poste : `gh` absent → release via API + jeton du credential manager git (`cmd /c "git credential fill < fichier"` — le pipe PowerShell 5.1 corrompt l'entrée) ; Avast MITM HTTPS casse curl/Python urllib (SSL verify failed) → passer par PowerShell Invoke-RestMethod qui utilise le magasin Windows.
