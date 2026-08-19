---
name: piege-vocabulaire-identifiants-js-pas-seulement-texte-visible
description: "tests/test_vocabulaire_portable.py peut faire échouer un NOUVEAU nom de fonction JS contenant activation/activateur, pas seulement du texte visible"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-16T09:16:39.378Z
---

`tests/test_vocabulaire_portable.py` interdit "activation"/"activateur" (et
pluriels) dans tout texte VISIBLE des pages HTML de `concours/`
(`logx_configuration.html`, `logx_logbook.html`, `logx_mobile.html`,
`logx_panel.html`) — règle F4GLD permanente du 30/07/2026 (« supprime ce
language cibiste avec ACTIVATION ACTIVATEUR etc on est radioamateur ! »,
voir [[feedback-vocabulaire-radioamateur]]). Le garde-fou exempte les
COMMENTAIRES et une liste blanche fixe d'identifiants de code déjà existants
(`activationBar`, `ActivationMode`, `myActivationRef`, `selfSpotActivation`,
`refreshActivation`, `applyActivationMode`, `logx_activation`, etc. — regex
`IDENT` dans le fichier de test).

**Piège trouvé pendant le chantier export POTA (16/08/2026)** : un `onclick=`
inline (`onclick="exportActivationAdif()"`) est lu comme du texte par ce
test au même titre qu'un libellé de bouton — la liste blanche `IDENT` ne
couvre QUE les identifiants qui existaient déjà au moment où elle a été
écrite, pas un nouveau nom de fonction inventé pour un chantier ultérieur.
`exportActivationAdif` n'y figurait pas → test rouge, alors que ce n'est ni
un texte visible ni un ancien identifiant oublié.

**How to apply:** avant de nommer une NOUVELLE fonction/variable/id JS
touchant la barre d'activation POTA/SOTA/IOTA/WWFF (ou toute page listée
ci-dessus), éviter "activation"/"activateur" dans le nom plutôt que
d'élargir la regex `IDENT` du test — un nom qui n'emploie pas le mot est de
toute façon souvent plus précis (ex. `exportPotaAdif`, spécifique à POTA,
choisi à la place de `exportActivationAdif`). Ne pas se fier à un grep du
seul texte visible avant de considérer un lot terminé : lancer
`tests/test_vocabulaire_portable.py` reste le seul filet fiable, il couvre
aussi les attributs (`onclick=`, `title=`) qu'un grep ciblé sur le contenu
entre balises pourrait manquer.
