---
name: chantier-ev7-sstv-panel-2026-08-08
description: "EV-7 14e incrément : panneau décodeur/émetteur SSTV extrait vers logx_sstv_panel.js (commit 4e838cd, branche feat/ev7-extract-sstv-panel) — 7 variables d'état 100% privées, 8 fonctions, aucun test à adapter, revue adversariale 0 constat"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T17:33:15.487Z
---

Chantier livré sur la branche `feat/ev7-extract-sstv-panel` (commit de contenu
`4e838cd`), fusion sur `main` à confirmer une fois la CI verte.

## Contexte

Après le 13e incrément ([[chantier-ev7-busted-call-2026-08-08]]), reprise sans
nouvelle demande explicite ("go4" restait la dernière approbation, plus
l'instruction permanente de F4GLD "je m'absente qques heures continu a bosser
sans moi t'arrete pas"). Candidat SSTV réutilisé depuis l'évaluation détaillée
déjà produite lors de l'inventaire du 10e incrément (fichier
`rtty_sstv_eval.txt` du scratchpad de session, extrait du `journal.jsonl` du
Workflow original) plutôt que de relancer un inventaire complet — même motif
que pour busted-call.

## Ce qui a changé

7 variables d'état 100% privées au bloc (`_sstvDecoder`, `_sstvDevicesLoaded`,
`_sstvOutDeviceLoaded`, `_sstvLignesRecues`, `_sstvTxArmed`, `_sstvTxPixels`,
`_sstvModeSelectRempli`) + 8 fonctions (`toggleSstvPanel`,
`toggleSstvDecoder`, `sstvSauverImage`, `sstvEffacerImage`,
`remplirSstvModeSelect`, `sstvOnArmChange`, `sstvChargerImage`,
`sstvEnvoyerImage`) déplacées vers `logx_sstv_panel.js` (200 lignes,
extraites de `logx_logbook.js` L2471-2670). Grep exhaustif confirmé : aucune
de ces variables/fonctions n'est lue/écrite ailleurs dans le fichier.

Dépendances sortantes : uniquement des utilitaires génériques déjà éprouvés
par `logx_cw_panel.js` (`notify`/`trF`/`trT`/`escHtml`/
`loadAudioInputDevices`/`loadAudioOutputDevices`/`txAudioPtt`) + 3 symboles
de `logx_sstvdecoder.js` (`SstvAudioDecoder`/`SSTV_MODES_PAR_NOM`/
`sstvEncodeSamples`, déjà un fichier séparé chargé en L1873 de
`logx_logbook.html`) — tous utilisés uniquement à l'intérieur de corps de
fonction, jamais au niveau top-level (pas de piège d'ordre de `<script>`
comme celui trouvé sur `logx_hardware_cat.js`,
cf. [[chantier-ev7-radio-cat-2026-08-08]]).

Dépendance entrante : `updateKeyerPanels()` (coordinateur CW/RTTY/SSTV/voix,
reste dans `logx_logbook.js`) fait uniquement
`document.getElementById('sstvPanel').style.display=...` — couplage DOM pur,
pas un appel à une fonction du bloc, même traitement déjà réservé à
`cwPanel`.

## Différence notable avec busted-call : aucun test à adapter

Contrairement au 13e incrément, aucun test ne fige le CODE SOURCE de ce bloc
précis. `test_sstv_decodeur.py` ne teste que `logx_sstvdecoder.js` (le
pipeline DSP, déjà séparé, sans rapport). Seule adaptation faite par
convention établie : ajout de `'logx_sstv_panel.js'` à `JS_EXTRAITS_EV7`
dans `tests/test_logbook_menu_debut_fin.py` — précaution de cohérence, pas
un correctif requis (confirmé : `itemsMenuLogbook()` ne référence aucune
fonction SSTV).

Suite ciblée : 95 tests passés (`test_sstv_decodeur.py`,
`test_logbook_menu_debut_fin.py`, `test_search.py`,
`test_config_assistant_search.py`). Suite complète : 8790 passés (x2).

## Vérification navigateur

`toggleSstvPanel()` ouvre/ferme le panneau (état DOM pur, revérifié fermé
après test), `remplirSstvModeSelect()` peuple un `<select>` (pure DOM, pas
de matériel audio/réseau touché). Aucune fonction déclenchant un vrai
décodage micro ou une émission audio n'a été appelée.

## Revue adversariale

2 dimensions (extraction-fidelity, dependency-integrity) : **0 constat**.

## Suite

`logx_logbook.js` : 6507 → 6310 lignes après ce 14e incrément (6930 avant le
10e). Candidat suivant déjà évalué avec le même niveau de détail (même
scratchpad) : **Décodeur RTTY + émission RTTY** (L2423-2600 approx, risque
FAIBLE), nécessitant cette fois l'adaptation de `tests/test_rtty_decodeur.py`
(fixture qui extrait `rttyEstIndicatif(` par découpe de texte + un test qui
vérifie que `rttyOutput`/`rttyStartBtn`/`rttyMark`/`rttyShift` apparaissent
dans le texte de `logx_logbook.js` — motif `_lire_tout()` à réutiliser,
comme pour busted-call). 15e incrément à suivre dans la même session.
