---
name: piege-appel-top-level-casse-tests-hote-entier
description: EV-7 — un appel TOP-LEVEL restant dans logx_logbook.js vers un symbole extrait casse TOUS les tests qui évaluent le fichier hôte en entier, pas seulement ceux liés à la fonctionnalité (08/08/2026)
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T22:50:12.924Z
---

Piège découvert au 19e incrément EV-7 ([[chantier-ev7-esm-callbot]]),
généralisation plus large des deux pièges précédents
([[piege-dependance-cachee-fichier-tiers-deja-extrait]] et l'incident
CI du 16e incrément) : **un appel TOP-LEVEL (hors de toute fonction)
laissé dans `logx_logbook.js`, qui dépend d'un symbole désormais défini
dans un fichier extrait par EV-7, casse TOUS les tests qui évaluent le
texte complet de `logx_logbook.js` via V8/py_mini_racer — même ceux qui
n'ont AUCUN rapport fonctionnel avec le bloc extrait.**

Mécanisme précis : la ligne `renderVoiceDynPanel();` (sans être à
l'intérieur d'une fonction) restait dans `logx_logbook.js` juste après
l'emplacement du bloc CALLBOT/ESM retiré. Une fonction top-level referencée
dans le corps d'une AUTRE fonction ne pose problème qu'AU MOMENT DE
L'APPEL (résolution tardive) — mais un appel top-level s'exécute AU PARSE
du fichier, donc dès que `ctx.eval(logx_logbook.js)` tourne dans N'IMPORTE
QUEL test, même un test qui ne teste ni ESM ni CALLBOT. Résultat : 12
fichiers de tests touchés d'un coup (`test_audio_recorder_client.py`,
`test_awards_clublog_realtime_blocked_js.py`,
`test_bandmap_waterfall_band_change.py`, `test_cw_panel_consolidation.py`,
`test_edit_qso_mode_hors_concours.py`, `test_export_adif_client_bande.py`,
`test_export_edi_num_sent.py`, `test_logbook_render_window_reset.py`,
`test_notify_dynamic_i18n.py`, `test_partner_view_closed_panel.py`,
`test_qtc_panel_js.py`, `test_rph_weekend_fallback.py`) — contre 1-2
fichiers pour les pièges précédents de la campagne.

**Pourquoi ce n'est PAS un bug produit** : dans la page réelle, l'ordre
des `<script>` (fichier extrait AVANT `logx_logbook.js`) garantit que le
symbole existe déjà quand l'appel top-level s'exécute — vérifié en
navigateur, `renderVoiceDynPanel()` a bien rendu les boutons dès le
chargement. C'est UNIQUEMENT dans les tests qui chargent `logx_logbook.js`
seul (sans le fichier extrait) que ça casse.

**Réflexe à appliquer pour tout incrément EV-7 futur** : avant de pousser,
grep TOUT le fichier hôte (`logx_logbook.js`) pour un appel top-level au(x)
symbole(s) déplacé(s) — pas seulement leurs usages À L'INTÉRIEUR d'autres
fonctions (déjà couvert par le réflexe du piège précédent). Concrètement :
après extraction, chercher chaque nom de fonction/variable déplacée dans
`logx_logbook.js` et, pour chaque occurrence restante, vérifier si elle
est à l'intérieur d'un bloc `function ... { }` ou à la racine du fichier
— une occurrence à la racine (souvent juste après/avant l'ancien
emplacement du bloc extrait) est le signal. Ne pas se contenter de
corriger APRÈS un échec CI ou un run pytest complet : ce diagnostic doit
se faire AVANT de pousser, car le rayon de casse peut toucher une
douzaine de fichiers sans rapport apparent, ce qui rend le diagnostic
après-coup coûteux (il a fallu lancer la suite pytest complète et
dépouiller 65 cas d'échec pour cartographier les 11-12 fichiers touchés).

**Méthode validée une 2e fois avec succès** ([[chantier-ev7-voice-keyer-2026-08-09]],
20e incrément, 09/08/2026) : le même symptôme est réapparu (un nouvel
appel top-level `voiceRefreshSlots();` juste à côté de
`renderVoiceDynPanel();`), mais cette fois repéré PAR GREP AVANT
d'extraire — la liste des 14 fichiers déjà établie au 19e incrément
(ceux qui évaluent `logx_logbook.js` en entier via V8) a été corrigée
d'emblée, sans qu'aucun nouveau 15e fichier ne se révèle manquant
(confirmé par la revue adversariale, grep exhaustif des 43 fichiers de
tests référençant `logx_logbook.js`). Résultat : suite pytest verte du
premier coup, 0 échec, contre 65 échecs pour découvrir le même piège
après coup au 19e incrément. Le réflexe « grep top-level avant de
pousser » est donc la méthode à appliquer systématiquement, pas un
correctif ponctuel — elle a fait ses preuves deux fois de suite.
