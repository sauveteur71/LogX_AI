---
name: chantier-audit-trouvabilite-24-correctifs-2026-08-09
description: "Audit trouvabilité/intuitivité (6 dimensions, 30 constats → 24 retenus) + correctifs complets sur demande « corrige tout d'un coup », 09/08/2026 (PR #7, b8ac199)"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T20:23:50.858Z
---

Suite du chantier [[chantier-fix-sidebar-et-filtre-chasse-2026-08-09]] le même
jour : F4GLD a demandé « sur quoi tu peux désormais travailler avec ce maître
mot [intuitivité] » → proposition d'un audit large "trouvabilité" (nav,
recherche, découvrabilité fonctions, onboarding/états vides, icônes, aide
contextuelle) → audit Workflow 6 agents + synthèse → « corrige tout d'un
coup ».

## Méthode

Workflow 6 chercheurs parallèles (un par dimension) + 1 agent de synthèse
dédupliquant/priorisant. 30 constats bruts → 24 retenus (2 critiques, 12
majeurs, 10 mineurs) après élimination de 2 faux positifs vérifiés (bouton
"signaler un problème" en fait fonctionnel ; icônes fonctionnelles déjà
pourvues en title). Exécution : 2 items délégués à des agents Agent tool en
arrière-plan sur des fichiers totalement disjoints (`logx_search.py` par un
agent, `logx_carte.html` par un autre), le reste fait directement par moi en
séquentiel pour éviter tout risque d'édition concurrente sur les fichiers à
forte densité de constats (`logx_configuration.html`, `logx_logbook.html`).

## Les 2 critiques

1. **LOGBOOK identité fictive** — `#setupCallsign`/`#setupLocator` avaient un
   `value="F6KQJ/P"`/`value="JN15XC"` codé EN PLUS du `placeholder=`. Le test
   `if(callEl.value && locEl.value)` de `prefillSetupFromConfig()` était donc
   toujours vrai dès le chargement, la modale de première config ne
   s'affichait jamais, `setupDone()` persistait silencieusement la fausse
   identité. Correctif : retirer les deux `value=`. Test de régression par
   assertion statique sur le HTML (pas de harnais DOM complet) —
   `tests/test_setup_modal_pas_de_fausse_identite.py`.

2. **Recherche quasi inopérante** — `logx_search.py` comparait la requête
   ENTIÈRE comme une seule sous-chaîne (`query_lower in text.lower()`), sans
   découpage en mots, sans normalisation d'accents, sans tri par score, et le
   bloc `<nav>` dupliqué sur 11 pages polluait les résultats en tête. Corrigé
   par l'agent délégué (tokenisation multi-mots + score, normalisation NFD,
   exclusion du `<nav>` de l'indexation, tri décroissant). Vérifié : les 5
   requêtes réalistes de l'audit (« comment exporter mon log »...) donnent
   toutes un résultat pertinent après coup.

## Piège majeur trouvé EN COURS DE ROUTE (hors périmètre de l'audit)

En vérifiant en navigateur mon propre correctif #353 (lien
`logx_configuration.html?openAssistant=1` depuis LOGBOOK), le panneau
assistant refusait obstinément de s'afficher — ou pire, semblait DÉJÀ ouvert
par défaut sur une page fraîchement chargée SANS le paramètre. Après ~45 min
de diagnostic (fausses pistes : cache navigateur, timing DOMContentLoaded,
bfcache, tabs polluées par des tests précédents — toutes écartées une à une
par des tests empiriques ciblés), la cause réelle : la div elle-même,
`<div id="assistantPanel" style="display:none;...;display:flex;...">`,
contient la propriété `display` déclarée DEUX FOIS dans le MÊME attribut
`style=` — en CSS, la dernière déclaration d'une propriété répétée l'emporte,
donc `display:flex` (placé plus loin dans le style, au milieu d'un bloc de
propriétés liées) écrasait silencieusement le `display:none` initial. Le
panneau était donc TOUJOURS visible dès le chargement, sur `main`, depuis
avant le début de cette session — confirmé par `git diff` montrant cette div
comme totalement intacte dans mon diff. Corrigé en retirant le `display:flex`
en trop (un seul `display:none` fait foi, cohérent avec tous les autres
panneaux flottants de l'appli).

**How to apply** : quand un `display.style` lu en JS ne correspond PAS à ce
que le HTML source semble dire, ne pas se fier à une lecture visuelle rapide
du fichier — chercher explicitement une DEUXIÈME occurrence de la même
propriété CSS dans le MÊME attribut `style=` (facile à rater dans un long
style multi-ligne où les propriétés liées sont groupées visuellement, ex.
`display:none;position:fixed;...;width:...;...;display:flex;flex-direction:...`
— le second `display` se noie visuellement dans un groupe de propriétés
"layout" qui n'a rien à voir avec le premier). `element.style.display` (pas
`getAttribute('style')`) est le test décisif — matché avec un
`document.createElement` + `setAttribute('style', rawString)` isolé pour
confirmer sans ambiguïté que c'est bien le PARSING CSS qui tranche, pas un
autre effet de bord.

## Autre confirmation utile

Un des deux agents délégués (`logx_carte.html`), à la fin de son travail, a
lui-même signalé de façon transparente que « d'autres fichiers semblaient
modifiés en parallèle, par une autre session » (en réalité : moi-même,
éditant simultanément le bloc `<nav>` du même fichier pendant qu'il éditait
`applyConfig()`/CSS plus bas). `git diff --stat` après coup a confirmé les
DEUX jeux de changements coexistent sans perte ni corruption — édition
concurrente sur RÉGIONS DISJOINTES du même fichier, par des acteurs
différents (agent vs moi), sans conflit réel. Contraste avec le piège déjà
documenté [[piege-perte-edition-synologydrive-agents-paralleles]] : ce
piège-là concernait des agents éditant la MÊME région/contenu en parallèle —
ici les régions ne se recouvraient pas, donc pas de perte. **How to apply** :
le risque SynologyDrive documenté n'interdit pas toute édition concurrente
sur un même fichier — seulement la même RÉGION DE TEXTE. Des agents/humains
touchant des sections clairement disjointes d'un même gros fichier (nav en
haut vs logique JS plus bas) peuvent coexister sans souci, à condition de
vérifier après coup via `git diff --stat`/relecture, pas de le supposer.

## Voir aussi

[[chantier-fix-sidebar-et-filtre-chasse-2026-08-09]] (chantier précédent le
même jour, même session) — [[piege-cache-navigateur-masque-changement-js]]
(fausse piste explorée avant de trouver le vrai bug) —
[[piege-perte-edition-synologydrive-agents-paralleles]] (nuance apportée
ci-dessus : région disjointe ≠ risque de perte).
