---
name: chantier-carte-ia-backlog-restant-2026-08-18
description: "CARTE IA : backlog multi-phase clos — bandeau connectivité IA (PR #105), projection score fin de concours (PR #106), planification VOACAP 12 mois pour DXpéditions (PR #107), 18/08/2026"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-18T07:37:41.676Z
---

Suite de [[chantier-config-panel-plein-ecran-fermeture-uniforme-secrets-2026-08-16]] :
F4GLD a demandé une vérification/amélioration générale, réponse "oui vas y
relance" comprise comme validant la reprise des 2 tâches en sommeil du
tracker (#51 backlog CARTE IA + #92 CONFIG CAT — cette dernière s'est avérée
DÉJÀ FAITE par une PR antérieure, juste vérifiée en conditions réelles).

## Scoping initial (agent Explore) avant tout code

Avant de foncer, un agent a vérifié l'état RÉEL du backlog CARTE IA
(description tâche #51 : "repli auto hors-ligne, bandeau de connectivité" +
"fonctions Expert (projection concours, VOACAP expédition, saisie vocale,
OCR)"). Résultat : OCR abandonné (déjà su), saisie vocale DÉJÀ livrée et
fonctionnelle (`logx_voice_dictation.js`, `#chatMicBtn`) — donc seuls 3
éléments restaient un vrai vide :
1. Bandeau de connectivité IA (le repli hors-ligne existait mais réactif
   seulement, pas de bandeau persistant ni de détection proactive).
