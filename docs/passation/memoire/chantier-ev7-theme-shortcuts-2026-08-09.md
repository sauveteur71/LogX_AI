---
name: chantier-ev7-theme-shortcuts-2026-08-09
description: EV-7 22e incrément — extraction Thème jour/nuit + raccourcis clavier vers logx_theme_shortcuts.js (09/08/2026, fusionné dfce887) — piège du bloc extrait par sous-chaîne, revue adversariale à 0 constat
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T00:25:12.980Z
---

22e incrément de la campagne EV-7, DERNIER de la liste des 6 candidats
FAIBLE-risque identifiés par l'inventaire du 16e incrément
([[inventaire-ev7-16e-candidat-2026-08-08]]) — extraction du bloc TOGGLE
JOUR/NUIT + RACCOURCIS CLAVIER GLOBAUX de `logx_logbook.js` (lignes
originales 4723-4867) vers `concours/logx_theme_shortcuts.js`, chargé en
`<script>` classique juste après `logx_locator_reverse.js`, avant
`logx_logbook.js`. Contenu : `toggleTheme()`, `toggleShortcutsHelp()`, une
IIFE auto-exécutée `(function applyTheme(){...})()` (thème au chargement —
sans rapport avec la fonction homonyme totalement indépendante de
`logx_statusbar.js`, portée lexicale différente, aucune collision malgré le
nom identique), `_modaleOuverte()`, et le gros écouteur
`document.addEventListener('keydown', ...)` (macros F1-F8, Search&Pounce,
SO2R, F9, Échap, ?, Ctrl+Z, Ctrl+F, Entrée). Branche
`feat/ev7-extract-theme-shortcuts`, commit contenu `85c6c2d`, fusionné sur
`main` en `dfce887`.

**Grep exhaustif avant extraction : zéro appel top-level en jeu**, contrairement
aux 19e/20e incréments. Les 4 identifiants exportés ne sont référencés nulle
part ailleurs (ni logx_logbook.js, ni fichiers déjà extraits, ni HTML hors
attributs `onclick=`).

**Piège trouvé — encore une 3e classe distincte de dépendance cachée,
découverte uniquement par exécution réelle de la suite pytest complète** :
`test_macros_au_clavier.py` extrayait le bloc F1-F8 DIRECTEMENT du texte
source de `logx_logbook.js` par recherche de sous-chaîne
(`src.index("if(/^F[1-8]$/.test(e.key)")`), et non par référence à un
symbole nommé — donc invisible à TOUT grep d'identifiant. Une fois le bloc
physiquement déplacé, `src.index(...)` levait `ValueError: substring not
found`, faisant échouer les 20 tests de ce fichier d'un coup. Corrigé en
ajoutant une constante `THEME_SHORTCUTS_JS` et en repointant `_source_js()`
vers le nouveau fichier ; la constante `JS` (devenue inutilisée) a été
retirée et le docstring d'en-tête mis à jour.

**Bilan des 3 classes de dépendance cachée découvertes sur les incréments
16-22, aucune détectable par un seul réflexe universel** :
1. Appel TOP-LEVEL restant dans `logx_logbook.js` vers un symbole déplacé
   ([[piege-appel-top-level-casse-tests-hote-entier]], 19e/20e incréments)
   — détectable par grep du symbole + vérification "à la racine vs dans une
   fonction".
2. Appel en CORPS DE FONCTION depuis le cœur (ex. `clearForm()`), exercé
   uniquement par un scénario de test qui simule le flux réel (21e
   incrément) — indétectable par grep seul, seule l'exécution de la suite
   pytest complète le révèle.
3. Extraction de bloc par RECHERCHE DE SOUS-CHAÎNE/TEXTE dans un test dédié
   (22e incrément, ce chantier) — indétectable par grep d'identifiant
   puisque ce n'est pas une référence à un symbole nommé ; seule
   l'exécution de la suite complète le révèle aussi.

**Conclusion méthodologique pour la suite de la campagne** : le grep
proactif des symboles top-level reste une bonne première passe (gratuite,
rapide), mais NE REMPLACE JAMAIS le lancement de la suite pytest complète
après extraction — c'est le seul filet qui couvre les 3 classes à la fois.

Revue adversariale Workflow (2 dimensions, prompts durcis pour ne remonter
que les vrais correctifs actionnables) : **0 constat, la revue la plus
propre de la campagne** — confirmant que le grep proactif + la suite pytest
complète, appliqués rigoureusement, suffisent à fiabiliser un incrément
avant même la revue.

Vérification navigateur : `toggleTheme()`/`toggleShortcutsHelp()` existent
en portée globale réelle ; dispatch d'un vrai événement `keydown` avec
`key:'?'` déclenche bien l'overlay d'aide ; `toggleTheme()` bascule bien
`body.classList.day-mode` ; aucune erreur console liée à
"theme"/"shortcut"/"keydown" après hard-reload.

**Suite de la campagne** : les 6 candidats FAIBLE-risque de l'inventaire du
16e incrément sont désormais tous extraits (Callbook, Lookup, Daynight,
ESM/Callbot, Voice Keyer, Reverse Lookup Locator+Compas, Theme+Shortcuts —
en réalité 7, le décompte initial de "6 FAIBLE" a été légèrement sous-estimé).
Pour un 23e incrément, il faudra soit relancer un inventaire Workflow
complet (comme au 16e incrément) pour recartographier ce qu'il reste dans
`logx_logbook.js`, soit reprendre la liste MOYEN de l'inventaire (numéros
de ligne tous périmés après 7 extractions cumulées depuis le 16e — à
relocaliser par grep de fonctions, pas par ligne).
