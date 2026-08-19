---
name: chantier-ev7-edit-qso-2026-08-09
description: "EV-7 24e incrément : extraction Édition QSO vers logx_edit_qso.js (09/08, merge 34e734a) — 3 dépendances croisées documentées (dup_finder/theme_shortcuts/verif_panel), 0 constat revue, découverte au passage d'une régression adaptivePoll sans rapport"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T02:19:54.030Z
---

24e incrément de la campagne [[inventaire-ev7-23e-2026-08-09]] (candidat
n°3). Extraction de 206 lignes de `concours/logx_logbook.js` vers
`concours/logx_edit_qso.js` (nouveau) : `editQSO()`, champs ADIF
personnalisés (`editExtraFields`/`renderEditExtraFields`/
`addEditExtraField`/`removeEditExtraField`/`updateEditExtraField`),
`updateEditDistInfo()`, `closeEdit()`, `saveEdit()`, `deleteQSOSilent()`/
`deleteQSO()`, `undoLastQSO()`. `logx_logbook.js` : ~4924 → ~4722 lignes.

Aucun piège des 3 classes connues cette fois, mais **3 dépendances
croisées EN CORPS DE FONCTION** trouvées et documentées dans l'en-tête du
nouveau fichier (sûres dans le modèle à portée globale partagée, vérifiées
une à une pour confirmer qu'aucun test V8 existant ne les exerce sans
charger `logx_edit_qso.js`) :
- `logx_dup_finder.js` appelle `deleteQSOSilent()` (suppression en lot) ;
- `logx_theme_shortcuts.js` appelle `undoLastQSO()` (raccourci Ctrl+Z,
  gestionnaire keydown global — `test_macros_au_clavier.py` ne teste QUE
  le bloc F1-F8, jamais Ctrl+Z, donc pas d'impact) ;
- `logx_verif_panel.js` appelle `editQSO()` depuis `fixFromValidation()`
  (bouton "Corriger" sur un constat IA — `test_peer_version_xss.py`
  exerce `showChecklist()` mais jamais ce chemin, donc pas d'impact).

1 seul fichier de test dédié affecté : `test_edit_qso_mode_hors_concours.py`
(appelle `editQSO()` directement en V8), corrigé en ajoutant
`EDIT_QSO_JS_PATH` à sa fixture `moteur()`. Suite pytest complète : 1
échec isolé au 1er passage (`test_update_integrity.py::
test_peer_annoncant_le_bon_asset_toujours_accepte`, test réseau pair-à-
pair timing-sensible SANS AUCUN rapport avec l'extraction) — confirmé
flake par relance isolée (verte) puis relance complète (100% verte).

Revue adversariale (2 dimensions) : 0 constat — 3e fois consécutive après
[[chantier-ev7-theme-shortcuts-2026-08-09]] et
[[chantier-ev7-export-adif-2026-08-09]].

**Découverte importante au passage** (vérification navigateur, sans
rapport avec cet incrément) : `logx_hardware_cat.js` reproduit à 100%
`ReferenceError: adaptivePoll is not defined` à chaque chargement de
`logx_logbook.html`. Un correctif identique existe déjà (commit `dc194d6`,
`DOMContentLoaded` au lieu de `setTimeout(fn,0)`) mais sur une branche
jamais fusionnée (`claude/loving-noyce-c5ded3`) — perdu quand
`logx_hardware_cat.js` a été régénéré par l'extraction EV-7 phase 2
(`e2cec50`). Traité comme correctif séparé, pas mélangé à cet incrément.

Suite : candidat n°4 (Exports EDI + Cabrillo, `exportEDI`/`exportCabrillo`,
212 lignes) devient le 25e incrément.
