---
name: piege-cache-navigateur-masque-changement-js
description: "PIÈGE vérification navigateur : navigate({force:true}) répétée sur la même URL peut servir un <script src> périmé depuis le cache HTTP — un correctif JS peut sembler ne pas fonctionner alors qu'il fonctionne, seul Ctrl+Shift+R (vrai rechargement forcé) le prouve"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T06:56:52.645Z
---

Trouvé le 08/08/2026 pendant [[chantier-ev7-radio-cat-2026-08-08]] : après
avoir corrigé un bug réel (appel `adaptivePoll()` avant sa définition, dû à
l'ordre des `<script>`), le correctif (`setTimeout(fn, 0)`) semblait ne PAS
fonctionner — `rigState.enabled` restait à `false` après plusieurs
`navigate({url, force:true})` vers la même URL, malgré le correctif
appliqué sur disque et confirmé présent via `fetch()` direct depuis la page.

**Cause** : le navigateur du pane Browser garde son cache HTTP normal, et
`navigate({force:true})` ne le vide pas systématiquement pour les
sous-ressources (`<script src="...">`) — seule la page HTML elle-même est
rechargée, le script JS référencé peut rester servi depuis le cache tant que
son URL ne change pas. Un ajout de logs `console.log()` temporaires dans le
fichier n'apparaissait même pas dans `read_console_messages` — signe que le
code exécuté n'était pas le code sur disque.

**Comment l'avoir détecté plus tôt** : comparer le contenu réellement exécuté
(ex. absence de logs de diagnostic ajoutés exprès) au contenu réellement
servi par le serveur (`fetch('/chemin/du/fichier.js').then(r=>r.text())`
exécuté depuis la page elle-même, PAS un outil externe) — si les deux
divergent, c'est le cache, pas le code.

**Correctif qui fonctionne à coup sûr** : `computer{action:"key",
text:"ctrl+shift+r"}` (hard reload) plutôt que `navigate({force:true})`
seul, quand on modifie un fichier JS référencé par `<script src>` et qu'on
veut vérifier l'effet d'un changement récent en navigateur.

**Comment l'appliquer** : avant de conclure qu'un correctif JS "ne marche
pas" en vérification navigateur (surtout après plusieurs `navigate` sans
effet visible), toujours tenter un Ctrl+Shift+R en premier réflexe plutôt
que de re-douter la logique du correctif — le symptôme (comportement
identique avant/après un changement censé le corriger) est souvent le cache,
pas un vrai échec de correctif.
