---
name: piege-couleur-data-vs-theme
description: "Un hex identique à l'accent du thème peut être une DONNÉE de code-couleur sans rapport — vérifier le contexte de chaque occurrence avant un grep-replace"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-03T09:22:27.244Z
---

Lors du chantier de refonte graphique (passage du duo cyan/orange-red à un
accent cuivre unique, cf. [[chantier-design-graphite-cuivre-2026-08]]), un
grep sur les anciens hex `#00D4FF`/`#FF5030` dans `logx_configuration.html`
et `logx_logbook.html` remontait des dizaines d'occurrences — mais une
bonne moitié n'étaient PAS le thème de l'appli : ce sont des systèmes de
code-couleur PAR CATÉGORIE qui réutilisent par coïncidence les mêmes teintes
que l'ancien accent :
- `groupColors` dans `logx_configuration.html` : couleur par GROUPE de
  concours (REF=cyan, International=orange-red...) affichée sur les cartes
  de la liste des concours.
- `.op-1` à `.op-5` dans `logx_logbook.html` : couleur par OPÉRATEUR en mode
  multi-op (op-1=orange-red, op-2=cyan, op-3=violet...).
- Légende de carte QSO par BANDE (144 MHz=cyan, 432 MHz=orange...).

**Pourquoi c'est un piège** : ces trois systèmes sont de VRAIS composants
fonctionnels (distinguer visuellement plusieurs concours/opérateurs/bandes
à l'écran), pas de la déco liée au thème. Un remplacement en masse (sed
global sur le hex) les aurait tous fait converger vers la même couleur,
détruisant silencieusement la distinction qu'ils encodent — sans qu'aucun
test ne le voie (ce sont des couleurs, pas des valeurs testées).

**Comment l'éviter** : après un grep, lire le CONTEXTE de chaque groupe de
résultats avant de toucher quoi que ce soit — un hex isolé dans une règle
CSS de bouton/bordure/glow est presque toujours le thème ; un hex qui
apparaît comme valeur d'un champ nommé `color:` à l'intérieur d'un objet de
données (concours, opérateur...), ou dans une table de correspondance
`{'GroupeA': hex1, 'GroupeB': hex2}`, est presque toujours une donnée de
catégorisation à laisser intacte. Un `grep -c` seul ne suffit pas à estimer
l'ampleur réelle d'un remplacement — il faut lire un échantillon de chaque
famille de résultats.
