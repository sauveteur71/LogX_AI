---
name: chantier-ev7-bandscope-waterfall-2026-08-09
description: "EV-7 31e incrément : extraction BANDSCOPE+WATERFALL vers logx_bandscope_waterfall.js (09/08, merge 835780e) — try/catch englobant de refreshBandMap() et bandmapClick() vérifiés intacts, intégration réelle confirmée contre le serveur de production, 0 constat"
metadata: 
  node_type: memory
  type: project
  modified: 2026-08-09T06:28:51.673Z
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
---

31e incrément de la campagne, candidat MOYEN du 3e inventaire
([[inventaire-ev7-3e-2026-08-09]]). Extraction de 95 lignes de
`concours/logx_logbook.js` (1197-1291) vers `concours/logx_bandscope_waterfall.js`
(nouveau) : `drawBandscope()` (spectre SVG de densité des spots),
`toggleWaterfall()`/`_wfShown`/`_wfLastBand`, `_cssVar()` (utilitaire lecture
couleur CSS calculée), `drawWaterfallRow()` (rendu canvas 2D d'une chute
d'eau, défile via `drawImage`).

**Point d'attention structurel respecté avec succès** : le bloc extrait est
encadré par DEUX fonctions du cœur qui ne devaient pas être touchées —
`refreshBandMap()` (juste avant, avec son gros `try{}catch(e){}` qui appelle
`drawBandscope()`/`drawWaterfallRow()` en toute fin) et `bandmapClick()`
(juste après, gestion du clic QSY sur un spot — fonctionnalité différente).
Les deux sont restées intactes et complètes dans `logx_logbook.js`,
confirmé par la revue adversariale (comptage d'accolades).

Dépendances croisées vérifiées sûres : `refreshBandMap()` appelle
`drawBandscope()`/`drawWaterfallRow()` en corps de fonction (jamais
top-level) ; ces dernières lisent en retour `_BM_PCOL`/`escHtml` et
`currentBand`/`_BM_CSSVAR` (constantes/fonctions du cœur), toujours en
corps de fonction — sûr par le même raisonnement que tous les incréments
précédents (fichier extrait chargé avant le cœur).

2 fichiers de test mis à jour (`test_bandmap_waterfall_band_change.py` —
fichier dédié qui exécute réellement `toggleWaterfall()`/`drawWaterfallRow()`
en V8 — et `test_logbook_menu_debut_fin.py`). **2 faux positifs identifiés
et vérifiés indépendamment par la revue adversariale** : `test_panneaux_multi_fenetres.py`
(teste `popoutScope()` dans un fichier déjà extrait, fonctionnalité
homonyme de fenêtre détachée sans rapport) et `test_freq_unite_spots.py`
(le mot "bandscope" n'apparaît que dans un commentaire de prose, le test
réel porte sur la conversion de fréquence dans `refreshBandMap()`, restée
dans le cœur) — aucun changement nécessaire pour ces deux-là.

Suite pytest complète (8792 tests) verte du premier coup. Vérification
navigateur réelle sur le serveur de production (`http://localhost:8080/logx_logbook.html`
— voir [[piege-url-concours-prefixe-sert-vide]]) : `toggleWaterfall()`/
`drawBandscope()`/`drawWaterfallRow()` exercées avec des données
synthétiques (SVG non vide, canvas 2D sans exception). **Test d'intégration
réel supplémentaire** : appel complet de `refreshBandMap()` (cœur) contre
le vrai serveur de production, résolu sans erreur — confirme l'appel
cross-fichier de bout en bout en conditions réelles, pas seulement une
vérification unitaire des fonctions isolées.

Revue adversariale (extraction-fidelity + dependency-integrity, 2 agents,
53 appels d'outils) : 0 constat.

`logx_logbook.js` : ~4188 → ~4093 lignes (net après ajout du pointeur).

Suite : dernier candidat MOYEN du 3e inventaire — MACROS F1-F8 (32e
incrément, découpage non-contigu à surveiller), puis FILTRE D'AFFICHAGE
DES SPOTS + refreshBandMap (33e), avant de lancer un 4e inventaire.
