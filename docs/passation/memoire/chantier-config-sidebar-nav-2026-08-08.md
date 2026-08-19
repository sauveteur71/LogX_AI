---
name: chantier-config-sidebar-nav-2026-08-08
description: "Refonte CONFIG en arborescence de réglages permanente façon OpsLog (merge ace73e7) — revue adversariale Workflow a trouvé 5 constats dont 1 CRITIQUE (nav/LOGBOOK recouverte, exactement le défaut que le chantier visait à corriger) ; ma propre vérification initiale l'avait manqué en ne testant qu'un seul point de la nav"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T11:44:45.325Z
---

Chantier livré et fusionné sur `main` le 08/08/2026 (commit `ace73e7`, merge
de `feat/config-sidebar-nav`, commits de contenu `35a6190` + `80ff151`).

## Origine

F4GLD a demandé "lance sidebar config" — feu vert explicite pour le point 1
(différé) de la revue OpsLog du chantier [[chantier-n1mm-rename-masterscp-fetch-2026-08-08]].
Investigation préalable en 3 agents (mécanique existante, pièges/dépendances,
inventaire des 19 catégories) AVANT tout code, plan présenté et confirmé par
F4GLD avant implémentation — consistant avec la pratique établie pour tout
gros chantier de cette session.

## Ce qui a changé

Remplace le système "hub de cartes cliquables + popup plein écran par
catégorie (overlay noir `.cat-modal{position:fixed;inset:0}`)" par une
arborescence de réglages PERMANENTE (`#configSidebar`, toujours montée) +
un panneau de contenu docké (`.cat-modal-box`, `position:fixed`, plus de
backdrop) — un seul panneau visible à la fois, plus de retour à un "hub"
qui n'existe plus. Les ~2300 lignes de contenu des 19 popups de catégorie
(+1 "Résumé" fusionnée comme 20e entrée) n'ont PAS bougé dans le fichier :
seule leur CSS/position a changé, pas leur position dans le DOM — évite le
risque d'une relocalisation massive.

Points clés :
- `openCategoryPopup(cat)` ferme la section précédente (via `_currentOpenCat()`)
  avant d'ouvrir la cible, garde `_confirmDiscardCatChanges()` peut annuler
  tout le switch.
