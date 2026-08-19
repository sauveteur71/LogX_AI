---
name: chantier-designer-carte-qsl-2026-08-10
description: "Designer de carte QSL imprimable minimal (canvas, export PNG/JPG), dernier P1 de l'audit concurrentiel — PR #14, workflow implémentation+revue adversariale"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-10T10:29:07.788Z
---

Suite de [[analyse-concurrence-logx-ai-2026-08-10]] (dernier P1 restant : Wavelog/
Log4OM/GridTracker2 ont tous un designer de carte QSL, LogX AI n'en avait aucun).
PR #14, mergée le 10/08/2026. Implémenté via Workflow (1 agent implémentation +
3 agents de revue adversariale en parallèle : correction/sécurité, design/
intuitivité, cohérence des tests).

**Décision de scope prise AVANT le codage, pas par l'implémenteur** : pas de
nouvelle page top-level (aurait dupliqué la nav sur 11 fichiers .html, piège
documenté dans `tests/test_page_chasse_split.py`) — panneau DANS LOGBOOK, sur
le modèle exact de `showAwards()`/`#awardsOverlay` (logx_awards.js), ouvert
depuis le menu ☰ DÉBUT/FIN. Rendu **100% client-side** (canvas 2D 1500×1000,
2 gabarits), **aucun endpoint serveur** — toutes les données existaient déjà
côté client (`qsoLog`, `myCall`/`myLocator`, `/config`).

**Direction design assumée** : le CADRE de l'overlay suit le thème sombre
graphite&cuivre habituel (réutilise `.shortcuts-overlay`/`.shortcuts-box`
tel quel) ; le `<canvas>` lui-même imite une VRAIE carte imprimée sur papier —
fond crème `#F7F3EA` FIXE, filet cuivre `#8B4F1F` (teinte JOUR de --accent)
FIXE, indépendant du thème actif de l'interface. Raisonnement : c'est un objet
imprimable, pas un écran HUD — même logique que refuser d'appliquer le thème
sombre à un document destiné à sortir sur papier blanc.

## Bug réel trouvé par la revue adversariale (pas par moi, pas par l'implémenteur)

**[MAJEUR]** La carte affichait l'indicatif ACTUEL de la session
(`myCall` global) plutôt que celui RÉELLEMENT utilisé pendant CE QSO
(`q.my_call`). `qsoLog` est filtré par PORTÉE (concours+année), pas par
indicatif — un opérateur portable qui change d'identité dans la même journée
(F4GLD/P → F4GLD/M, nouveau SETUP) voit cohabiter dans le même log des QSO
faits sous des indicatifs différents. Le code voisin (`myLocator`) gérait
DÉJÀ correctement ce cas (`q.my_locator || myLocator`) — l'indicatif, lui,
avait été oublié. Corrigé (`q.my_call || myCall || ...`), et le calcul des
données de la carte extrait en fonction PURE `_qslBuildCardData(q, rawMsg)`
pour être testable indépendamment du canvas (le stub `<canvas>` des tests JS
ne fournit pas de vrai contexte 2D — `getContext()` renvoie `null` dans le
DOM minimal, donc les fonctions de dessin ne s'exécutent JAMAIS dans les
tests : toute logique qu'on veut couvrir doit être extraite AVANT l'appel à
`getContext`).

**[MINEUR]** Champ de recherche de QSO non réinitialisé à la réouverture du
panneau (texte d'une session précédente affiché alors que la liste, elle,
repart complète) — corrigé en vidant le champ dans `showQslCardDesigner()`.

## Piège d'accessibilité confirmé une 2e fois (pas nouveau, déjà documenté)

`concours/logx_theme_shortcuts.js` a EN RÉALITÉ **3 listes** distinctes à
tenir à jour pour qu'un nouveau panneau/overlay soit pleinement accessible,
pas 2 comme documenté jusqu'ici (voir chantier accessibilité du 09/08) :
`_elementModaleOuverte().ids` (Échap + neutralisation macros F1-F8),
`watchedIds` (focus automatique à l'ouverture), ET une **3e liste cachée** :
le handler Échap lui-même contient un bloc `classList.remove('show')`
CODÉ EN DUR par overlay plutôt que d'itérer sur `ids` — sans l'ajout manuel
à CE bloc précis, Échap ne fait RIEN sur le nouveau panneau (silencieux,
aucune erreur JS). Trouvé par l'implémenteur en testant Échap en navigateur
réel, pas par lecture de code. **Réflexe pour tout nouveau panneau/overlay
futur** : chercher les 3 occurrences de l'ID du panneau dans
`logx_theme_shortcuts.js`, pas seulement les 2 tableaux `ids`/`watchedIds`.

## Piège de vérification CI (faux négatif transitoire)

`gh pr checks <N>` a affiché « pending » alors que le run était déjà terminé
et VERT — l'annotation `X Process completed with exit code 1` visible dans
les logs du job « Tests + validation schema + harnais mock » est un
faux-positif TROMPEUR : elle correspond au harnais d'éval IA qui tente
d'ouvrir `reg_rph_fr_20250312.pdf` (référencé en dur dans
`concours/logx_eval.py` CORPUS, volontairement dans `.gitignore` — règlement
personnel de F4GLD, jamais commité) — absent par construction sur GitHub
Actions, mais cette étape est non-bloquante pour la conclusion du job
(vérifié : la MÊME annotation est présente sur les 2 derniers runs `main`
réussis). Le signal fiable n'est PAS `gh pr checks` seul mais
`gh pr view <N> --json state,mergeable,statusCheckRollup` ou le ✓ en tout
début de ligne de `gh run view <id>` — à réutiliser si ce faux négatif
réapparaît sur une PR future.
