---
name: chantier-onboarding-premiere-visite-2026-08-07
description: "Écran d'accueil (2 questions, première visite CONFIG) livré — merge 36380a2, demandé par F4GLD pour l'intuitivité"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T12:32:58.395Z
---

Demande F4GLD (07/08/2026, en plein milieu d'un autre chantier) : « il
faudra ameliorer l'intuitivite au maximum pouque ca ne devienne pas
inutilisable ou effrayant peutetre mettre en place a la premiere ouverture
2 ou 3 questions pour connaitre le niveau de l'utilisateur et le passer en
mode expert ou debutant ». Inquiétude légitime : la complexité croît vite
(SO2R, CAT propriétaire, panadapter...) et rien ne guidait un tout nouvel
utilisateur.

**Découverte avant d'implémenter** : le logiciel avait déjà DEUX
mécanismes pertinents, mais tous les deux silencieux :
- `getUiMode()` devinait déjà débutant/expert (aucun indicatif configuré =
  débutant) — jamais expliqué, juste deviné.
- Le sélecteur **MODE D'UTILISATION** (simple/contest/expedition/radioclub)
  existait déjà tout en haut de CONFIG — c'était en réalité déjà la
  question « qu'est-ce qui t'amène ? ».

Décision via AskUserQuestion : F4GLD a choisi l'**écran d'accueil séparé**
plutôt que d'intégrer discrètement la question au flux existant (option que
j'avais recommandée pour son coût zéro) — plus visible/pédagogique assumé
comme préférable à moins d'étapes.

**Livré** (`36380a2`) : `#onboardingOverlay` (réutilise le style
`.cat-modal` existant pour la cohérence visuelle), 2 questions à choix
(pas de texte libre) :
1. Expérience préalable (N1MM+/Win-Test/DXLog...) → pose `rc_ui_mode`.
2. Usage visé → reporte DIRECTEMENT sur le `<select id="usage_mode">`
   existant (pas une 3e question redondante).

Lien « Passer, je choisirai moi-même » qui ferme SANS rien figer (retombe
sur l'heuristique silencieuse existante plutôt que de forcer une valeur
au hasard). `await maybeShowOnboarding()` ajouté en toute première ligne de
`init()`, avant `applyUiMode()` — jamais reposé une fois `rc_ui_mode`
présent en localStorage (y compris pour les utilisateurs déjà passés par
l'ancienne heuristique silencieuse avant l'ajout de cet écran).

**Bug réel trouvé par la suite de tests EXISTANTE, pas par moi** :
`test_vocabulaire_portable.py` a fait échouer le premier commit — j'avais
copié "activation portable" depuis un raisonnement par analogie au lieu du
texte RÉEL du sélecteur `usage_mode` (qui dit juste "EXPÉDITION / PORTABLE",
sans "activation") — "activation"/"activateur" est un mot interdit dans ce
projet depuis [[feedback-vocabulaire-radioamateur]] (30/07/2026). Corrigé
avant le commit final. Rappel utile : même un texte d'apparence anodine,
recopié de mémoire plutôt que du fichier source exact, peut réintroduire un
piège déjà documenté — la suite de tests existante a fait exactement son
travail ici.

**Vérification navigateur** : au-delà des clics de fonction directs, un
test au `.click()` réel sur les éléments DOM (pas juste l'appel direct des
fonctions JS) a confirmé que l'attribut `onclick` déclenche bien le même
comportement — plus rigoureux qu'un simple appel de fonction en console,
plus proche d'un vrai clic utilisateur.

13 tests py_mini_racer (même motif que
`tests/test_config_popup_backdrop_click.py`), y compris la gestion de la
Promise `maybeShowOnboarding()` (motif de `test_config_html_sota_qrz_race.py`
: capturer le `resolve`, vérifier qu'il n'est PAS déjà résolu, puis résoudre
manuellement + `ctx.eval("undefined")` pour vider la microtask queue).
