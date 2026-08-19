---
name: chantier-ev7-dxcc-lookup-2026-08-08
description: "EV-7 11e incrément : table CTY_PREFIX + lookupDXCC() extraites vers logx_dxcc_lookup.js (merge 532a2eb) — extraction via script Python plutôt que Write/Edit pour garantir l'intégrité des ~130 emoji drapeaux Unicode complexes ; revue adversariale 0 constat"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T16:16:44.146Z
---

Chantier livré et fusionné sur `main` le 08/08/2026 (commit `532a2eb`, merge
de `feat/ev7-extract-dxcc-lookup`, commit de contenu `def1cd9`).

## Contexte

Candidat #2 du top 3 identifié par l'inventaire Workflow (cartographie de 64
blocs restants dans `logx_logbook.js`) lors de
[[chantier-ev7-contest-picker-2026-08-08]] (le 10e incrément, candidat #1,
avait déjà été livré). F4GLD a demandé de poursuivre directement ("go 2").

## Ce qui a changé

`CTY_PREFIX` (table préfixe → {pays, continent, zone CQ, drapeau}, ~120
lignes) et `lookupDXCC(call)` (résolution du préfixe le plus long, 4→1
caractères, avec dépouillement du suffixe `/P`/`/MM` etc.) déplacés de
`logx_logbook.js` (lignes 887-1020) vers `logx_dxcc_lookup.js` — extraction
mécanique à l'identique. `<script src="logx_dxcc_lookup.js">` ajouté dans
`logx_logbook.html` avant `<script src="logx_logbook.js">`.
`JS_EXTRAITS_EV7` mis à jour.

Bloc confirmé 100% autonome dès l'investigation initiale : IIFE
auto-suffisante (aucune dépendance sortante), 4 appels internes à
`logx_logbook.js`, tous en LECTURE PURE et tous à l'intérieur du corps
d'une fonction (jamais au niveau top-level du fichier) — donc aucun souci
d'ordre de `<script>` malgré le nouveau fichier chargé AVANT
`logx_logbook.js`. Zéro appelant externe (aucun autre fichier JS/HTML du
dépôt), zéro test existant référençant ces symboles.

## Piège méthodologique évité : extraction via script, pas Write/Edit

Le bloc contient ~130 entrées avec emoji drapeaux, dont plusieurs séquences
Unicode COMPLEXES (drapeaux régionaux Écosse/Pays de Galles/Angleterre,
utilisant des séquences de « tag » multi-codepoints, pas de simples emoji
à 2 codepoints comme 🇫🇷). Retranscrire ce contenu à la main via l'outil
Write aurait présenté un risque réel de corruption silencieuse (troncature,
substitution, ou mauvais encodage d'un des drapeaux les plus complexes).

**Décision prise avant d'écrire quoi que ce soit** : extraction via un
script Python dédié (lecture des lignes exactes par index, écriture
directe du même contenu binaire dans le nouveau fichier, remplacement par
un court commentaire dans le fichier source) — élimine tout risque de
retranscription manuelle. Piège rencontré PENDANT l'exécution (pas anticipé
à l'avance) : le premier essai du script a planté à l'étape `print()` avec
`UnicodeEncodeError: 'charmap' codec can't encode...` — la CONSOLE Windows
(cp1252) ne peut pas afficher les emoji, mais ÇA N'AVAIT RIEN À VOIR avec
l'écriture des fichiers eux-mêmes (qui utilisaient déjà `encoding='utf-8'`
explicite). Vérifié qu'aucun fichier n'avait été touché avant de relancer
(le crash intervenait avant les appels `open(..., 'w')`). Corrigé en
retirant l'affichage brut des emoji dans les `print()` de diagnostic
(`PYTHONIOENCODING=utf-8` + affichage ASCII-safe via `.encode('ascii',
'replace')` pour les extraits de contenu) — la logique d'extraction
elle-même n'a jamais eu besoin d'être modifiée.

Intégrité vérifiée à 3 niveaux indépendants après coup : (1) recherche des
emoji `🇫🇷`/`🏴` dans le fichier écrit, (2) vérification syntaxique JS des
deux fichiers via `new Function(src)` (py_mini_racer), (3) test EN
NAVIGATEUR RÉEL sur le serveur de production —
`lookupDXCC('DL1ABC')`/`('W1AW')`/`('JA1XYZ')`/`('F4GLD/P')` retournent
tous les bons drapeaux/pays/continent/zone CQ, `_brickCtx()` (qui consomme
`lookupDXCC` en interne) fonctionne normalement. Revue adversariale
Workflow (2 dimensions, avec consigne explicite d'échantillonner les
drapeaux pour confirmer l'absence de corruption) : **0 constat**.

## Réflexe généralisable pour toute future extraction EV-7

Avant d'extraire un bloc via Write/Edit, vérifier s'il contient du contenu
Unicode dense/complexe (emoji multi-codepoints, texte non-latin, séquences
de combinaison) — si oui, préférer un script d'extraction programmatique
(lecture/écriture directe des octets/lignes) à une retranscription
manuelle par l'outil d'édition, même si cela demande une étape
supplémentaire.

## Suite

`logx_logbook.js` : 6843 → 6706 lignes. Reste du top 3 : la carte QSO
Leaflet (`initMap`/`refreshMapLayers`/`toggleMapView`, ~115 lignes,
candidat #3 non encore traité). RTTY, SSTV et le filet anti-busted call
restent en réserve FAIBLE risque. Mêmes candidats à éviter que documentés
dans [[chantier-ev7-contest-picker-2026-08-08]] (chemin critique, faux
candidats mélangeant plusieurs sujets).
