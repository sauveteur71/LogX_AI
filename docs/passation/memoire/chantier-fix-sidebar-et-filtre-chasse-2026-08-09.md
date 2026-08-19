---
name: chantier-fix-sidebar-et-filtre-chasse-2026-08-09
description: "Fix bouton LOGGER caché sous scroll sidebar CONFIG (#5, 74977bb) + filtre bandes CLUSTER NEED LIST et mode EXPÉDITIONS DX (#6, de308b4), 09/08/2026"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T18:06:12.427Z
---

Trois demandes F4GLD arrivées en cours de turn (auto mode) après la fin du
chantier ACOM/audit du 09/08/2026, traitées à la suite l'une de l'autre.

## 1. Signalement UX : popup CONFIG infermable (PR #5, 74977bb)

« je ne peux pas fermer le popup config sans cliquer ailleurs que sur les
onglets c'est un peu penible ». Diagnostic PAR MESURE DOM (pas supposition) :
le bouton de fermeture existait déjà (`.config-sidebar-launch` → `launchApp()`,
sauve + retourne vers LOGBOOK, épinglé en bas de la sidebar depuis la refonte
`#225`) mais toute la sidebar (titre+import+~20 catégories+LOGGER) défilait en
UN SEUL bloc `overflow-y:auto` — mesure `javascript_tool` : `scrollHeight:513`
vs `clientHeight:161` sur le viewport testé, bouton à `top:697` alors que la
zone visible s'arrêtait à `y:390`. L'utilisateur ne l'a simplement jamais vu.

**Correctif** : scindé `.config-sidebar` en 3 zones — titre+import+divider
FIXES en haut, nouveau `<div class="config-sidebar-scroll">` qui contient
SEULE la liste des catégories (`overflow-y:auto;flex:1;min-height:0`), et le
bouton LOGGER FIXE en bas (déjà `margin-top:auto`, resté hors de la zone de
scroll). Vérifié à 415px ET 900px de hauteur de fenêtre, jour ET nuit : le
bouton reste `visibleWithoutScroll:true` dans les deux cas.

