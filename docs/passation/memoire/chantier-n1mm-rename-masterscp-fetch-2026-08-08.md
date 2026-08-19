---
name: chantier-n1mm-rename-masterscp-fetch-2026-08-08
description: "Lot livré — renommage libellés N1MM en UI CONFIG, auto-fetch MASTER.SCP, fix bug esmSend() (CW manuel sans CAT jouait un message vocal), 3 ajouts UI inspirés d'une revue de captures OpsLog ; revue adversariale Workflow a trouvé et fait corriger 3 vrais bugs avant fusion"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T09:15:14.248Z
---

Chantier livré et fusionné sur `main` le 08/08/2026 (commit `1b83620`, merge
de `feat/master-scp-auto-fetch-rename`, commits de contenu `bae23d3`).

## Origine

F4GLD a demandé si la mention « N1MM » en CONFIG (section BASES
D'INDICATIFS EXTERNES) était nécessaire ou si les données pouvaient être
récupérées automatiquement. Réponse : « N1MM » y désignait un FORMAT de
fichier (documenté publiquement), pas une dépendance au logiciel — mais par
cohérence avec l'interdiction déjà établie de nommer un concurrent dans le
code ([[feedback-jamais-qso-director-dans-le-code]]), le libellé a été
neutralisé. Séparément, F4GLD a partagé 4 captures d'écran d'OpsLog
(concurrent) et demandé d'en extraire ce qui est transposable — 4 points
identifiés, 3 retenus pour ce chantier (point 1, arborescence de réglages à
gauche, jugé trop gros et reporté à un chantier dédié séparé, décision
explicite de F4GLD via AskUserQuestion).

## Ce qui a été livré

**1. Renommage** : « BASES D'INDICATIFS EXTERNES (N1MM) » → « BASES
D'INDICATIFS EXTERNES », « CALL HISTORY (format N1MM) » → « CALL HISTORY »
(`logx_configuration.html`). Les ~12 autres mentions « N1MM » du fichier
sont restées — elles citent le vrai logiciel tiers dans un contexte
d'interopérabilité réelle (réseau ADIF, partage de port CAT, auto-lancement
de logiciels tiers), pas notre propre fonctionnalité — confirmé exhaustif
par la revue adversariale.

**2. Auto-fetch MASTER.SCP** : nouveau bouton « Mettre à jour depuis
Internet » à côté de l'import manuel. Télécharge
`http://www.supercheckpartial.com/MASTER.SCP` (URL vérifiée live via
WebFetch avant implémentation — 351 Ko, release 2026.07.31, c'est la source
par défaut utilisée par N1MM+/Win-Test eux-mêmes) via `fetch_url()`
(`logx_utils.py`, pool de threads borné déjà établi), réutilise
`import_master_scp()` existant tel quel. Call History reste 100% manuel —
décision assumée : propre à CHAQUE concours, distribué par l'organisateur à
une URL différente à chaque fois, pas de source centrale automatisable.

**3. Fix bug esmSend()** (préexistant, sans lien avec le chantier —
remarqué en corrigeant `logx_logbook.js` pendant [[chantier-ev7-radio-cat-2026-08-08]]) :
exigeait `rigState.enabled` pour router en CW, contrairement à
`updateKeyerPanels()` juste à côté qui utilise le repli
`rigState.mode || currentMode` SANS l'exiger. Un opérateur en CW MANUEL
(clé/manip externe, pas de CAT branché) voyait ESM jouer un message VOCAL
réel au lieu du CW attendu — pas une dégradation d'affichage, une action
FAUSSE et audible sur l'air. Aligné sur le même repli.