- `closeCategoryPopup()`/`closeConfigPopup()`/`bindCatModalBackdropClose()`/
  `openSummaryPopup()`/`closeSummaryPopup()` supprimées entièrement (plus de
  backdrop à cliquer, plus de hub où "revenir", Résumé fusionnée dans
  CONFIG_SECTIONS comme 20e entrée — élimine le risque de coexistence avec
  une catégorie, protégé avant seulement par accident via l'overlay disparu).
- `_EXPERT_ONLY_CATS` (relay/autostart/pgxl/telemetry) appliqué à CHAQUE
  entrée de l'arborescence — lacune trouvée par l'investigation : l'ancien
  panneau flottant listait les 19 catégories sans filtre.
- `renderHub()` renommée `renderConfigTree()`, itère `CONFIG_SECTIONS`
  DIRECTEMENT (plus de 2e liste dupliquée — cause d'un bug déjà corrigé une
  fois pour 'relay', voir [[chantier-cat-proprietaire-omnirig-flex-pgxl-icomremote-2026-08-06]]).
- `goStep()`/`state.step` (ancien assistant par étapes, déjà mort depuis la
  migration hub/popups) purgés, + refs DOM mortes #step4/#panel3/#panel5/
  #step2/#btnStep1Next/#btnStep3Back.
- 20 boutons "Fermer" retirés (script Python regex, mécanique et sûr — plus
  de sens dans un panneau permanent) ; `saveConfigAndClose()` renommée
  `saveCategoryPanel()`, ne ferme plus rien.
- Panneau "Identité" ouvert par défaut au chargement (plus de hub d'accueil).

## 5 constats CONFIRMÉS par la revue adversariale Workflow (PAS par moi)

Revue à 4 dimensions en parallèle (mécanique ouverture/fermeture, purge de
code mort, CSS/layout, couverture de tests) + vérification indépendante de
chaque constat — 6 constats bruts, 5 confirmés (1 doublon entre 2 agents
sur le même bug) :

1. **[CRITIQUE] Nav/statusbar recouvertes par le panneau permanent** —
   `.cat-modal-box`/`.config-sidebar` en `top:6%` (relatif au viewport) ne
   tenaient pas compte de la hauteur RÉELLE de header+nav+statusbar (~200px
   en flux normal à 1366×768, largement > 6%). LOGBOOK et le reste de la
   nav étaient structurellement inatteignables au clic — violation directe
   de la règle CLAUDE.md "chemin critique jamais cachable", **exactement le
   défaut que ce chantier visait à corriger**. Corrigé par une position
   dynamique mesurée en JS (`--config-panel-top`, mise à jour par
   `ResizeObserver` — la statusbar est injectée après un fetch async et
   `flex-wrap:wrap` donc sa hauteur n'est PAS fixe) plutôt qu'un pourcentage
   de viewport deviné.
2. **[MAJEUR]** Re-cliquer l'entrée déjà active de l'arborescence effaçait
   silencieusement le marqueur de modifications non enregistrées (le
   `_catFormSnapshots[cat] = ...` final de `openCategoryPopup()` s'exécutait
   inconditionnellement même quand `cat === catégorie déjà ouverte`). Avec
   la sidebar permanente et toujours cliquable (contrairement à l'ancien hub
   caché derrière la popup), ce geste est devenu courant. Corrigé par un
   early-return no-op explicite.
3. **[MINEUR]** CSS mort `.steps`/`.step`/`.panel` (ancien assistant par
   étapes) laissé en place malgré `goStep()`/`state.step` déjà purgés dans
   le même commit — retiré.
4. **[MAJEUR]** `.cat-modal-box` sans `min-width` ni repli `@media` —
   largeur nulle/négative possible sous ~254px de large. `min-width:300px`
   ajouté.
5. **[MAJEUR]** `buildConfigSidebar()`, désormais SEUL mécanisme de
   navigation entre catégories, sans AUCUNE couverture de test réelle (son
   appel est enveloppé dans un `try/catch` vide préexistant, avalé par le
   DOM minimal des tests qui n'ont pas `createElement`/`body`). Ajout de 4
   tests avec un DOM stub FONCTIONNEL (`createElement` + parseur regex
   volontairement simple pour `innerHTML`) qui exécutent le VRAI
   `CONFIG_SECTIONS`/`_EXPERT_ONLY_CATS`/`buildConfigSidebar()` et vérifient
   le HTML réellement généré — pas seulement sa présence littérale dans la
   source.

## Leçon la plus importante : ma propre vérification navigateur du constat #1 était fausse

Avant la revue adversariale, j'avais testé la nav en navigateur et conclu
qu'elle était accessible — **en ne testant qu'UN SEUL point** (`elementFromPoint`
sur le lien "CONFIG", le premier de la nav). Ce point tombait PAR HASARD
juste hors de la zone couverte par le panneau (le premier et le dernier lien
de la nav débordent horizontalement de la sidebar/panneau, contrairement aux
9 liens du milieu — dont LOGBOOK). Un seul point de test a donné une fausse
confiance totale. **Généralisation pour toute vérification future de
"élément cliquable derrière un autre" : toujours tester TOUS les éléments
concernés (boucle sur `querySelectorAll`), jamais un seul point
représentatif — surtout quand l'enjeu est un chemin critique (règle
CLAUDE.md "Intuitivité").**

## Reliquat séparé (pas ce chantier)

Pendant la vérification, F4GLD a signalé 2 bugs LOGBOOK sans rapport
(indicatif "OP1" affiché au lieu du vrai indicatif ; export ADIF
STATION_CALLSIGN manquant côté Python) — traités sur une branche séparée,
voir mémoire à venir.
