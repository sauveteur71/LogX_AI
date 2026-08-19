---
name: chantier-ev7-rtty-panel-2026-08-08
description: "EV-7 15e incrément : panneau décodeur + émission RTTY extrait vers logx_rtty_panel.js (commit 657b365, branche feat/ev7-extract-rtty-panel) — 6 variables d'état + 12 fonctions, tests adaptés, revue adversariale 0 constat"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T18:09:48.685Z
---

Chantier livré sur la branche `feat/ev7-extract-rtty-panel` (commit de
contenu `657b365`), fusion sur `main` à confirmer une fois la CI verte.

## Contexte

Après le 14e incrément ([[chantier-ev7-sstv-panel-2026-08-08]]), reprise
sans nouvelle demande explicite (instruction permanente de F4GLD "je
m'absente qques heures continu a bosser sans moi t'arrete pas"). Candidat
RTTY réutilisé depuis l'évaluation détaillée déjà produite lors de
l'inventaire du 10e incrément (même scratchpad `rtty_sstv_eval.txt` que
pour SSTV) — dernier des 2 candidats FAIBLE risque de ce lot.

## Ce qui a changé

6 variables d'état (`_rttyDecoder`, `_rttyTexte`, `_rttyDevicesLoaded`,
`RTTY_TX_MACROS`, `_rttyTxArmed`, `_rttyOutDeviceLoaded`) + 12 fonctions
déplacées vers `logx_rtty_panel.js` (178 lignes, extraites de
`logx_logbook.js` L2292-2469). L'évaluation initiale n'en listait que 7
(les points d'entrée HTML directs : `toggleRttyPanel`, `rttyAppliquerTons`,
`toggleRttyDecoder`, `rttyClicTexte`, `clearRttyOutput`, `rttyOnArmChange`,
`rttyEnvoyerLibre`) — en relisant le VRAI code j'ai trouvé 5 fonctions
internes supplémentaires jamais câblées en HTML mais appelées seulement
depuis d'autres fonctions du même bloc (`rttyTons`, `rttyRender`,
`rttyEstIndicatif`, `renderRttyMacroBtns`, `rttyEnvoyerTexte`) — confirmées
par grep exhaustif comme strictement internes au bloc, donc extraites avec
le reste sans risque.

## Dépendance entrante non documentée par l'évaluation initiale

`updateKeyerPanels()` (coordinateur CW/RTTY/SSTV/voix, reste dans
`logx_logbook.js`) ne se contente pas d'appeler `renderRttyMacroBtns()` et
de basculer `#rttyDecoder.style.display` (déjà noté dans l'évaluation) :
elle ÉCRIT aussi directement dans `_rttyDevicesLoaded`/
`_rttyOutDeviceLoaded` (`loadAudioInputDevices('rttyDevice').then(ok =>
{ _rttyDevicesLoaded = ok; })`). Trouvé en lisant le code réel avant
extraction, pas après coup. Sans danger : portée globale classique
partagée, `updateKeyerPanels()` n'est exécutée qu'au runtime (poll d'état
radio), jamais au chargement des `<script>` — la même règle
top-level-vs-corps-de-fonction que pour toutes les extractions précédentes
s'applique, juste dans le sens inverse (le fichier chargé APRÈS mute une
variable du fichier chargé AVANT, à l'intérieur d'un corps de fonction).

## Tests adaptés

`tests/test_rtty_decodeur.py` (contrairement à SSTV, RTTY touche bien un
test dédié comme prévu par l'évaluation) :
- fixture `moteur_logbook` : extrayait `rttyEstIndicatif(` par découpe de
  texte depuis `logx_logbook.js` seul → lit désormais
  `logx_logbook.js + logx_rtty_panel.js`.
- `test_le_panneau_est_bien_cable_dans_le_logbook` : vérifiait les
  identifiants `rttyOutput`/`rttyStartBtn`/`rttyMark`/`rttyShift` dans le
  texte de `logx_logbook.js` seul → même adaptation. `cwPanel`, resté dans
  `logx_logbook.js`, inchangé.

`tests/test_logbook_menu_debut_fin.py` : `logx_rtty_panel.js` ajouté à
`JS_EXTRAITS_EV7` (18e entrée) par convention établie.

## Bug préexistant trouvé en vérification, signalé séparément

En vérifiant en navigateur, une erreur console répétée chaque seconde
("Cannot set properties of null (setting 'textContent')" dans
`updateClockAndCountdown()`, `cd = document.getElementById('sbCountdown')`
sans garde `if(cd)`) — confirmée PRÉ-EXISTANTE via A/B test `git stash`
(même erreur identique sans les changements RTTY). Signalée via
`spawn_task` (`task_63cef982`) plutôt que corrigée dans cette branche,
même traitement que le bug `adaptivePoll` du 10e incrément
([[chantier-ev7-contest-picker-2026-08-08]]).

## Vérification navigateur

`toggleRttyPanel()` ouvre/ferme le panneau (DOM pur), `rttyEstIndicatif()`
filtre correctement (indicatifs reconnus, `CQ`/`599` rejetés, ponctuation
parasite retirée), `rttyRender()` tokenise en éléments cliquables,
`renderRttyMacroBtns()` peuple 4 boutons macro depuis `RTTY_TX_MACROS`.
Aucune fonction déclenchant un vrai décodage micro ou une émission audio
n'a été appelée. État remis à zéro après test (`clearRttyOutput()`).

## Revue adversariale

2 dimensions (extraction-fidelity, dependency-integrity) : **0 constat**.

## Suite

`logx_logbook.js` : 6310 → 6135 lignes après ce 15e incrément (6930 avant
le 10e, soit -795 lignes sur 6 incréments consécutifs). Les 2 candidats
FAIBLE risque de l'évaluation initiale (RTTY, SSTV) sont maintenant
épuisés — un nouvel inventaire Workflow complet sera nécessaire pour
identifier un 16e candidat si le chantier continue.
