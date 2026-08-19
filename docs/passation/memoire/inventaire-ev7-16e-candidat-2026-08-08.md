---
name: inventaire-ev7-16e-candidat-2026-08-08
description: "EV-7 : inventaire Workflow complet (35 blocs, 31 évalués) pour identifier le 16e candidat d'extraction — recommandation Callbook (L954-1128), 4 candidats ÉLEVÉ à éviter documentés avec raisons précises"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T19:08:50.514Z
---

Demandé explicitement par F4GLD ("nouvel inventaire Workflow complet pour
identifier un 16e candidat") après épuisement des 2 candidats FAIBLE risque
de l'évaluation initiale (RTTY, SSTV — cf. [[chantier-ev7-rtty-panel-2026-08-08]]).
Workflow complet (3 phases : cartographie 35 blocs → évaluation parallèle
de 31 blocs ≥80 lignes → synthèse), ~4M tokens, 863 appels d'outils, ~25 min.
**Aucune extraction n'a été lancée** — F4GLD était absent depuis des heures,
résultat présenté en attente de son choix.

## Recommandation n°1 : Callbook (QRZ/HamQTH/HamDB) + statut à la frappe

`concours/logx_logbook.js` L954-1128 (175 lignes), cible `logx_callbook.js`.
**Zéro test à adapter** (seul incrément du lot entier dans ce cas — juste
une mise à jour cosmétique de `JS_EXTRAITS_EV7`). État interne quasi-total
autonome (1 seule variable partagée en lecture, `_stateAnnuaire`, motif déjà
validé 15 fois). Hors chemin critique (enrichissement de frappe, pas la
saisie/l'enregistrement eux-mêmes). Point à documenter dans l'en-tête (pas
à corriger) : `fmtDate()` est déjà consommée par `logx_awards.js`.

**Alternative si on veut extraire plus gros pour le même risque** : Lookup
indicatifs (HamQTH distant/cache cluster/calldb/autocomplete), L4831-5153,
323 lignes — même profil "zéro test obligatoire", ~2x plus gros.

## Classement complet des 11 candidats FAIBLE (du plus propre au moins)

1. Callbook (L954-1128, 175L) — 0 test — **recommandé**
2. Lookup indicatifs (L4831-5153, 323L) — 0 test — alternative volume
3. Widget jour/nuit + champ locator (L3005-3098, 94L) — 0 test
4. Callbot vocal (macros dynamiques) + ESM (L2046-2159, 114L) — 1 test
5. Keyer vocal DVK slots serveur (L1527-1670, 144L) — 1 test
6. Reverse lookup locator→indicatifs + compas (L5155-5294, 140L) — 1 test
7. Thème jour/nuit + raccourcis clavier globaux (L5686-5830, 145L) — 1 test
8. Formats d'échange concours + mode expédition (L87-184, 98L) — 2 tests
9. Saisie n° série auto + champ indicatif (L2886-3003, 118L) — 2 tests, 1 risque de "passe silencieuse" documenté
10. Bandeau dernier QSO + édition + champs ADIF (L3818-4048, 231L) — 2 tests
11. **submitQSO()** + effacement formulaire (L3100-3298, 199L) — 2 tests, mais touche le **chemin critique absolu** (bouton d'enregistrement du QSO, protégé par CLAUDE.md "Intuitivité") — à traiter avec la plus grande prudence si jamais retenu malgré tout

## 4 candidats ÉLEVÉ — à ne PAS proposer dans un futur inventaire

- **État global & détection file://** (L1-85) — pas un sous-système, c'est
  l'état FONDAMENTAL partagé par ~6100 lignes (myCall/currentContest/
  currentBand/currentMode...) ; ~8 fichiers de test à toucher pour 85 lignes.
- **backupNow() + setupDone()** (L2306-2399) — `setupDone()` est la fonction
  d'amorçage CENTRALE de toute la page (15 fonctions appelées, 5 variables
  d'état utilisées 18-23 fois ailleurs), l'équivalent d'un `main()`.
- **Horloge + compte à rebours concours** (L2401-2514) — exécute du code au
  NIVEAU SUPÉRIEUR au chargement (`setInterval` immédiat appelant des
  fonctions déclarées plus loin) → ReferenceError garantie sous la
  convention EV-7, **même classe de bug que le piège `adaptivePoll`** déjà
  corrigé une fois (cf. [[chantier-fix-adaptivepoll-domcontentloaded-2026-08-08]]).
- **Rendu du tableau du log / `renderLog()`** (L3666-3816) — mécaniquement
  propre, MAIS documenté à plusieurs reprises dans le code lui-même comme
  "chemin critique, jamais déplacé", point d'ancrage d'au moins 7 fichiers
  déjà extraits. Défaire une décision d'architecture déjà actée.

## Candidats MOYEN à mélange explicite (piège déjà documenté, à scinder si repris)

CS_DATA+filtre avancé, Soapbox+macros CW+adaptivePoll, préremplissage modal
démarrage (4 sous-systèmes sans lien), affichage panneaux CW/RTTY/SSTV+SO2R
(contient aussi un piège classe-adaptivePoll : 4 appels top-level en fin de
bloc), décodeur CW wrapper+audio générique. Détail complet et candidats
MOYEN restants (band map, scoring, export EDI/ADIF, chat multi-op, sync
multi-onglet...) dans le journal du Workflow si besoin de retrouver le
raisonnement exact — non reproduit ici pour rester consultable rapidement.

## Suite

Si F4GLD valide un candidat au retour, suivre le pipeline standard des
incréments 10-15 (extraction Python, vérif syntaxe, script tag,
JS_EXTRAITS_EV7, tests ciblés + suite complète, vérif navigateur — attention
au [[piege-push-qsolog-live-render-auto]] découvert le même jour si le test
touche qsoLog —, revue adversariale Workflow, commit/push/CI/merge/mémoire).
