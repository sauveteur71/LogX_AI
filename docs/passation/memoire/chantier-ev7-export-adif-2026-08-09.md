---
name: chantier-ev7-export-adif-2026-08-09
description: "EV-7 23e incrément : extraction Export ADIF + CSV vers logx_export_adif.js (09/08, merge 7fdf8c8) — candidat n°1 de l'inventaire rejeté après lecture de son propre commentaire d'exclusion"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T01:16:40.220Z
---

23e incrément de la campagne [[inventaire-ev7-23e-2026-08-09]]. Extraction de
112 lignes de `concours/logx_logbook.js` vers `concours/logx_export_adif.js`
(nouveau) : `ADIF_BAND`/`ADIF_BAND_OFFICIELLES`, `adifBandLabel()`,
`adifField()`, `ADIF_STD_TAGS`, `buildAdifText()`, `downloadAdifBlob()`,
`exportADIF()`, `exportCSV()`. `logx_logbook.js` : ~5033 → ~4922 lignes.

**Détour avant l'extraction** : le candidat n°1 classé "le plus sûr" par
l'inventaire (`matchesAdvancedFilter`) a été REJETÉ sans être tenté — son
propre commentaire d'en-tête dans le code documentait une décision
adversariale ANTÉRIEURE de le garder dans le cœur pour ne pas faire
dépendre `renderLog()` (chemin critique) d'un fichier optionnel. Confirme
la leçon déjà notée dans l'inventaire : toujours lire le commentaire du
bloc AVANT de faire confiance à un verdict FAIBLE purement technique/
statistique. Extraction faite sur le candidat n°2 à la place.

Aucun piège des 3 classes connues ([[chantier-ev7-theme-shortcuts-2026-08-09]])
rencontré cette fois : grep exhaustif AVANT extraction confirmait 0 appel
top-level dépendant du bloc, et le seul usage externe
(`logx_filter_builder.js` → `downloadAdifBlob(buildAdifText(...))`) migre
les deux symboles ENSEMBLE, donc pas de dépendance croisée introduite.
1 seul fichier de test génuinement affecté (`test_export_adif_client_bande.py`,
motif JS_EXTRAITS_EV7 déjà éprouvé). Suite pytest complète VERTE du premier
coup — aucun cycle correctif nécessaire, une première dans cette campagne.

Revue adversariale (2 dimensions, prompts durcis) : 0 constat brut, 0
confirmé — 2e fois consécutive après [[chantier-ev7-theme-shortcuts-2026-08-09]]
qu'une extraction ressort totalement propre, signe que la méthodologie
(grep exhaustif + suite complète + revue) converge bien avant le commit.

Suite : [[inventaire-ev7-23e-2026-08-09]] candidat n°3 (Édition QSO,
`editQSO`/`saveEdit`, 206 lignes) devient le 24e incrément.
