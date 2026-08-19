---
name: chantier-ev7-esm-callbot-2026-08-08
description: EV-7 19e incrément — extraction CALLBOT vocal + ESM vers logx_esm_callbot.js (08/08/2026, fusionné fac5187)
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T21:54:08.610Z
---

19e incrément de la campagne EV-7 : extraction du bloc CALLBOT vocal +
ESM (Enter Sends Message) de `logx_logbook.js` (lignes originales
1875-1988) vers `concours/logx_esm_callbot.js`, chargé en `<script>`
classique dans `logx_logbook.html` AVANT `logx_logbook.js`. Contenu :
`VOICE_MACRO_DEFAULT`, `getVoiceDynMacros()`, `saveVoiceDynMacros()`,
`renderVoiceDynPanel()`, `sendVoiceDynMacro()`, `editVoiceDynMacro()`,
`esmMode`/`esmExchanged`, `toggleEsm()`, `esmSend()`, `esmHandleEnter()`.
Branche `feat/ev7-extract-esm-callbot`, commit contenu `1b8518d`, fusionné
sur `main` en `fac5187`.

**Le piège central de cet incrément** (le plus large rencontré à ce jour
dans la campagne) est documenté séparément dans
[[piege-appel-top-level-casse-tests-hote-entier]] — un appel TOP-LEVEL
`renderVoiceDynPanel();` restant dans `logx_logbook.js` a cassé 12
fichiers de tests d'un coup, pas seulement ceux liés à ESM/CALLBOT.

**Constat confirmé par la revue adversariale Workflow** (1 seul, sur les
2 dimensions extraction-fidelity + dependency-integrity) : le commentaire
d'en-tête de `logx_hardware_cat.js` (ajouté lors de l'incrément précédent,
[[chantier-ev7-radio-cat]]) décrivait le bug `esmSend()`/`rigState.enabled`
comme « non corrigé ici — signalé séparément à F4GLD », alors que le code
réellement déplacé dans `logx_esm_callbot.js` montre qu'il l'était déjà
(`rigState.mode`, avec un commentaire explicite « corrigé séparément sur
demande explicite de F4GLD »). Dérive purement documentaire (préexistante
avant cet incrément — introduite par le commit qui a appliqué le
correctif sans mettre à jour ce commentaire pointeur, pas par cet
incrément lui-même), corrigée dans le même commit que l'extraction.

**Vérification navigateur** (serveur local port 8080, hard-reload
Ctrl+Shift+R) : toutes les fonctions extraites existent en portée globale
réelle après chargement de la page ; `renderVoiceDynPanel()` a bien rendu
les 4 boutons macro de `VOICE_MACRO_DEFAULT` dès le chargement (preuve
vivante que l'appel top-level fonctionne une fois le fichier chargé dans
le bon ordre) ; `toggleEsm()` bascule correctement `esmMode` et
l'affichage du bouton `#esmBtn` (texte + couleur).

**Bruit sans rapport découvert pendant la vérification** (diff confirmé
minimal, aucun lien avec cet incrément) : deux erreurs console
préexistantes et répétées (`ReferenceError: adaptivePoll is not defined`
dans `logx_hardware_cat.js:524-525`, et un crash
`Cannot set properties of null (setting 'textContent')` pointant vers
`logx_logbook.js:2337` alors que la fonction à cette ligne a pourtant un
garde `if(lbl)` — le vrai site du crash reste à identifier). Signalé comme
tâche séparée (spawn_task), PAS traité dans cet incrément.

Suite pytest complète verte (EXIT_REEL=0, vérifié deux fois) après
correction des 12 fichiers de tests + le fichier
`test_edit_qso_mode_hors_concours.py` découvert lors de la 2e passe.
