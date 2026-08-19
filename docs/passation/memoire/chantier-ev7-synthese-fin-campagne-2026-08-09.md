---
name: chantier-ev7-synthese-fin-campagne-2026-08-09
description: "Synthèse de fin de campagne EV-7 (36 incréments, ~7500→3668 lignes) — terme naturel atteint, 5 classes de pièges documentées"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T12:13:40.491Z
---

La campagne EV-7 (LogX AI, refactor incrémental de `concours/logx_logbook.js`
en fichiers dédiés `concours/logx_*.js`) a produit **36 incréments** fusionnés
sur main entre le 07/08/2026 et le 09/08/2026, réduisant `logx_logbook.js`
d'environ **7500+ lignes à 3668 lignes** — plus de la moitié du fichier
d'origine extraite vers 30 fichiers dédiés, chacun chargé en `<script>`
classique AVANT `logx_logbook.js` (portée globale partagée, pas de modules
ES — convention constante sur les 36 incréments).

**Why:** demande utilisateur initiale (avant le début de cette longue session
autonome) de rendre le monolithe plus maintenable en l'éclatant par
fonctionnalité, sans jamais casser le comportement en production.

## Méthodologie stabilisée (identique sur la quasi-totalité des incréments)

1. **Extraction** : script Python heredoc (`/c/Users/parri/AppData/Local/Programs/Python/Python313/python.exe`,
   PYTHONIOENCODING=utf-8), extraction par **ancre de chaîne**
   (`src.index("...")`) plutôt que par numéro de ligne (qui dérive à chaque
   incrément) — méthode adoptée dès le 32e incrément (MACROS F1-F8, premier
   bloc non-contigu) et généralisée ensuite.
2. **Vérification syntaxe** : `py_mini_racer.MiniRacer()` + `new Function(json.dumps(src))`
   sur les deux fichiers (cœur modifié + nouveau fichier) après chaque
   extraction — a détecté au moins une extraction tronquée (36e incrément)
   avant même de lancer un test.
3. **`<script>` tag** ajouté dans `logx_logbook.html`, toujours juste avant
   `<script src="logx_logbook.js">`.
4. **`JS_EXTRAITS_EV7`** (liste Python dans `tests/test_logbook_menu_debut_fin.py`)
   mise à jour avec le nouveau nom de fichier.
5. **Grep des 4 (puis 5) classes de pièges** de dépendance cachée, à chaque
   incrément, AVANT de considérer l'extraction sûre :
   - **Classe 1 — appel top-level** : une instruction exécutée au chargement
     du script (pas dans une fonction) qui référence un symbole déplacé —
     casse TOUS les tests hôte-entier si le nouveau fichier n'est pas chargé
     avant `logx_logbook.js`.
   - **Classe 2 — appel function-body du cœur** : une fonction du cœur (le
     plus souvent `submitQSO()`, `setupDone()`, `clearForm()`) appelle un
     symbole désormais déplacé — invisible à un grep du nom du BLOC, il faut
     chercher les appelants du SYMBOLE.
   - **Classe 3 — extraction de test par sous-chaîne** : un test qui extrait
     un bloc de `logx_logbook.js` par recherche littérale de texte (titre de
     panneau, motif de code) — casse si le bloc déménage, même si le
     comportement réel est intact.
   - **Classe 4 — constante/variable locale au corps d'une fonction**,
     recherchée par un test SANS chercher le nom de la fonction elle-même —
     la classe la plus sournoise, rencontrée 4 fois (dernière occurrence :
     33e incrément, `refreshBandMap()`).
   - **Classe 5 — variable d'état partagée avec le cœur** (introduite au
     35e incrément) : une variable `let`/`const` de portée module, utilisée
     par le bloc candidat mais aussi lue/écrite par du code du CŒUR situé
     ailleurs dans le fichier. Règle de décision affinée au 36e incrément :
     **écriture** multiple depuis le cœur → la variable reste au cœur, seule
     la fonction qui la lit migre (ex. `lastQsoTime`/`_myVersion`) ;
     **lecture seule** depuis le cœur → la variable peut migrer en bloc avec
     ses fonctions sans risque (ex. `bipEnabled`/`esmMode`), car le fichier
     qui la déclare charge toujours avant le cœur.
