---
name: chantier-audit-accessibilite-24-correctifs-2026-08-09
description: "Audit accessibilité (6 dimensions, 38 constats → 23 retenus) + correctifs complets en session autonome nocturne, 09/08/2026 (PR #8, bedfdfe) — 3 bugs réels trouvés par la revue adversariale avant fusion"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T21:31:24.550Z
---

Chantier mené en **session autonome nocturne** (F4GLD parti se coucher, consigne
« bosse jusque là si tu as de quoi faire ») juste après avoir mergé la PR #7
(audit trouvabilité, voir [[chantier-audit-trouvabilite-24-correctifs-2026-08-09]]).
Décision prise seul : lancer un audit sur la dimension **accessibilité**
(clavier, ARIA, contraste, sémantique HTML, focus visible, formulaires/erreurs)
— jamais couverte par les audits précédents du projet (sécurité, qualité,
trouvabilité). Méthode identique : Workflow 6 chercheurs parallèles + 1 agent
de synthèse, 38 constats bruts → 23 retenus (5 critiques, 12 majeurs, 6 mineurs).

## Constats critiques les plus importants

1. **LOGBOOK : le formulaire de saisie QSO (le plus utilisé du logiciel) n'avait
   AUCUN label associé** sur ses 11 champs (indicatif, RST, numéros, locator,
   bande/mode/opérateur, fréquence, réf.). Un lecteur d'écran annonçait
   « champ vide » sans dire lequel. Corrigé en convertissant chaque
   `<div class="field-label">` en `<label for="...">` (le CSS `.field-group`
   étant déjà `display:flex`, la conversion div→label est neutre visuellement).
2. **CONFIG et LOGBOOK n'avaient AUCUNE balise de titre HTML** (h1-h6) — 65
   titres visuels (`.cat-modal-title` en `<span>`, `.section-title` en `<div>`)
   convertis en h2/h3 réels via script Python (regex non-greedy, vérifié
   équilibre ouvertures/fermetures après coup).
3. **6 panneaux** (net/qtc/filtre/doublons/checklist/taux) ne se fermaient ni
   à Échap ni au clavier — ajoutés à `_modaleOuverte()` et au handler Escape
   de `logx_theme_shortcuts.js`, en appelant leur fonction `close*()` dédiée
   quand elle existe (nettoyage associé conservé, ex. destruction du
   graphique du panneau taux).

## Méthode d'exécution (paquets A-E)

Comme pour le chantier trouvabilité : paquets par fichier/risque, 1 agent en
arrière-plan sur les fichiers totalement disjoints (`logx_hardware_cat.js`,
`logx_edit_qso.js`, `logx_scan_qsl.js`, `logx_panel.html` — 4 correctifs
indépendants, rapport final tronqué mais diff vérifié directement, exact et
conforme aux instructions), le reste fait séquentiellement par moi
(`logx_theme_shortcuts.js`, `logx_logbook.html`, `logx_configuration.html`,
+ script Python appliqué uniformément aux 17 pages pour les tokens CSS
partagés `--muted`/`--border`/règle `focus-visible` générique).

**Piège de test découvert pendant l'exécution** : `buildConfigSidebar()`
utilisait `nav.setAttribute('aria-label', ...)` en premier jet — a cassé 4
tests (`test_config_category_switch.py`) car le faux DOM de test
(`makeFakeNav()`) n'implémente pas `setAttribute`. Corrigé en utilisant
`nav.ariaLabel = '...'` (propriété directe, reflétée par ARIAMixin, Baseline
"widely available" depuis 2023-2024 — largement suffisant puisque
`logx_bootstrap.py` lance toujours le Chrome/Edge réellement installé sur la
machine, jamais un Chromium embarqué figé). Confirmé par la revue
adversariale comme un choix délibéré et sûr, pas un oubli.

## Décision de scope : ce qui a été DÉLIBÉRÉMENT reporté

