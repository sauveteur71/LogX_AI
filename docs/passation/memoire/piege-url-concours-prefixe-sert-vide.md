---
name: piege-url-concours-prefixe-sert-vide
description: "PIÈGE vérification navigateur : http://localhost:8080/concours/logx_logbook.html sert un contenu périmé/vide sur le serveur de production — toujours utiliser la racine /logx_logbook.html (09/08)"
metadata: 
  node_type: memory
  type: project
  modified: 2026-08-09T06:00:18.750Z
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
---

Découvert pendant la vérification navigateur du 30e incrément EV-7
([[chantier-ev7-cw-panel2-audio-2026-08-09]]) : naviguer vers
`http://localhost:8080/concours/logx_logbook.html` (avec le préfixe
`/concours/`) charge une page où TOUTES les fonctions EV-7 récemment
extraites sont `undefined` et où `document.querySelector('script[src=...]')`
ne trouve aucun des script tags pourtant présents dans le fichier source —
y compris des fichiers mergés des HEURES plus tôt dans la même session
(`logx_soapbox.js`). Un `fetch('/concours/logx_logbook.html')` confirme :
réponse vide (`len:0`).

La bonne URL, confirmée par grep des chemins déjà utilisés dans les erreurs
console (`http://localhost:8080/logx_hardware_cat.js`, sans préfixe) et par
un `fetch('/logx_logbook.html')` qui renvoie bien le contenu à jour (168903
octets, tous les script tags présents) : le serveur sert les fichiers
`concours/*` À LA RACINE de son URL, pas sous un chemin `/concours/`.

**Réflexe pour toute vérification navigateur future sur ce projet** :
toujours naviguer vers `http://localhost:8080/logx_logbook.html` (et
équivalent pour les autres pages : `logx_configuration.html`, etc.), JAMAIS
vers `http://localhost:8080/concours/logx_logbook.html`. Si un onglet
existant montre des fonctions `undefined` alors qu'elles sont sensées être
chargées, vérifier `location.href` ET faire un `fetch(url, {cache:'no-store'})`
sur le chemin exact avant de conclure à un problème de cache navigateur — ça
peut être un problème de CHEMIN, pas de cache (voir aussi
[[piege-cache-navigateur-masque-changement-js]] pour le cas cache, distinct
de celui-ci).