6. **Suite pytest complète** (~8792 tests) relancée après chaque extraction,
   en arrière-plan (`run_in_background`, JAMAIS combiné avec un `&` shell
   interne — piège documenté séparément). **Piège de notification réaffirmé
   au 36e incrément** : le résumé de notification peut annoncer un exit code
   trompeur alors que des tests ont réellement échoué — toujours vérifier le
   VRAI résultat écrit explicitement dans le fichier de log (`FAILED`
   présent ou non), au besoin en ajoutant un `echo "REAL_EXIT_CODE:$?" >> log`
   dans la commande elle-même.
7. **Vérification navigateur réelle** sur le serveur de production port
   8080 (JAMAIS redémarré de toute la campagne), toujours via l'URL RACINE
   (`http://localhost:8080/logx_logbook.html`, jamais le préfixe
   `/concours/` qui sert du contenu vide/périmé sur ce serveur de dev) :
   `typeof` de chaque symbole exporté + exercice fonctionnel réel des
   fonctions sans effet de bord réseau dangereux (jamais de vrai envoi
   CW/vocal, jamais de vraie sauvegarde NAS, jamais de vrai push GitHub/CI
   déclenché depuis le navigateur), avec remise à zéro de l'état modifié
   pour ne pas polluer la session live partagée.
8. **Revue adversariale Workflow** à 2 dimensions (fidélité de l'extraction
   + intégrité des dépendances), chaque constat brut re-vérifié
   indépendamment par un agent chargé de le RÉFUTER (`real_bug=false` par
   défaut sauf preuve du contraire lue dans le code).
9. **Commit/branche/push/CI/merge** : branche dédiée par incrément
   (`feat/ev7-<N>-<nom>`), CI GitHub Actions surveillée via `gh run list`,
   merge `--no-ff` sur main, suppression de la branche locale+distante.
   `concours/custom_contests.json` jamais staged (dérive serveur continue,
   sans rapport avec le refactor).
10. **Mémoire** : une entrée `chantier-ev7-<nom>-AAAA-MM-JJ.md` par
    incrément fusionné, avec une ligne en tête de `MEMORY.md`.

## Inventaires successifs (méthodologie de croisement chemin-critique)

5 inventaires Workflow ont rythmé la campagne, chacun cartographiant le
fichier restant, évaluant les candidats contre les 5 classes de pièges, puis
croisant explicitement chaque candidat contre le **chemin critique** de
l'application (config → sélection concours → saisie bande/mode/callsign/
RST/échange → bouton d'enregistrement du QSO → navigation CONFIG↔LOGBOOK) :
tout candidat appelé, même indirectement, par `setupDone()`, `clearForm()`,
`submitQSO()`, `pickBand()`, `onFreqInput()` ou `prefillSetupFromConfig()`
est classé ÉLEVÉ et écarté, quel que soit son risque technique propre. Cette
méthode (établie au 3e inventaire) s'est avérée nettement plus fiable que
les inventaires initiaux moins structurés.

Le **5e inventaire** (09/08/2026) a conclu explicitement, après lecture
intégrale du fichier restant (alors 3724 lignes) : **4 candidats FAIBLE
réels totalisant ~74 lignes** (fusionnés au 36e incrément), et **plus de
90 % du fichier restant relevant du chemin critique intouchable** — le
scoring, l'activation POTA/SOTA/IOTA/WWFF, le chat multi-opérateur, le
BroadcastChannel, l'horloge/countdown (piège TDZ réel confirmé), et le menu
DÉBUT/FIN sont tous câblés directement à une des 6 fonctions du chemin
critique.

## Conclusion

La campagne EV-7 touche à son **terme naturel** à ce stade (36e incrément,
09/08/2026) : le dernier inventaire n'a identifié aucun candidat FAIBLE ou
MOYEN convaincant au-delà de ce qui a déjà été extrait, et la proportion de
chemin critique dans ce qui reste (>90 %) rend toute extraction
supplémentaire structurellement risquée sans bénéfice de maintenabilité
proportionné. **How to apply :** ne pas lancer de 6e inventaire par
réflexe — un futur chantier sur `logx_logbook.js` devrait plutôt porter sur
le chemin critique lui-même (refactor DANS le fichier, pas extraction VERS
un autre fichier), ou attendre un fait nouveau (nouvelle fonctionnalité
ajoutée qui, elle, serait née autonome dès le départ — cf. règle
« Intuitivité »/`expert-only` de CLAUDE.md, qui recommande déjà de ne PAS
mélanger nouveau code non-critique avec le cœur dès sa création).