**How to apply** : pour tout futur panneau/sidebar avec une zone de contenu
potentiellement longue (liste de catégories, d'items...) ET un bouton
d'action permanent (fermer/valider/lancer) qu'on épingle avec
`margin-top:auto`, ne JAMAIS mettre `overflow-y:auto` sur le CONTENEUR ENTIER
— seulement sur un `<div>` interne dédié au contenu variable, en laissant les
éléments fixes (titre, bouton d'action) HORS de cette zone scrollable. Sinon
le bouton fixe scrolle avec le reste et peut sortir du viewport sans aucun
indice visuel qu'il faut défiler pour l'atteindre — piège d'autant plus
sournois qu'il ne casse RIEN fonctionnellement (le bouton marche très bien
une fois atteint), donc invisible à toute vérification qui ne mesure pas le
DOM réel.

## 2. Filtre bandes CLUSTER — NEED LIST (PR #6, de308b4)

« mettre un filtre pour choisir une ou plusieurs bandes ». Puces `.band-chip`
générées DYNAMIQUEMENT depuis les bandes réellement présentes dans
`spotsData` (pas une liste figée) + puce "TOUTES BANDES" en tête pour
réinitialiser — multi-sélection (`Set` `selectedBands`, vide = pas de
filtre), même patron que les filtres TOUS/MULTS/SANS DUPES déjà existants
(cohérence UI). Piège trouvé APRÈS un 1er jet : le label interne de bande
utilisé partout dans l'appli (`_band_from_freq()`, `logx_scoring.py`) n'est
PAS un libellé `'20m'`/`'40m'` mais un nombre MHz nominal en chaîne
(`'14'`, `'3.5'`, `'21'`...) — confirmé en observant le rendu réel
(`sr-band` affiche déjà `${s.band} MHz`). Le premier `BAND_ORDER` écrit de
mémoire (`['160m','80m','40m',...]`) ne matchait donc RIEN et le tri
retombait silencieusement sur l'ordre d'insertion — pas un bug bloquant
(le filtrage fonctionnait quand même, seul l'ORDRE des puces était
cosmétiquement dégradé) mais détecté par une lecture DOM réelle des libellés
de puces (`['21','14','28','24','18','7']` au lieu de l'ordre HF croissant
attendu), pas par relecture du code seul.

**How to apply** : avant d'écrire une table de tri/format pour un champ
`band` dans CE codebase, vérifier la convention RÉELLEMENT utilisée à la
source (`grep _band_from_freq` dans `logx_scoring.py`) plutôt que de supposer
le format ham-radio usuel `'Xm'` — l'appli a fait le choix interne du nombre
MHz nominal en chaîne, cohérent avec l'affichage existant `${band} MHz` sur
ce même panneau.

## 3. Mode dans EXPÉDITIONS DX — NG3K (même PR #6)

« afficher la fréquence si disponible et le mode » — la fréquence live
existait déjà (`freq_khz`/`spot_band`, ajoutés en task #144) mais pas le
mode. `logx_dxpeditions._match_spot_freq()` itérait déjà sur les spots
cluster complets (qui portent tous un champ `mode`, vérifié par grep sur les
4 sources `logx_clusters.py` : DXHeat/telnet/F5LEN/DXSummit, cohérentes) —
il ne manquait qu'à le RENVOYER (tuple 2→3 : `(freq, band, mode)`) et
l'exposer comme `e['spot_mode']` dans `fetch_dxpeditions_chasse()`, déjà
transporté tel quel par `self._json(...)` côté `/data/dxpeditions_active`
(aucune sérialisation à toucher). Affiché réutilisant la classe CSS
`.sr-mode` déjà existante (même style que le mode POTA/SOTA affiché plus
haut sur la même page) — pas de nouvelle classe créée. Vérifié en navigateur
via une expédition SYNTHÉTIQUE injectée par mock de `fetch()` (aucune
expédition n'était spottée en direct au moment du test réel).

## Méthode commune aux 3

Deux branches indépendantes (pas empilées) : `fix/config-sidebar-*` basée
directement sur `main`, `feat/chasse-filtre-bande-et-mode-dx` aussi rebasée
sur `main` (pas sur la branche du fix précédent) pour garder les deux PR
mergeables indépendamment. `git checkout main` entre les deux a correctement
emporté les modifications de fichiers NON commitées (aucun conflit, fichiers
disjoints). Suite pytest complète relancée à 3 reprises (après chaque lot de
changements), 0 régression. Toujours PAS touché `concours/custom_contests.json`
(reste modifié en local, jamais stagé — conforme à la consigne permanente).

## Vérification post-fusion demandée par F4GLD (« verifie »)

Passe Workflow indépendante lancée APRÈS la fusion (4 agents à froid : état
git, 3 relectures de code sans connaissance de mes propres affirmations,
1 exécution pytest complète) — 0 constat sur les 3 relectures, donc la phase
de vérification adversariale (qui n'aurait servi qu'à trancher des constats
existants) s'est retrouvée vide par construction, pas sautée par erreur.
8855/8855 tests passés (388s) sur l'état RÉEL de `main` post-fusion (pas
juste sur la branche avant merge).

**Piège trouvé pendant cette passe** : la clé `spot_mode` était ABSENTE de
la réponse HTTP réelle de `/data/dxpeditions_active` testée en navigateur
sur le serveur de dev déjà en cours d'exécution — alors que le code Python
mergé était démontrablement correct (confirmé par import direct à froid :
`python -c "import logx_dxpeditions as dxp; ..."` donnait bien `spot_mode`).
Cause : Python ne recharge PAS ses modules à chaud, contrairement au JS —
un process serveur long-vivant démarré AVANT le merge continue de tourner
sur l'ancien bytecode importé tant qu'il n'est pas redémarré. Pas un bug de
mon correctif, un artefact de l'environnement de vérification. Comme le
process tourne sur le port 8080 (jamais à redémarrer, consigne permanente),
impossible de le confirmer par ce canal — la preuve est venue de l'import
Python à froid, complémentaire au navigateur, pas substituable par lui.
**How to apply** : pour tout changement PUR BACKEND PYTHON vérifié via le
serveur de dev déjà lancé, ne pas conclure à un bug si le comportement
observé ne reflète pas le code source actuel — importer le module à froid
dans un `python -c` séparé pour trancher entre « bug réel » et « process
serveur pas encore relancé » AVANT de creuser plus loin. Symétrique du piège
déjà documenté côté navigateur ([[piege-cache-navigateur-masque-changement-js]]),
mais côté serveur cette fois — même famille de piège, deux couches différentes.

**Détail mineur noté par l'agent pytest** : `pytest.ini` définit déjà
`addopts=-q -ra` — ajouter `-q` EN PLUS sur la ligne de commande donne
`-qq` chez pytest 9.1.1, qui supprime la ligne de résumé finale (mais
n'affecte aucun test exécuté). Purement cosmétique, sans impact sur la
fiabilité des runs pytest de ce projet, mais explique pourquoi un futur
grep sur "X passed" pourrait échouer silencieusement sur une commande qui
cumule les deux sources de `-q`.

## Voir aussi

[[chantier-audit-complet-9-dimensions-2026-08-09]] (chantier immédiatement
précédent le même jour) — [[piege-min-width-vs-max-width-css]] et
[[piege-conteneur-flex-wrap-partage-composite]] (pièges CSS déjà documentés,
famille voisine : conteneur partagé qui casse une zone qu'on croyait isolée).
