# Plan — Activité « LOG activation portable » (A3) v1

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development ou executing-plans. Steps en cases à cocher.

**Goal:** Faire de l'activité d'activation portable (POTA/SOTA/XOTA) une activité de premier plan qui pré-câble bandes, affichage et accès au socle existant — carnet unique, sans nouveau backend.

**Architecture:** Réutilise le patron « activité » de LOG V/UHF. L'entrée existe déjà sous l'id `iota_pota` (accueil + preset statusbar). v1 comble les manques : bandes portables par défaut, label élargi à tout le XOTA, et (increments 2-3, après confirmation F4GLD) réconciliation rôle↔activité + cockpit aiguilleur.

**Tech Stack:** JS vanilla (front), tests V8 py_mini_racer, HTML statique. Aucun Python.

**Spec:** `docs/superpowers/specs/2026-09-09-activite-activation-portable-design.md`

## Global Constraints
- Carnet UNIQUE : `logx_activity` n'est jamais un filtre serveur, juste une VUE client (repli d'affichage). Copié du patron `vuhf`.
- Masquer ≠ bloquer : tout reste accessible en changeant d'activité / via les toggles CONFIG.
- Ne PAS renommer l'id `iota_pota` (clé établie dans accueil + statusbar) — n'élargir que le LABEL/hint visibles.
- Aucune fonction TX touchée. Aucun merge dans `main` avant revue visuelle F4GLD.
- Tests : témoin par mutation obligatoire (retirer le correctif → le test rougit), empreinte md5 contrôlée après restauration.

---

## Increment 1 — bandes portables par défaut + label élargi (SÛR, confirmé)

### Task 1 : bandes portables par défaut pour l'activité activation

**Files:**
- Modify: `concours/logx_logbook.js` (~1513-1531, zone `_activiteEstVuhf`/`renderBandButtons`)
- Test: `concours/tests/test_logbook_band_picker_xota.py` (create)

**Interfaces:**
- Produces : `_activiteEstXota()` → bool (vrai ssi `localStorage.logx_activity==='iota_pota'`) ; constante `XOTA_ACTIVITY_DEFAULT_BANDS`.
- Consumes : `renderBandButtons(contest)`, `_bandsForContest`, `ALL_BANDS` (existants).

- [ ] **Step 1 — test V8 qui échoue** : charger la logique de repli et vérifier que, `logx_activity='iota_pota'` et aucun concours, les bandes proposées = `XOTA_ACTIVITY_DEFAULT_BANDS` (7/14/21/28/50/144/432), pas ALL_BANDS. (Modèle : `test_logbook_band_picker_vuhf.py`.)
- [ ] **Step 2 — lancer, vérifier l'échec** (`_activiteEstXota` non défini).
- [ ] **Step 3 — implémenter** : ajouter après `VUHF_ACTIVITY_DEFAULT_BANDS` :
  ```js
  function _activiteEstXota(){
    try{ return localStorage.getItem('logx_activity') === 'iota_pota'; }catch(e){ return false; }
  }
  // Activation portable (POTA/SOTA/WWFF/châteaux…) hors concours : bandes déca
  // SSB/CW courantes + V/UHF portable, plutôt que ALL_BANDS. Reste filtrable par
  // les toggles CONFIG comme les autres.
  const XOTA_ACTIVITY_DEFAULT_BANDS = ['7','14','21','28','50','144','432'];
  ```
  et étendre le repli dans `renderBandButtons` :
  ```js
  const contestBands = _bandsForContest(contest)
    || (_activiteEstVuhf() ? VUHF_ACTIVITY_DEFAULT_BANDS
        : _activiteEstXota() ? XOTA_ACTIVITY_DEFAULT_BANDS
        : ALL_BANDS);
  ```
- [ ] **Step 4 — lancer, vérifier le vert.**
- [ ] **Step 5 — témoin par mutation** : casser le repli (forcer ALL_BANDS) → test rougit ; restaurer ; md5 identique.
- [ ] **Step 6 — commit** `feat(xota): bandes portables par défaut pour l'activité activation`.

### Task 2 : élargir le label de l'activité à tout le XOTA

**Files:**
- Modify: `concours/logx_accueil.js:33` (entrée ACTIVITIES `iota_pota`)
- Modify: `concours/logx_statusbar.js:1793` (`ACTIVITY_LABELS.iota_pota`)
- Test: `concours/tests/test_accueil_activite_xota.py` (create) — statique

- [ ] **Step 1 — test qui échoue** : l'entrée `iota_pota` de `ACTIVITIES` porte le label « LOG activation portable » et un hint mentionnant SOTA + châteaux (pas seulement IOTA/POTA).
- [ ] **Step 2 — échec.**
- [ ] **Step 3 — implémenter** : `label:'LOG activation portable', hint:'POTA · SOTA · WWFF · châteaux…'` (accueil) ; `iota_pota:'LOG activation portable'` (statusbar labels). Icône inchangée.
- [ ] **Step 4 — vert.**
- [ ] **Step 5 — mutation** : remettre l'ancien label → rougit ; restaurer.
- [ ] **Step 6 — commit** `feat(xota): élargit le label de l'activité activation portable`.

### Task 3 : non-régression + push branche

- [ ] Lancer la famille : `test_accueil*`, `test_activation*`, `test_logbook_band_picker*`, `test_notify_dynamic_i18n` (charge le logbook). Tout vert.
- [ ] Push branche `feat/a3-activation-v1`. **Ne PAS merger** — attendre la revue visuelle F4GLD.

---

## Increments 2-3 — EN ATTENTE des réponses D1/D2 de F4GLD (ne pas construire à l'aveugle)

- **Inc. 2 — réconciliation rôle↔activité** : intégrer le sous-choix chasse/portable/mixte AU flux de l'activité (aujourd'hui tuiles séparées `_renderXotaRoleAccueil`). Dépend de D1 (activité chapeau + sous-choix, ou 3 cartes distinctes ?).
- **Inc. 3 — cockpit aiguilleur** : réf du jour (lookup) + boutons (logbook activation / CHASSE / carte de sortie). Dépend de D2 (router vers CHASSE existante vs fusion).

Ces increments réutilisent `logx_xota_role.js`, `logx_activation_ui.js`, `logx_ref_info.js`, `logx_xota_carte.js`, `logx_chasse.html` — déjà présents. À planifier en détail une fois D1/D2 tranchés.

## Self-review
- Couverture spec : v1 couvre D3 (bandes) + une partie de D1 (label) ; D1(structure)/D2/D4 explicitement différés (increments 2-3, gated). OK.
- Placeholders : aucun (code réel donné). OK.
- Cohérence de types : `_activiteEstXota`/`XOTA_ACTIVITY_DEFAULT_BANDS` cohérents entre tasks. OK.
