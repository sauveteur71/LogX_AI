---
name: chantier-ev7-outils-divers-2026-08-09
description: "EV-7 36e incrément — combo SO2R+backupNow+QSO TIMER+bip audio vers logx_outils_divers.js (09/08, merge 9f7d1e6)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T12:12:56.104Z
---

36e (et dernier prévu à ce stade) incrément de la campagne EV-7 (LogX AI) :
combo de 4 candidats FAIBLE (~74 lignes au total) issus du 5e inventaire,
regroupés dans `concours/logx_outils_divers.js` (même motif que le combo du
8e incrément) : `updateQsoTimer()` + son `setInterval`, SO2R bascule
d'émission (`so2rBasculer`/`so2rAfficher`/`so2rRafraichir`/`_so2rFocus`),
`backupNow()`, audio bip confirmation QSO (`bipEnabled`/`initBipBtn`/
`toggleBip`). Fusionné sur main : commit 9f7d1e6 (merge), de22f59 (contenu).

**Extraction non-contiguë à 4 blocs** — technique par ancre de chaîne déjà
établie, mais premier incrément où un mauvais choix de marqueur de fin a
tronqué un bloc silencieusement (le texte de fin de `toggleBip()` était
identique à une ligne de l'IIFE `initBipBtn()` qui le précède — `src.index()`
a trouvé la PREMIÈRE occurrence au lieu de la dernière). Détecté
immédiatement par la vérification syntaxe py_mini_racer (`SyntaxError:
Unexpected token '}'`), corrigé en repartant de `git show HEAD:...` et en
utilisant un marqueur de fin plus long et réellement unique
(`localStorage.setItem('rc_bip', ...)`, absent de l'IIFE).
**How to apply :** pour tout futur marqueur de fin de bloc extrait, vérifier
qu'il n'apparaît PAS ailleurs dans le MÊME bloc candidat avant de l'utiliser
comme ancre — ne pas se fier uniquement à `src.index(end_marker, start_idx)`
si le bloc contient du code structurellement répétitif (deux fonctions aux
corps très proches).

**Motif « classe 5 » (variable d'état partagée, introduit au 35e incrément)
illustré des DEUX côtés dans le même incrément :**
- `lastQsoTime` reste dans le cœur (écrite par `submitQSO()` à 3 sites de
  succès + un site d'init, tous dans le cœur) — seule `updateQsoTimer()`
  (qui la LIT seulement) migre.
- `bipEnabled` migre EN BLOC avec ses fonctions — le seul site cœur
  (`playBeep()`) ne fait qu'une LECTURE simple, pas d'écriture. Même patron
  déjà en production pour `esmMode` (déclarée dans `logx_esm_callbot.js`).
**How to apply :** la règle de décision n'est pas seulement « y a-t-il un
site externe ? » mais « ce site externe LIT ou ÉCRIT ? ». Écriture multiple
depuis le cœur → laisser la variable au cœur. Lecture seule (même depuis le
cœur) → la variable peut migrer avec ses fonctions sans risque, car le
fichier qui la déclare charge toujours avant le cœur.

**Bug réel trouvé et corrigé — PAR UN VRAI RUN PYTEST, PAS PAR LA REVUE** :
`tests/test_macro_cw_serie_bande.py` exécute `submitQSO()` dans un vrai
moteur V8 (scénario complet CW/macros/série). Sans `logx_outils_divers.js`
dans sa chaîne de chargement, `bipEnabled` était indéfinie au moment où
`playBeep()` (appelée par `submitQSO()`) la lisait → `ReferenceError`
silencieuse en plein scénario → le marqueur de fin (`__done`) restait à
`false` → 3 tests en échec avec le message générique « le scénario ne s'est
pas déroulé entièrement ». Corrigé en ajoutant `OUTILS_DIVERS_JS_PATH` à la
chaîne de `_real_source()`. **How to apply :** ce fichier de test documente
déjà lui-même ce piège en commentaire pour CHAQUE incrément précédent qui l'a
touché (hardware_cat, callbook, lookup, esm_callbot, voice_keyer,
locator_reverse, macros, filtre_spots) — c'est un « canari » fiable pour la
classe de piège n°2 (appel function-body depuis `submitQSO()`), à toujours
faire tourner en priorité (isolément d'abord, `pytest tests/test_macro_cw_serie_bande.py -q`)
avant la suite complète pour tout futur incrément touchant de près ou de
loin `submitQSO()`/`playBeep()`.

**Piège de notification réaffirmé** : la 1re tentative de lancement de la
suite complète a affiché « exit code 0 » dans la notification alors que 3
tests avaient réellement échoué (log contenant bien `FAILED`). Corrigé la
2e fois en écrivant explicitement `echo "REAL_EXIT_CODE:$?" >> log` DANS le
fichier de log lui-même, pour ne plus jamais dépendre du résumé de
notification seul — voir [[piege-echo-exit-masque-code-sortie-reel]].

Revue adversariale (Workflow, 2 dimensions, avec consigne explicite de
chercher d'autres fichiers de test hôte-entier similaires oubliés) :
0 constat sur l'extraction elle-même (bonne nouvelle : la revue n'a rien
trouvé que le run pytest réel n'avait pas déjà détecté et corrigé avant
elle) ; 1 constat déjà connu et sans action requise (dérive
`custom_contests.json`, hors périmètre, jamais staged).

Voir aussi la synthèse de fin de campagne : [[chantier-ev7-synthese-fin-campagne-2026-08-09]].