2. Projection concours (aucune réponse du coach n'était prospective).
3. VOACAP expédition (calcul ponctuel "maintenant" seulement).

**Réflexe qui a évité du travail redondant** : toujours vérifier l'état réel
du code avant de se fier à une description de tâche datée, même écrite par
soi-même — évite de refaire ce qui existe déjà (cf. #92).

## PR #105 — Bandeau de connectivité IA

`_setAiOffline(state, msg)` centralise 2 déclencheurs (évènements navigateur
online/offline + `offlineFallback()` sur échec IA, qui couvre à lui seul ses
6 sites d'appel) et 1 résolution (`finalizeAgentReply()`, commune à tous les
chemins de succès). Bandeau positionné hors de `#chatMsgs` (jamais emporté
par son scroll), bordure+point `var(--yellow)` + texte `var(--text)` —
jamais de remplissage plein avec l'accent, donc pas de piège de contraste
jour/nuit à gérer pour cette fois.

## PR #106 — Projection de score en fin de concours

Nouveau topic `'projection'` dans `logx_coach.answer_text()`, 100%
déterministe. Extrapolation à rythme constant (`rate_avg` × heures
restantes), avec 2 garde-fous d'honnêteté : même seuil que `hint_rate_drop`
existant (≥10 QSO) avant de faire confiance à `rate_avg`, et avertissement
systématique rappelant que les multiplicateurs se raréfient en fin de
concours — **jamais présentée comme une prédiction fiable**, réflexe à
garder pour toute future fonctionnalité prospective similaire.

Traductions FR+EN seulement — découverte en lisant `logx_coach_i18n.py` :
la famille `off_*`/`nudge_*` entière n'a JAMAIS eu de traduction DE/ES/IT/
PT/NL/PL (seuls FR/EN sont complets sur cette famille, repli français déjà
en place pour les 5 autres langues) — donc ne pas traduire dans ces 5
langues n'est PAS une régression introduite, juste suivre l'état déjà
établi. Vérifier ce genre de "trou déjà là" avant de se lancer dans une
traduction manuelle risquée dans 5-6 langues non maîtrisées nativement.

## PR #107 — Planification VOACAP 12 mois (DXpédition)

Découverte clé en lisant le code AVANT d'écrire quoi que ce soit :
`logx_voacap.predict()` acceptait DÉJÀ `month`/`year` en paramètres
optionnels — seul l'endpoint HTTP `/data/voacap` ne les lisait jamais
depuis la requête. Le "moteur ne supporte pas de date future" du rapport de
scoping initial était donc FAUX (ou du moins incomplet) : c'est la couche
HTTP qui bridait, pas `logx_voacap.py`. **Toujours lire le code jusqu'au
bout avant de conclure qu'une fonctionnalité manque — un scoping rapide
peut manquer un paramètre optionnel déjà câblé.**

Mesure empirique AVANT de figer la conception UI (nombre de mois à
comparer) : un calcul VOACAP réel prend ~0.1-0.3s (mesuré avec le vrai
binaire sur le répertoire principal, PAS dans un worktree — voir piège
ci-dessous), donc 12 appels séquentiels (~1-3s total) sont largement dans
le budget d'un clic. Décidé APRÈS mesure, pas par supposition.

Nouveau bouton PLANIFIER EXPÉ (menu ⋯ PLUS CARTE IA, expert-only) : compare
la même destination sur les 12 prochains mois, affiche le MEILLEUR créneau
par mois (bande/heure/REL% max) plutôt que le tableau 24h×8-bandes complet
répété 12 fois (illisible) — choix de conception délibéré pour la
lisibilité, pas une limitation technique.

## ⚠️ FAUX POSITIF : le "bug \config" n'a jamais existé (vérifié 18/08)

Signalé pendant PR #107 comme `if path == '\config':` (backslash au lieu de
slash) rendant l'endpoint "écran mural d'expédition" mort depuis toujours,
et confié à un chantier isolé (spawn_task task_96fd7864). **La vérification
a montré que le constat était FAUX de bout en bout** :

- `grep -F` sur le fichier (worktree ET copie de travail principale) : aucun
  backslash-config nulle part ; la ligne est `if path == '/config':`.
- `git log --all -S "'\config'" -- concours/logx_http.py` : **zéro commit**
  dans TOUTE l'histoire du dépôt — la chaîne n'a jamais été écrite.
- L'endpoint est massivement vivant : **18 sites d'appel** `fetch('/config')`
  répartis sur 14 fichiers, dont `logx_statusbar.js` inclus sur toutes les
  pages — s'il était mort, l'application entière serait visiblement cassée.
- Le test réclamé par le chantier **existait déjà** :
  `concours/tests/test_config_endpoint_usage_mode.py` (vrai
  ThreadingHTTPServer + Handler, 3 tests, verts) couvre la liste blanche ET
  un garde-fou "aucun secret".
- Preuve d'exécution refaite quand même : GET /config -> HTTP 200, exactement
  les 13 champs de la liste blanche, **aucune fuite** même avec
  `api_key`/`qrz_password`/`auth_token`/`lotw_password` bourrés dans
  `current_config`.

Aucune ligne modifiée, aucune branche, aucune PR — il n'y avait rien à
corriger.

**Réflexe à garder** : un constat "repéré en passant" en LISANT du code
pendant un autre chantier doit être re-confirmé par un `grep -F` littéral
(+ `git log -S` si on affirme "depuis son introduction") AVANT d'ouvrir un
chantier dessus. Un numéro de ligne cité de mémoire et une chaîne recopiée
à la main sont deux sources d'erreur indépendantes ; ici les deux ont
divergé du fichier réel. Même logique que
[[piege-artefacts-perimes-verification]] et
[[piege-liste-identifiants-ecrite-a-la-main]], appliquée cette fois à un
constat de bug plutôt qu'à un artefact.

## Pièges confirmés (déjà documentés, revus ici)

- `test_predict_reel_avec_le_vrai_binaire` échoue systématiquement dans
  TOUT worktree (encore confirmé, 4e+ occurrence cette session), passe
  systématiquement sur le répertoire principal — toujours reconfirmer sur
  le répertoire principal avant de creuser, ne jamais supposer une
  régression de ses propres changements sur ce test précis.
- `git worktree remove` bloqué par SynologyDrive ("Permission denied") :
  réessayer immédiatement suffit (nettoie les métadonnées Git même si la
  suppression physique du dossier échoue au 1er coup), puis `rm -rf` sur
  le dossier résiduel si besoin. Le dépôt accumule plusieurs dossiers
  résiduels plus anciens (`.claude/worktrees/charming-sanderson-c6e663` et
  consorts, hash aléatoires probablement générés par un outil tiers) — ne
  jamais les toucher sans consulter F4GLD, contexte inconnu, hors scope de
  tout chantier ponctuel.
