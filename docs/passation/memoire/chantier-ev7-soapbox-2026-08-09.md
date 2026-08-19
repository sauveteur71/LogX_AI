---
name: chantier-ev7-soapbox-2026-08-09
description: "EV-7 29e incrément : extraction SOAPBOX PAR BANDE vers logx_soapbox.js (09/08, merge 26f777b) — 0 constat, dernier candidat MOYEN du 3e inventaire attaqué"
metadata: 
  node_type: memory
  type: project
  modified: 2026-08-09T05:16:42.493Z
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
---

29e incrément de la campagne, candidat MOYEN du 3e inventaire
([[inventaire-ev7-3e-2026-08-09]]). Extraction de 32 lignes de
`concours/logx_logbook.js` (3564-3595) vers `concours/logx_soapbox.js`
(nouveau) : `SOAPBOX_BANDS`, `toggleSoapbox()`, `saveSoapbox()`,
`loadSoapbox()`, `getSoapbox(band)`.

Dépendances croisées vérifiées sûres : ces fonctions sont autonomes
(lisent/écrivent leur propre état local + localStorage), aucun appel
sortant vers le cœur ni appel entrant depuis une fonction du chemin
critique confirmé (setupDone/clearForm/prefillSetupFromConfig).

2 fichiers de test touchés : `test_export_edi_num_sent.py` (ajout du
chemin `logx_soapbox.js` dans `_real_source()`, motif déjà répété 4 fois
ce chantier) et `test_logbook_menu_debut_fin.py` (ajout à
`JS_EXTRAITS_EV7`). Suite pytest complète verte du premier coup.
Vérification navigateur : `toggleSoapbox()`/`saveSoapbox()` appelés
réellement, `getSoapbox()` relu correctement après un `loadSoapbox()`.
Revue adversariale (extraction-fidelity + dependency-integrity) : 0
constat, chaque dimension vérifiée indépendamment.

`logx_logbook.js` : ~4396 → ~4364 lignes (35 lignes nettes retirées, y
compris l'en-tête de section).

Suite : dernier candidat MOYEN du 3e inventaire consommé. Passage au 30e
incrément — DÉCODEUR CW #2 (`logx_cw_panel2_audio.js`), puis BANDSCOPE+
WATERFALL (31e), MACROS F1-F8 (32e), FILTRE SPOTS+refreshBandMap (33e) —
avant de lancer un 4e inventaire Workflow complet.
