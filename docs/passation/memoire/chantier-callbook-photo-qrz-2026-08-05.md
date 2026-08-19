---
name: chantier-callbook-photo-qrz-2026-08-05
description: "Photo QRZ dans le callbook du logbook (05/08/2026, a4ec690) — deuxième point OpsLog déjà livré (enregistrement audio par QSO, plus ancien dans la session)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-05T20:09:04.913Z
---

Livré le 05/08/2026 (commit `a38f446`, mergé `a4ec690`) : la fiche callbook
affichée à la frappe dans LOGBOOK montre désormais la photo du titulaire
quand QRZ.com (compte XML abonné) la fournit — balise `<image>` du XML,
jamais présente sur HamQTH/HamDB. `logx_qrz.py` filtre le schéma (http/https
uniquement) avant de la transmettre au client, `logx_logbook.js`
(`lookupQRZ()`) l'affiche en miniature 36px avec repli silencieux
(`onerror`) si le lien est mort.

C'était le premier des deux points mineurs identifiés lors de la comparaison
OpsLog (voir échange F4GLD du 05/08/2026). Le second point — enregistrement
audio optionnel par QSO — s'est avéré **déjà livré plus tôt dans la même
session** (commits `5a2c452`/`47196a8`, bien avant la comparaison OpsLog :
tampon glissant 2 min + clip 20s au log, toggle `recEnabled` en
localStorage, WAV PCM16 encodé côté client). Un résumé de compaction avait
listé ce point comme « pending » alors qu'il ne l'était plus — vérifié par
`git log --all` avant de commencer, pas fait confiance au résumé seul.

🚨 **Piège trouvé en testant** : `photo.removeAttribute('src')` a fait
planter `tests/test_macro_cw_serie_bande.py` (test JS réel via
py_mini_racer) — le DOM minimal de ce test ne stubbe QUE `setAttribute`/
`getAttribute` dans son proxy générique, pas `removeAttribute`. Un appel à
une méthode DOM non listée dans ce stub renvoie `undefined` puis explose en
« not a function » au premier appel — silencieusement absorbé par endroits
(catch englobant) mais fatal ici car l'appel était dans `clearForm()`,
appelée à CHAQUE QSO loggué. Corrigé en remplaçant par une simple
affectation de propriété (`photo.src = ''`), déjà le pattern utilisé
partout ailleurs dans ce fichier pour manipuler le DOM.

**How to apply** : avant d'appeler une méthode DOM autre que
`style`/`classList`/`dataset`/`setAttribute`/`getAttribute`/`appendChild`/
`querySelector` etc. dans `logx_logbook.js`, vérifier qu'elle est bien
listée dans le proxy `ElProxy()` de `tests/test_macro_cw_serie_bande.py`
(et `test_logbook_render_window_reset.py`, même pattern) — sinon préférer
une affectation de propriété brute, qui passe toujours par le trap `set`
générique du Proxy.
