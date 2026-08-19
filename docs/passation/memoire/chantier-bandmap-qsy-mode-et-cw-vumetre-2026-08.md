---
name: chantier-bandmap-qsy-mode-et-cw-vumetre-2026-08
description: "Deux bugs signalés ensemble par F4GLD (04/08/2026) : QSY tableau de bande sans mode (`9bc60b2`) + décodeur CW sans retour de diagnostic (`dc1416c`)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-04T10:13:13.292Z
---

Suite directe de [[chantier-voicekeyer-synthese-multivoix-2026-08]], même
message du 04/08/2026 : *« gros progres le CAT fonctionne mais lorsque je
clic sur le tableau de bande la radio ne commute pas automatiquement sur la
fréquence et le mode. le decodeur CW fonctionne mais ne decode rien »* — deux
bugs distincts, traités l'un après l'autre sur deux branches séparées.

## Bug 1 — QSY tableau de bande : fréquence oui, mode jamais

Le CAT lui-même marchait (la fréquence changeait bien) — c'est le MODE qui
n'était jamais transmis à `/rig/qsy`. Deux endroits distincts, deux causes
différentes :

- **`logx_bande.html`** (fenêtre popup par bande) : `qsy(khz)` ne construisait
  le body qu'avec `freq_khz` — aucun `data-mode` posé sur les lignes/épingles
  du tableau à la source. Il fallait ajouter le mode à la donnée AVANT de
  pouvoir le transmettre.
- **`logx_logbook.js`** (`bandmapClick()`) : le mode ÉTAIT transmis, mais
  c'était `currentMode` — le mode de SAISIE COURANTE de l'opérateur, pas le
  mode RÉEL du spot cliqué. Un clic sur un spot CW pendant une saisie SSB
  faisait donc QSY en SSB. `modeSpot` était déjà calculé juste à côté
  (ligne 1587) mais jamais transmis à la fonction — pas un bug d'absence de
  donnée, un bug de mauvaise donnée utilisée. Même défaut trouvé et corrigé
  dans `drawBandscope()` (spectre SVG), qui appelait aussi `bandmapClick`
  sans mode.

Piège méthodologique rencontré en essayant de vérifier ce fix en navigateur :
`qsy()` est défini à l'intérieur d'une IIFE `(function(){...})()` dans
`logx_bande.html`, donc invisible depuis l'extérieur (`typeof qsy` ===
`'undefined'` en console) — impossible d'injecter un clic de test qui appelle
directement cette fonction depuis un script externe. Vérification retombée
sur : lecture attentive du diff (x3) + absence d'erreur console au chargement
+ suite pytest complète verte, sans simulation de clic bout-en-bout.

## Bug 2 — Décodeur CW : aucun bug de code trouvé, un vrai trou de diagnostic

Après lecture complète du pipeline DSP (`logx_cwdecoder.js` : Goertzel +
seuil adaptatif + décodeur temporel), **aucun bug ponctuel identifiable** —
le code est déjà le fruit d'itérations documentées (dérive de l'unité de
temps, compensation du délai de bloc). Le vrai problème : rien n'indiquait à
l'utilisateur SI le signal atteignait le seuil de détection, si le bon
périphérique audio était sélectionné, ou si le ton CW réglé (`650 Hz` par
défaut) correspondait à la tonalité réelle reçue — un décodeur silencieux
est indiscernable d'un décodeur qui reçoit juste du silence.

Correctif : un vumètre de diagnostic (`#cwMeter`/`#cwMeterFill`/
`#cwMeterThreshold`) branché sur le callback `onLevel` déjà câblé mais
jusque-là utilisé UNIQUEMENT pour afficher le WPM. Barre de niveau reçu +
repère de seuil, échelle visuelle = 3x le seuil courant (le seuil restant
toujours visible même s'il dérive avec le bruit de fond). Effet secondaire
corrigé au passage : `CwAudioDecoder` affichait "15 MPM" dès le démarrage
(valeur PAR DÉFAUT du décodeur temporel `MorseTimingDecoder`, avant toute
vraie mesure) — laissait croire qu'un signal était détecté alors que non.
`decoder.wpm` mis à 0 explicitement à la construction du wrapper audio (le
`MorseTimingDecoder` standalone, lui, garde son défaut 15 inchangé —
comportement testable isolément non touché).

## Reflex tests : aucun test JS n'existe dans ce dépôt (rappel)

Les deux corrections sont pur JS front-end — aucun test pytest ne les
couvre directement (confirmé par grep avant de committer : aucune référence
à `cwMeter`/`data-mode`/`bandmapClick` dans `tests/`). La suite pytest
complète reste verte après les deux fixes (aucune régression Python), mais
la SEULE garantie sur la logique JS elle-même vient de la lecture de code +
d'une vérification navigateur isolée sans erreur console — pas d'automatisation.
