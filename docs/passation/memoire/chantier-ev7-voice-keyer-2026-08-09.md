---
name: chantier-ev7-voice-keyer-2026-08-09
description: EV-7 20e incrément — extraction Keyer vocal DVK vers logx_voice_keyer.js (09/08/2026, fusionné 3567166) — piège top-level anticipé PROACTIVEMENT, 0 échec pytest
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T22:49:58.552Z
---

20e incrément de la campagne EV-7 : extraction du bloc KEYER VOCAL (phonie,
messages WAV enregistrés, slots DVK côté serveur) de `logx_logbook.js`
(lignes originales 1358-1498) vers `concours/logx_voice_keyer.js`, chargé
en `<script>` classique dans `logx_logbook.html` juste après
`logx_esm_callbot.js`, avant `logx_logbook.js`. Contenu : `VOICE_SLOTS`,
`_mediaRec`/`_recSlot`/`_recChunks`, `voiceSlots`, `voiceRefreshSlots()`,
`_voiceMigrationFaite`/`voiceMigrerAnciens()`, `renderVoicePanel()`,
`voiceRecord()`, `_blobToBase64()`, `voicePlay()`. Branche
`feat/ev7-extract-voice-keyer`, commit contenu `c3a1456`, fusionné sur
`main` en `3567166`.

**Point notable : le piège de [[piege-appel-top-level-casse-tests-hote-entier]]
a été anticipé PROACTIVEMENT cette fois, pas découvert après coup.** Avant
même d'extraire, un grep de tous les identifiants du bloc a révélé l'appel
top-level `voiceRefreshSlots();` (ligne ~1883 de `logx_logbook.js`, juste à
côté de `renderVoiceDynPanel();`, le même symptôme que le 19e incrément).
Les 14 fichiers de tests qui évaluent `logx_logbook.js` en entier via V8
(la même liste que celle établie au 19e incrément, aucun 15e fichier
manquant — confirmé par la revue adversariale) ont été corrigés AVANT le
premier push. Résultat : suite pytest complète verte du **premier coup**
(EXIT_REEL=0, 0 échec) — contre 65 échecs répartis sur 12 fichiers pour le
19e incrément, qui avait découvert ce piège après coup. La méthode « grep
top-level avant de pousser » est donc validée une 2e fois avec succès (voir
mise à jour de [[piege-appel-top-level-casse-tests-hote-entier]]).

**Dépendance inverse documentée sans risque** : `voicePlay()` est appelée
par `logx_esm_callbot.js` (`esmSend()`, rôle vocal) — strictement à
l'intérieur d'une fonction (jamais top-level), donc sans risque : les deux
fichiers extraits sont de toute façon chargés avant `logx_logbook.js`.

**Revue adversariale Workflow** (2 dimensions, 8 constats bruts, tous
vérifiés indépendamment) : **zéro défaut réel trouvé**. Les 4 constats
marqués « confirmé » par les vérificateurs étaient tous des confirmations
« rien à corriger » (extraction fidèle, `JS_EXTRAITS_EV7` correct, ordre
de chargement correct dans les 14 fichiers, suite pytest verte) — pas des
bugs. Un vérificateur a aussi noté qu'un flake isolé (`test_awards_qsl.py`,
lié à `pytest-randomly`, sans rapport avec cette branche) était apparu lors
d'un premier passage puis disparu — cohérent avec
[[suite-tests-flakes-sous-charge]], pas une régression de cet incrément.

Vérification navigateur (serveur local port 8080, hard-reload) : toutes
les fonctions extraites existent en portée globale réelle, `voiceRefreshSlots()`
a bien déclenché `renderVoicePanel()` qui a rendu les 4 boutons macro dès
le chargement, aucune erreur console liée à « voice ».
