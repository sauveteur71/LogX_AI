---
name: inventaire-ev7-3e-2026-08-09
description: "EV-7 : 3e inventaire Workflow complet (21 candidats évalués) après épuisement de la liste FAIBLE du 2e inventaire — 2 candidats FAIBLE, 5 MOYEN avec précaution précise documentée, 14 ÉLEVÉ (dont un bloc complet 894-3538 exclu en masse comme chemin critique)"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T03:45:43.793Z
---

3e inventaire Workflow de la campagne (le 1er est
[[inventaire-ev7-16e-candidat-2026-08-08]], le 2e
[[inventaire-ev7-23e-2026-08-09]]), lancé après épuisement des 5 candidats
du 2e inventaire (2 rejetés après coup — voir
[[chantier-ev7-rejet-selecteurs-2026-08-09]] pour le 2e rejet — 3 extraits
et fusionnés). `logx_logbook.js` fait ~4513 lignes. 21 candidats évalués,
~2.34M tokens, 416 appels d'outils, ~18 min.

**Consigne explicite ajoutée à cet inventaire suite aux 2 rejets
précédents** : chaque évaluateur devait croiser TOUT site d'appel externe
en corps de fonction avec la liste des fonctions du chemin critique déjà
confirmées (setupDone, clearForm, onCallInput, submitQSO, bearing,
cardinalDir, updateBandRecap, renderLog, updateStats, prefillSetupFromConfig,
fetchLog, calcPoints/calcDist, etc.) — pas seulement vérifier « corps de
fonction vs top-level ». Résultat : nettement plus de candidats classés
ÉLEVÉ que lors des 2 premiers inventaires (14/21), preuve que la consigne a
été appliquée sérieusement plutôt que de reproduire l'erreur du 2e
inventaire.

## Ordre d'extraction recommandé

1. **TX audio générique RTTY/SSTV** (`txAudioPtt`), lignes 4159-4201
   (43L) → `logx_tx_audio.js`. **Le plus sûr des 3 inventaires cumulés** :
   fonction unique, aucun lien même indirect avec le chemin critique. Ses
   2 seuls appelants (`rttyEnvoyerTexte()` dans logx_rtty_panel.js,
   `sstvEnvoyerImage()` dans logx_sstv_panel.js) sont DÉJÀ des fichiers
   optionnels — optionnel→optionnel. 1 seul fichier de test à corriger
   (JS_EXTRAITS_EV7).
