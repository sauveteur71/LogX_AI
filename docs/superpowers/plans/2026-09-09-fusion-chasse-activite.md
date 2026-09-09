# Plan — Fusion TOTALE de CHASSE dans l'activité « activation portable » (A3 / D2)

> **For agentic workers:** REQUIRED SUB-SKILL: subagent-driven-development ou executing-plans. Steps en cases à cocher.

**Goal:** Fusionner le contenu de `logx_chasse.html` (spots POTA/SOTA/WWFF/WCA, DXpéditions, need-list cluster, QSY/rotor, FT8, fiche, objectifs) DANS l'activité activation portable (accueil + cockpit), puis rediriger la page autonome. Décision F4GLD D2 = fusion totale.

**Architecture:** CHASSE reste INTACTE et servie jusqu'au tout dernier incrément ; on construit la fusion à côté, additivement, en réutilisant le cockpit d'accueil (qui lit déjà `/data/spots_ranked`, la même source). Le serveur (endpoints + `logx_chasse_priorite.py` + annotation crédit) n'est JAMAIS touché.

**Tech Stack:** JS vanilla, tests V8 py_mini_racer, HTML statique. Aucun Python.

**Spec:** `docs/superpowers/specs/2026-09-09-activite-activation-portable-design.md` (D2)

## Global Constraints
- CHASSE (`logx_chasse.html`) reste la référence vivante jusqu'à l'incr. 5 ; ses tests garde-fous (`test_page_chasse_split`, `test_chasse_*`) doivent rester VERTS à chaque incrément 1→4.
- Carnet unique, masquer ≠ bloquer, aucune émission touchée (spots = annonces).
- Chaque incrément : test + témoin par mutation + md5, sans merge dans main avant revue visuelle F4GLD.
- Ne pas toucher le serveur (endpoints/priorité/crédit) — tout existe déjà.

## Endpoints réutilisés (tous existants)
`/data/spots_ranked`, `/data/pota_spots`, `/data/sota_spots`, `/data/wwff_spots`,
`/data/wca_planned`, `/data/dxpeditions_active`, `/data/operator_goals` (GET+POST),
`/rig/state`, `/rig/qsy`, `/rotor/state`, `/rotor/point`, `/wsjtx/strategy`(+state),
`/data/voacap`, `/calldb/lookup/`, `/awards/prochaines_cibles`.

---

## Incr. 1 — Module partagé `logx_chasse_panneaux.js` (ADDITIF, sans toucher CHASSE)
Extraire les fonctions PURES de rendu de spot (aujourd'hui inline dans
logx_chasse.html) dans un nouveau module `window.LogxChassePanneaux`, testées en
V8 en isolation. **CHASSE n'est PAS modifiée à cette étape** (zéro risque).
- Fonctions : `esc`, `splitBadge`, `creditBadge` (+ constantes `CREDIT_LABELS`,
  `PRIO_COLORS`) — retournent du HTML pur à partir d'un spot.
- Test : `test_chasse_panneaux_module.py` (V8) — `creditBadge(spot)` produit le
  même badge/score/classe que l'inline (comparer aux assertions de
  `test_chasse_affiche_credit`).
- Garde-fou : `test_page_chasse_split` + `test_chasse_affiche_credit` restent verts
  (CHASSE inchangée).

## Incr. 2 — Câbler CHASSE sur le module (refactor invisible)
`logx_chasse.html` charge `logx_chasse_panneaux.js` et remplace ses fonctions
inline par des façades qui délèguent au module (mêmes noms, même rendu). Ajuster
`test_page_chasse_split` pour accepter le `<script src>` externe si besoin.
- Test : CHASSE rend un spot identique (V8 avant/après) ; page inchangée à l'écran.

## Incr. 3 — Need-list complète dans le cockpit d'accueil
Étendre `logx_accueil_cockpit.js`/`_grille()` : sous le cockpit, un bloc « Cibles
en direct » qui rend la need-list COMPLÈTE via le module (incr.1), alimenté par le
`/data/spots_ranked` **déjà chargé** par `LogxCockpit.charger()` (v[0]) — zéro
endpoint neuf. Nouveaux conteneurs `#ckNeedList` (+ filtres optionnels).
- Test : `test_accueil_needlist_js.py` (V8) — le cockpit affiche la need-list.

## Incr. 4 — Panneaux activation (POTA/SOTA/WWFF/WCA/NG3K) dans l'activité, gatés rôle
Sur le flux « activation portable » (après la carte chapeau → rôle), monter les
panneaux `#potaList…#dxList` et brancher les loaders (paramétrés par ids). Gate
par `LogxXotaRole.roleConfig(role)` : `portable` masque la chasse, `chasse`/`mixte`
la montrent. Ajouter sur l'accueil les scripts manquants nécessaires (`logx_i18n.js`).
Porter aussi QSY/rotor/FT8/fiche/objectifs (endpoints existants).
- Test : câblage loaders + respect du rôle ; objectifs (clés === `logx_operator_goals.CLES`).

## Incr. 5 — Rediriger l'ancienne page + nettoyage (SEUL incrément destructif)
Après parité prouvée : (a) `logx_chasse.html` → redirection vers l'activité ;
(b) mettre à jour les **13 navs** (`ORDRE_NAV_ATTENDU`) ; (c) repointer les href
de repli (`logx_bandeaux_defs.js`, `logx_search.py`, `logx_statusbar.js`, `logx_i18n.js`).
- Test : réécrire `test_page_chasse_split.py` pour la nouvelle destination + test de
  redirection ; les tests serveur crédit restent inchangés (indépendants de la page).

## Ordre & sûreté
Incr. 1→4 purement ADDITIFS (CHASSE = référence vivante intacte). Incr. 5 seul
destructif, uniquement après parité. Serveur jamais touché.

## Self-review
- Couverture D2 (fusion totale) : incr. 3-4 embarquent tout le contenu CHASSE ;
  incr. 5 retire la page autonome. OK.
- Garde-fous : tests CHASSE verts jusqu'à l'incr. 5. OK.
- Risque : concentré sur incr. 2 (façades) et 5 (nav 13 pages) — traités en dernier,
  chacun avec ses tests.
