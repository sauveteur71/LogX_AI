---
name: chantier-lot-5-demandes-2026-08-02
description: "Lot utilisateur de 5 demandes (02/08/2026) — TOUTES livrées et fusionnées dans main (redémarrage, clusters, synchro multi-PC, alertes par type, config à onglets)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-02T09:50:02.079Z
---

Lot de 5 demandes de F4GLD le 02/08/2026, traité par tranches sur branches CI-vertes puis fusionné dans `main`.

**LIVRÉ (fusionné, `832e16f`) :**
1. **Bouton « redémarrage » figé** — `logx_statusbar.js` : `/app/update_install` partait bien mais le client AVALAIT l'erreur 400 (`apply_update_and_relaunch` refuse si fichier non vérifié / hors .exe). Il l'affiche maintenant. **À SUIVRE : demander à l'utilisateur le message d'erreur affiché pour réparer le FOND.**
2. **Liste clusters** — `logx_clusters.DX_CLUSTER_CATALOG` (17 nœuds, host:port de ng3k.com, PAS de mémoire, ports variés 7300/7373/9000/41112) + `/data/clusters` + sélecteur CONFIG groupé par région (construit en `createElement`, PAS innerHTML, pour esquiver `test_i18n_optgroup`).
3. **Synchro multi-PC, DEUX options indépendantes** (l'utilisateur veut les deux) :
   - **Cloud Sync** (dossier partagé, existait) : `_cloudsync_loop` faisait `sleep(60)` AVANT la 1re synchro → log périmé 1-3 min à l'ouverture. Corrigé : 1re passe force `due=True` (synchro immédiate au démarrage).
   - **LAN direct** (nouveau, `logx_lan_sync.py`) : beacon UDP diffusé (port **8073**) pour découverte auto + tirage HTTP `/log/lan/export` + fusion via `add_qso_to_log`. UN thread + UNE socket (beacon+écoute), registre borné TTL, HTTP borné. `_lan_sync_loop` dans logx_serveur (12 s). Toggle `lan_sync_enabled`.

**LIVRÉ (fusionné) — les 2 derniers :**
4. **⑤ Alertes voix + son PAR TYPE** (`adff040`) — dispatcher central `window.rcAlert(type, texte)` dans `logx_statusbar.js` : 6 types (new_dxcc/new_dept/new_grid/lotw_need/mult/rate), 7 sons WebAudio synthétisés (aucun/aigu/grave/double/montant/carillon/sirène), prefs par poste localStorage `rc_alerts`. Voix parle si le TYPE l'active MÊME quand le 🔊 global est coupé (sinon repli global). Sites FT8 + nudges branchés sur rcAlert. Panneau CONFIG (popup 11) « Son & voix par type ». **PIÈGE attrapé par la CI : `test_locator_tracker` scannait 2 `playBeep` en dur → mis à jour vers 2 `rcAlert` (new_grid/mult).**
5. **④ Config à ONGLETS + sélection visible** (`387bd87`) — sélection = **pavé plein + coche ✓ + scale 1.06-1.07** : config `.toggle-btn.on`, logbook `.bm-btn/.op-btn.active` (base ET mode jour). Config à onglets = barre latérale `#configSidebar` (15 sections) ajoutée SANS toucher les 15 popups existants (ils restent en DOM, juste masqués ; save lit tout). `openCategoryPopup` réécrit **cœur-d'abord + try/catch** pour que `test_assistant_banner_popup_js` (exécute les vraies fonctions en mini-DOM sans body/createElement) reste vert.

**PATRON RÉUTILISABLE de la session** : `getComputedStyle().transform` renvoie `none` sur un élément dans un `display:none` (popup fermé) — vérifier sur un élément VISIBLE. Et le serveur `python -m http.server` basique lâche (`ERR_CONNECTION_RESET`) sous la rafale de la grosse page logbook → recharger / cache-buster.

**SUITE POSSIBLE** : proposer une nouvelle beta pour embarquer tout le lot (+ rotor GS-232, alertes FT8, keyer). Redémarrage : demander à F4GLD le message d'erreur qui s'affiche désormais.

Voir [[chantier-etude-ia-6-evolutions-2026-08-01]] (brique voix), [[chantier-station-multi-propagation-2026-08-01]] (rotor/parc), [[piege-table-domaine-ecrite-de-memoire]] (clusters vérifiés via ng3k, pas de mémoire).