Deux constats critiques/majeurs de l'audit — remplacer les `alert()`/`confirm()`
bloquants (validation CONFIG au save, doublon QSO en LOGBOOK) par des bandeaux
non bloquants — ont été **volontairement exclus** de ce chantier : ce sont des
changements de comportement établi (pas de purs ajouts), avec un vrai risque
de régression sur le chemin critique (sauvegarde CONFIG, enregistrement QSO),
jugés trop risqués à faire sans supervision humaine en pleine nuit. Documenté
dans le commit et le corps de PR comme « chantier 2 » à faire séparément.
**How to apply** : en session autonome sans supervision, distinguer purs
ajouts (labels, roles ARIA, title, tabindex — zéro risque de régression
fonctionnelle) des changements de flux d'interaction établis (remplacer un
mécanisme de blocage existant) — ne faire les seconds qu'avec plus de temps
dédié aux tests, ou avec l'utilisateur disponible pour trancher.

## Le plus gros bug trouvé par la revue adversariale (pas par moi)

**Le piège de focus Tab/Shift+Tab que j'avais ajouté ne s'activait JAMAIS en
pratique**, pour 10 des 11 modales couvertes (seule `editOverlay` fonctionnait,
car `editQSO()` appelle déjà `.focus()` sur un champ interne). Aucune des
fonctions d'ouverture (`showQTCPanel()`, `openDupFinder()`, `showChecklist()`...)
ne posait de focus initial DANS la modale — donc `document.activeElement` au
premier Tab n'appartenait jamais à la liste `focusables` calculée par le
piège, et les conditions `activeElement===first/last` ne matchaient jamais.
Un correctif entier resté silencieusement inopérant, malgré une vérification
navigateur qui avait pourtant testé le piège... **mais en positionnant le
focus manuellement par script AVANT de tester** (`last.focus()` avant de
simuler Tab) — ce qui masquait exactement le problème que la revue a trouvé
(dans un usage réel, rien ne pose ce focus initial). **How to apply** : quand
on teste un piège de focus, ne JAMAIS positionner soi-même le focus de départ
par script — ouvrir la modale par sa VRAIE fonction d'ouverture et vérifier
où le focus atterrit naturellement, sinon le test valide la mécanique du
piège mais pas la condition réelle qui doit l'amorcer.

**Corrigé par un point central** (pas en patchant 10 fonctions dans 8
fichiers) : un `MutationObserver` générique dans `logx_theme_shortcuts.js`
qui observe l'attribut `class` de chaque overlay connu et focus son premier
élément focusable dès que `.show` est ajouté — `editOverlay` explicitement
exclu de la liste (sinon le MutationObserver, qui se déclenche en microtask
APRÈS le `.focus()` explicite d'`editQSO()` sur `editCall`, aurait volé le
focus vers le bouton de fermeture, une régression silencieuse du comportement
déjà correct).

## Autres bugs réels trouvés par la revue

- **`fixFromValidation()`** (ouvrir « corriger » depuis le panneau VÉRIFIER)
  cassait le focus-restore de `closeEdit()` : elle fait
  `validateOverlay.classList.remove('show')` (retire `display:flex` de
  l'ancêtre du bouton focus) **avant** d'appeler `editQSO(id)` — le navigateur
  blur() synchroniquement le bouton vers `<body>` dès que son ancêtre devient
  masqué, donc `editQSO()` capturait `<body>`, pas le vrai déclencheur.
  Corrigé en capturant `document.activeElement` AVANT de masquer l'overlay,
  et en le passant en paramètre optionnel de repli à `editQSO(id, triggerEl)`.
- **`.sr-only` (position:absolute) posé directement sur un `<th>`** casse la
  structure du tableau : `position:absolute` blockifie tout
  `display:table-cell` en `display:block` (spec CSS Display), le `<th>` sort
  de la grille et perd son association de colonne dans l'arbre d'accessibilité
  — un lecteur d'écran ne l'associe plus à sa colonne, RIEN dans une
  vérification visuelle navigateur ne le révèle (le texte était déjà invisible
  avant/après). **How to apply** : ne jamais poser `.sr-only` (position:absolute)
  directement sur une cellule de tableau — l'imbriquer dans un `<span>` À
  L'INTÉRIEUR du `<th>`/`<td>`.

## Voir aussi

[[chantier-audit-trouvabilite-24-correctifs-2026-08-09]] (chantier précédent
le même jour, même méthode) — [[piege-faux-dom-stub-et-passes-paires]]
(nuance ariaLabel vs setAttribute, même famille de piège que documenté avant)
— [[piege-verifier-sur-donnees-reelles]] (même famille : tester un mécanisme
avec un état posé artificiellement par script masque la vraie condition
d'amorçage, ici le piège de focus).
