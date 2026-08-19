---
name: chantier-ev7-locator-reverse-2026-08-09
description: EV-7 21e incrément — extraction Reverse Lookup Locator + Compas vers logx_locator_reverse.js (09/08/2026, fusionné 5cd7da1) — sans piège top-level, mais piège fonctionnel trouvé par pytest réel
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T23:37:13.714Z
---

21e incrément de la campagne EV-7 : extraction du bloc REVERSE LOOKUP
LOCATOR → INDICATIFS + COMPAS INLINE de `logx_logbook.js` (lignes
originales 4328-4467) vers `concours/logx_locator_reverse.js`, chargé en
`<script>` classique juste après `logx_voice_keyer.js`, avant
`logx_logbook.js`. Contenu : `locAcResults`/`locAcSelected`,
`searchByLocator()`, `showLocAC()`/`hideLocAC()`/`selectLocAC()`,
`onLocatorKeydown()`, `_lastCompassDeg`, `showCompassInline()`,
`pointAntennaFromCompass()`, `hideCompassInline()`. Branche
`feat/ev7-extract-locator-reverse`, commit contenu `d5177a8`, fusionné sur
`main` en `5cd7da1`.

**Contrairement aux 19e/20e incréments : zéro appel top-level en jeu.** Le
grep exhaustif fait avant extraction n'a trouvé aucun appel top-level dans
`logx_logbook.js` vers un symbole de ce bloc — confirmé par la revue
adversariale.

**Mais un piège DIFFÉRENT a été trouvé — pas par grep, mais par exécution
réelle de la suite pytest complète.** `clearForm()` et `onCallInput()`
(fonctions du cœur, restées dans `logx_logbook.js`, exercées par le flux
normal de `submitQSO()`) appellent `hideCompassInline()` en corps de
fonction — un appel parfaitement sûr en usage normal (fonction-body,
résolu tardivement), mais qui casse silencieusement le SEUL fichier de
test qui simule un scénario `submitQSO()` complet
(`test_macro_cw_serie_bande.py`, via son driver `__run(plan)`) : la même
classe de symptôme que le postmortem du 16e incrément Callbook
(`ReferenceError` dans une chaîne de Promise non attendue → `__done` reste
`false` sans exception visible). Corrigé en ajoutant
`LOCATOR_REVERSE_JS_PATH` à la concaténation multi-fichiers déjà existante
de ce test (HARDWARE+CALLBOOK+LOOKUP+ESM_CALLBOT+VOICE_KEYER+
LOCATOR_REVERSE+logx_logbook.js).

**Leçon générale à retenir** : le réflexe « grep top-level avant de
pousser » ([[piege-appel-top-level-casse-tests-hote-entier]]) couvre UNE
classe de dépendance cachée (appels qui s'exécutent au PARSE), mais pas
TOUTES — un appel en corps de fonction depuis le cœur vers le bloc extrait
peut aussi casser un test, à condition que ce test EXERCE réellement le
chemin qui contient l'appel (ici, seul un scénario `submitQSO()` complet
touchait `clearForm()`/`onCallInput()`). Le grep systématique des
identifiants déplacés (déjà pratiqué à chaque incrément) trouve les SITES
d'appel, mais ne dit pas lesquels sont exercés par quels tests — seule
l'exécution réelle de la suite pytest COMPLÈTE (pas seulement les tests
ciblés au fichier extrait) le révèle de façon fiable. Réflexe confirmé :
ne jamais considérer un incrément EV-7 terminé sans avoir relancé
`pytest concours/tests` en entier au moins une fois après l'extraction.

Revue adversariale Workflow (2 dimensions, prompt de vérification durci
pour ne remonter que les VRAIS correctifs actionnables, pas les simples
confirmations) : 1 seul constat brut, non confirmé comme actionnable —
revue la plus propre de la campagne à ce stade.

Vérification navigateur : `searchByLocator()`/`showLocAC()` déclenchés en
tapant "JN18" (12 résultats, autocomplete affichée) ; `showCompassInline()`
déclenché en tapant un locator complet "JN18AA" (cap 337° affiché) ; aucune
erreur console liée à "locator"/"compass" après hard-reload.
