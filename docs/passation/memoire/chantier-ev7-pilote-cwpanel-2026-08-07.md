---
name: chantier-ev7-pilote-cwpanel-2026-08-07
description: "Premier pilote du refactor EV-7 livré — composant CwPanel unifié éliminant ~150 lignes dupliquées radio1/radio2 dans logx_logbook.js, patron établi pour la suite"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T17:57:31.584Z
---

Chantier livré et fusionné sur `main` le 07/08/2026 (commit `c88b5c2`, merge
de `feat/ev7-refactor-pilote-panneau-cw`, commit de contenu `257a443`).

## Contexte de la décision

Après "[[chantier-ev7-filet-securite-2026-08-07]]" (le filet de sécurité,
livré puis étendu), F4GLD a dit « lance » — interprété comme feu vert pour
le VRAI refactor EV-7 (extraction de la logique métier hors présentation).
Le PRD lui-même interdit la réécriture Big Bang : approche par pilote borné
plutôt qu'un chantier monolithique sur les ~18000 lignes de
`logx_configuration.html` (8982) + `logx_logbook.js` (9193).

Cible choisie : le panneau décodeur CW, dupliqué intégralement radio1/radio2
depuis SO2R Phase 2 (6 fonctions + 6 variables d'état, ~150 lignes quasi
identiques, suffixe "2") — cas d'école du "composant panneau unifié" que le
PRD demande.

## Ce qui a été livré

`concours/logx_cw_panel.js` (nouveau) : classe `CwPanel` paramétrée par un
suffixe d'id DOM (`''`/`'2'`), méthodes `toggle()`/`loadDevices()`/
`setFreq()`/`toggleDecoder()`/`clearOutput()`. Le pipeline DSP
(`CwAudioDecoder`, `logx_cwdecoder.js`) était déjà bien séparé — CwPanel ne
fait QUE le branchement UI, comme avant.

`logx_logbook.js` : les 6 fonctions dupliquées disparaissent, remplacées par
des wrappers globaux fins (mêmes noms/arités qu'avant — aucun changement
côté HTML `onclick=` ni côté tests existants).

## Piège trouvé et corrigé PENDANT ce chantier (pas par l'audit après coup)

Première version : instanciation IMMÉDIATE (`const _cwPanels = {'':new
CwPanel(''), ...}`) au chargement du script. Résultat : 65 tests échouaient
d'un coup dans la suite complète — pas des tests CW, mais
`test_rph_weekend_fallback.py`, `test_notify_dynamic_i18n.py`,
`test_export_adif_client_bande.py` et une dizaine d'autres, qui évaluent
`logx_logbook.js` isolément (leur propre harnais `py_mini_racer`, sans
`logx_cw_panel.js`) — un `new CwPanel()` immédiat plantait leur simple
chargement du script avec une `ReferenceError`, avant même d'atteindre le
code qu'ils testaient réellement.

**Corrigé en rendant l'instanciation PARESSEUSE** (`_cwPanel(suffix)`, ne
crée les instances qu'au premier appel réel) plutôt qu'en touchant une
douzaine de fichiers de test sans rapport avec ce chantier — solution plus
sûre ET meilleure pratique générale (pas d'effet de bord global au chargement
du module). Réflexe pour toute suite d'EV-7 : **avant tout nouveau fichier
JS partagé, se demander s'il introduit un effet de bord au chargement du
script (instanciation immédiate, appel de fonction top-level) — s'il en a
un, il cassera potentiellement TOUS les harnais de test qui évaluent le
fichier appelant en isolation, même sur des tests sans aucun rapport.**

## Vérification (3 couches)

1. Suite pytest complète, 3 passes (1re avec le bug d'instanciation eager →
   65 échecs ; 2e après correctif → verte ; 3e après corrections mineures de
   doc → verte).
2. Navigateur réel (serveur prod, lecture seule) : ouverture/fermeture du
   panneau, `setFreq()` sans décodeur actif, pont de compatibilité
   `_cwOutText`/`_cwOutText2` (`Object.defineProperty`, nécessaire car
   `tests/test_cw_panel_consolidation.py` — un test PRÉEXISTANT, sur un
   tout autre bug de layout, écrit avant ce chantier — lit/écrit cette
   variable directement).
3. Revue adversariale par Workflow (2 agents parallèles, ultracode actif) :
   équivalence comportementale ligne à ligne (`git show main:...` pour
   comparer à l'ancien code) + recherche exhaustive de références oubliées
   dans tout le dépôt (pas seulement les fichiers déjà touchés). Aucune
   divergence de comportement trouvée ; 2 détails documentaires mineurs
   corrigés (commentaire de test décrivant à tort une instanciation eager
   après le correctif — contradiction avec ma propre conception ; référence
   obsolète à `_cwAudioDecoder` dans `docs/ETUDE_SO2R.md`).

## Reliquat

Le refactor EV-7 complet n'a fait qu'un pas : reste ~17800 lignes à traiter
(les ~15 autres panneaux de LOGBOOK — macro CW/vocal/RTTY, filtre avancé,
recherche de doublons, re-résolution en masse, contrôle de net, station
control — et les popups de CONFIG). Le patron est établi : composant
paramétré + wrappers globaux fins + instanciation paresseuse + vérification
en 3 couches (suite complète, navigateur, revue adversariale).