2. **BAND MAP S&P** (`bandmapNoter`/`bandmapSaut`), lignes 984-1034
   (51L) → `logx_bandmap_sp.js`. Toujours 0 dépendance chemin critique
   (seuls appelants : un onclick HTML + le listener clavier de
   logx_theme_shortcuts.js, déjà extrait). ⚠️ **Périmètre exact 984-1034,
   NE PAS étendre à 959-982** (section voisine `_BM_PCOL`/`_BM_CSSVAR`/
   `_BM_RANGE` utilisée par `bandFromFreq()`, chemin critique). Déplacer
   `let _bmSpots = []` (L988) avec le bloc. 4 fichiers de test à corriger
   dont `test_bandmap_sp.py` (extraction par comptage d'accolades) + le
   commentaire de tête de logx_theme_shortcuts.js à mettre à jour.

## MOYEN (précaution précise par candidat, extractibles avec soin)

- **SOAPBOX PAR BANDE** (33L) : `logx_export_edi.js` appelle déjà
  `getSoapbox()` en corps de `exportEDI()` — ajouter le nouveau chemin à
  `_real_source()` de `test_export_edi_num_sent.py`.
- **DÉCODEUR CW #2** (118L) : chaîne non gardée `setupDone/pickMode →
  updateKeyerPanels → loadAudioInputDevices/loadAudioOutputDevices`, mais
  protégée par `if(rtty)` (motif déjà accepté pour `renderRttyMacroBtns`,
  déjà extrait). MAJ `test_audio_recorder_client.py` ET
  `test_cw_panel_consolidation.py` ; vérifier en navigateur réel le mode
  RTTY après extraction (seule branche jamais exercée par pytest).
- **BANDSCOPE + WATERFALL** (108L) : dépendance à 2 niveaux depuis
  `pickBand()`/`onFreqInput()` via `refreshBandMap()`, atténuée par un
  try/catch déjà en place. ⚠️ Périmètre exact **1245-1352** (pas 1362 —
  L1353-1354 appellent `refreshBandMap` et restent dans le cœur) ; ne pas
  toucher le try/catch englobant (L1143-1242).
- **MACROS F1-F8** (149L) : découpe **non contiguë à 2 niveaux** — laisser
  en place les blocs i18n (L3707-3745) et `adaptivePoll()` (L3770-3782)
  intercalés. Extraire uniquement DEFAULT_MACROS/getMacros/saveMacros/
  expandMacro/renderMacroPanel + copyMacro + editMacro. MAJ 3 en-têtes de
  fichiers déjà extraits + `test_macro_cw_serie_bande.py`.
- **FILTRE D'AFFICHAGE DES SPOTS** (208L) : `setInterval`/`setTimeout`
  top-level (L1353-1354, HORS du bloc) référencent `refreshBandMap` qu'on
  déplacerait — sûr en page réelle (ordre `<script>` respecté) mais impose
  d'ajouter le fichier à ~15 tests hôte-entier. `test_filtre_spots.py`
  (extraction par regex `_SF_CONTINENTS`/`basculerContinent`) à rediriger.

## ÉLEVÉ (14 candidats, une phrase chacun)

- **FORMATS D'ÉCHANGE** (`applyExchangeFormat`/`currentExchange`) :
  `setupDone`, `submitQSO` ET `clearForm` en dépendent tous trois pour le
  numéro envoyé/reçu.
- **MODE D'UTILISATION + Menu DÉBUT/FIN** : `applyUsageModeToLogbook`
  appelée en tête de `prefillSetupFromConfig` ; `bandeauxRythmeMasques`
  par les 3 fonctions de rendu des stats — double dépendance DÉJÀ
  documentée par un commentaire du bloc lui-même.
- **ACTIVATION POTA/SOTA/...+ HORAIRES** : appel top-level fragile vers
  `nextRPHWeekendUTC` + 2 appels directs depuis `setupDone`/`submitQSO`.
- **ENREGISTREUR AUDIO PAR QSO** : `captureQsoAudioClip` sur les 3 seuls
  chemins de succès de `submitQSO()`.
- **PANNEAUX SELON LE MODE / SO2R** : `updateKeyerPanels` appelée par
  `pickMode()` ET `setupDone()` via `renderModeButtons`.
- **CLOCK + COUNTDOWN** : appel top-level `nextRPHWeekendUTC` — risque de
  TDZ bloquant `contestEndUTC` pour toute la session.
- **CLASSEMENT OPÉRATEURS** (`updateOpStats`) : appelée sans garde en fin
  de `updateStats()` (chaque QSO).
- **GRAPHE QSO/HEURE** (`drawHourChart`) : seul appelant `updateStats()`,
  sans garde — même schéma que `updateOpStats`.
- **i18n (trT/trF/notify) + adaptivePoll** : `notify`/`trF` 6× en corps de
  `submitQSO`, `adaptivePoll` réutilisée par `pollChat` — reproduirait la
  régression déjà vécue en production ([[chantier-fix-adaptivepoll-domcontentloaded-2e-2026-08-09]]).
- **CHAT MULTI-OPÉRATEUR** : `startChat()` en corps direct de `setupDone()`.
- **VUE PARTNER** : `broadcastTyping()` par `onCallInput()` ET
  `clearForm()` — même schéma que le candidat n5 déjà rejeté.
- **ALERTE DOUBLE-BANDE + ON4KST + RACCOURCI** : `crossBandAlert` à chaque
  frappe dans `onCallInput()`.
- **BROADCAST CHANNEL** : `bcBroadcast` 3× dans le `try{}` de `submitQSO()`
  + listener `DOMContentLoaded` déclencheur du bootstrap de toute la page —
  le pire cas, la page ne démarrerait plus du tout.
- **[EXCLU EN BLOC] cartographie du chemin critique** (lignes 894-3538,
  34 fonctions interdépendantes) : à ne plus jamais reproposer, même en
  sous-blocs.

## Suite

Le 27e incrément cible le candidat n°1 (TX audio générique, `txAudioPtt`,
43 lignes). Comme toujours, relocaliser par grep de fonction à chaque
incrément — les numéros de ligne seront périmés dès le 1er incrément
suivant.