**4. 3 ajouts UI** (idées tirées d'OpsLog, avec accord explicite F4GLD) :
- Bouton « Lancer » par ligne du panneau AUTO-LANCEMENT — `testAutostartRow()`
  → `POST /autostart/launch` → `logx_autostart.lancer()` (fonction déjà
  exhaustivement testée, endpoint = simple passe-plat HTTP).
- Cadenas visuel à côté du champ FRÉQUENCE (fermé = suit la radio CAT,
  ouvert = saisie manuelle) — rend visible un état qui existait déjà en
  interne (`dataset.userEdited`) mais jamais affiché.
- Avertissement avant de fermer une section CONFIG avec des modifications
  non enregistrées (`_snapshotCatForm`/`_catHasUnsavedChanges`/
  `_confirmDiscardCatChanges`) — NE change PAS la règle F4GLD du 04/08/2026
  (fermer ne sauvegarde jamais), prévient seulement qu'on va perdre
  quelque chose.

## 3 vrais bugs trouvés par la revue adversariale Workflow (PAS par moi), corrigés avant fusion

1. **Bypass du garde de fermeture, chemin très courant** : `openCategoryPopup(cat)`
   masquait la section précédemment ouverte SANS jamais appeler
   `_confirmDiscardCatChanges` — atteignable simplement en cliquant un
   AUTRE onglet de la barre latérale pendant que la section courante avait
   des modifications non enregistrées (`switchSection()` → `openCategoryPopup()`).
   Pire : 2 liens du fichier chaînaient `closeCategoryPopup('x');openCategoryPopup('y')`
   dans le MÊME onclick — cliquer « Annuler » dans la boîte de confirmation
   de `closeCategoryPopup()` faisait bien échouer CETTE fermeture, mais
   `openCategoryPopup('y')` s'exécutait quand même juste après (deux
   instructions indépendantes, pas de court-circuit), écrasant la section
   sans jamais redemander — le clic Annuler de l'opérateur était
   silencieusement ignoré. Corrigé : `openCategoryPopup()` vérifie
   désormais aussi la section qu'il s'apprête à remplacer ;
   `closeCategoryPopup()` renvoie `true`/`false` et les 2 liens utilisent
   `&&` pour ne plus ouvrir la cible si la fermeture a été refusée.
2. **Radios sans `id` jamais suivies** : `_snapshotCatForm()` ignorait tout
   champ sans `id` (`if(!el.id) return;`) — les 6 boutons radio du choix de
   fournisseur IA (section Assistant IA, `name="api_provider"`, aucun n'a
   d'`id`) passaient totalement inaperçus. Changer de fournisseur IA puis
   Fermer ne prévenait jamais, alors que `saveConfig()` persiste bien ce
   choix (`api_provider`, lu via `querySelector('...:checked')`). Corrigé :
   les radios sans `id` sont désormais suivies par `name` + état `checked`.
3. **Cadenas fréquence périmé si `rigctld` injoignable** : l'appel à
   `updateFreqLockIcon()` dans `applyRigState()` (`logx_hardware_cat.js`)
   n'était présent QUE dans la branche `d.ok===true` — un payload réel
   `{enabled:true, ok:false}` (CAT activé en CONFIG mais radio/port
   injoignable — cas RÉEL documenté dans plusieurs branches de
   `logx_cat.get_state()`, pas théorique) laissait l'icône dans un état
   périmé (généralement masquée) tant qu'aucun poll `ok:true` n'arrivait.
   Corrigé : l'appel est remonté avant le `if(d.ok)`, couvre les deux cas.

**Généralisation pour la suite** : cette revue confirme, une 3e fois
([[chantier-ev7-radio-cat-2026-08-08]] avait le même schéma), la valeur de
la revue adversariale Workflow AVANT fusion sur des changements JS
touchant plusieurs points d'entrée d'un même mécanisme (ici : 3 chemins de
fermeture d'un popup CONFIG, 2 branches d'une même fonction d'application
d'état) — un grep superficiel ou une vérification manuelle limitée à UN
scénario aurait manqué les 3.

## Incident pendant la vérification navigateur (leçon à retenir)

En testant le point 4 (avertissement fermeture), un test JS console a
appelé `saveConfig(true)` pour de vrai contre le serveur de production —
un POST RÉEL vers `/config/save`, pas un simple GET en lecture seule.
Détecté immédiatement (le champ `city` du DOM était vide au départ,
`orig + '_Y'` a été réellement persisté avant la remise en état DOM-only).
Corrigé sur-le-champ (re-`saveConfig(true)` avec la valeur correcte),
vérifié directement sur `.server_config.json` (fichier réel, `city: ''`
confirmé). Aucune perte de données réelle (le champ était déjà vide),
mais **leçon impérative pour toute vérification future** : ne JAMAIS
appeler `saveConfig()` ou toute fonction à écriture réelle contre le
serveur de production pendant une vérification navigateur — même pour
tester une fonctionnalité totalement différente (ici, `saveConfig()` a été
utilisé comme simple utilitaire pour rafraîchir un snapshot, sans réaliser
que la fonction elle-même a un effet de bord réseau réel). Toujours
préférer une manipulation DOM pure + mock de `confirm()`/`fetch()` pour ce
genre de test.

## Reliquat volontairement hors scope

Point 1 de la revue OpsLog (arborescence de réglages à gauche, remplaçant
le système actuel de popups par catégorie) — chantier de refonte à part
entière (7664+ lignes de `logx_configuration.html` à restructurer), reporté
à une session dédiée sur demande explicite. Aucune cible suivante choisie.
