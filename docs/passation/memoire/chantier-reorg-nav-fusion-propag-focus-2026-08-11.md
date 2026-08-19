---
name: chantier-reorg-nav-fusion-propag-focus-2026-08-11
description: "Réorg complète de la nav partagée + fusion PROPAG/FOCUS BANDE + renommage DÉPARTEMENTS→ZONES TRAVAILLÉES (11/08/2026, PR #33 + PR #34)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-11T09:55:15.034Z
---

Chantier en 2 PR décidé avec F4GLD (échange direct + AskUserQuestion) : réordonner
la barre de nav partagée et fusionner deux pages qui se recoupaient dans l'usage
concours réel.

**PR1 (#33, mergée)** : fusion réelle de contenu — `logx_focus.html` (FOCUS BANDE,
outil opérationnel gardé ouvert en concours : classement bandes, cluster, carrés à
reprendre) porté comme 4e onglet interne **« BANDE ACTUELLE »** dans
`logx_propagation.html`, NOUVEAU DÉFAUT à l'ouverture (devant HF/VHF/M'ENTEND-ON).
`logx_focus.html` supprimé après portage. Mécanique : `PROP_PANES = ['focus','hf',
'vhf','heard']`, tâches enregistrées via `propTask()` (le seul scheduler autorisé —
`test_aucun_minuteur_n_echappe_au_planificateur` interdit tout `setInterval` isolé,
y compris pour une horloge de pane).

**PR2 (#34, mergée)** : nouvel ordre de nav sur les 10 pages qui la partagent :
CONFIG → LOGBOOK → CHASSE → MODE NUMÉRIQUE → PROPAG → CARTE IA → **ZONES
TRAVAILLÉES** (ex-DÉPARTEMENTS, libellé seul, page/contenu diplôme inchangés) →
PANADAPTER (popout) → CALENDRIER → WEBSDR → ÉCOLE CW. Renommage propagé : clé i18n
dans les 7 langues (`logx_i18n.js`), `logx_search.py` (corrige au passage un bug
préexistant sans rapport : le label était `'CARTES'`), doc utilisateur.

**Why** : refléter l'usage réel en concours (PROPAG=dashboard consulté
ponctuellement vs FOCUS BANDE=outil travaillé en continu sur 2e écran) plutôt que
l'ordre historique d'ajout des pages.

**How to apply** : le patron `PROP_TASKS`/`propTask()`/`propTick()` de
`logx_propagation.html` (voir [[chantier-ev7-synthese-fin-campagne-2026-08-09]]
pour la méthodologie EV-7 dont il hérite) est maintenant la référence pour tout
futur onglet interne à fusionner dans une page multi-panneaux. Le bloc nav
`<nav class="app-nav">` reste dupliqué à la main dans chaque fichier HTML (pas de
partiel/include côté serveur) — toute future réorg doit éditer les 10 fichiers un
par un, avec `class="active"` posé sur le lien de la page courante.

## Pièges rencontrés

1. **`propTask(window.focusCharger, ...)` invisible au test statique** : le regex
   de `_taches()` dans `test_propagation_onglets.py` exige un identifiant NU
   (`\w+`), pas `window.xxx` — la présence du point fait échouer TOUT le match
   (pas seulement capturer `'window'`), rendant la tâche invisible à toute la
   suite de vérification statique sans qu'aucun test ne le signale explicitement.
   Toujours enregistrer les fonctions par leur nom nu dans `propTask()`.
2. **Alias `const $ = document.getElementById`** casse le même test :
   `test_chaque_chargeur_est_declare_dans_le_bon_onglet` cherche le littéral
   `getElementById(` dans le corps de la fonction — un alias raccourci ne
   contient jamais cette chaîne. Ne jamais introduire de raccourci `$()` dans du
   code porté vers `logx_propagation.html` (qui n'en a jamais eu).
3. **`cmd > file 2>&1; echo EXITCODE:$? >> file` doit être une commande SÉPARÉE**,
   pas chaînée à un `tail` ou autre lecture — sinon `$?` capture le code de la
   commande de lecture (toujours 0), pas celui de pytest. Revalidé sur ce chantier
   après l'avoir déjà documenté ([[piege-echo-exit-masque-code-sortie-reel]]).
4. **2 flakes réseau confirmés sans rapport avec le diff** :
   `test_http_mysql_test_route_correctement` et
   `test_peer_annoncant_le_bon_asset_toujours_accepte` — timeouts socket
   localhost, verts au re-run isolé. Toujours re-lancer isolément un échec avant
   de le traiter comme une régression réelle.
5. **`read_page`/`find` du navigateur peuvent tronquer l'arbre d'accessibilité**
   avant la fin d'une longue nav (11 liens) sans le signaler clairement — un
   `<a>` manquant dans `read_page`/`find` n'est pas forcément un bug de rendu :
   vérifier via `javascript_tool` (`document.querySelectorAll` direct) avant de
   conclure à une régression.
6. **Worktree Git non supprimable (`Permission denied`)** : un ancien serveur de
   test Python resté ouvert sur un port depuis une étape précédente du même
   chantier tenait un fichier du worktree — `git worktree remove --force` échoue
   silencieusement sur le dossier disque (mais retire quand même l'entrée Git).
   Chercher le process qui écoute sur le port de test associé
   (`netstat -ano | grep :PORT`) et le tuer avant de retenter `rm -rf`.

## Aparté hors scope (clarifié, aucun changement de code)

F4GLD a signalé voir la barre d'adresse/favoris Chrome au-dessus de LogX AI —
ce n'est PAS un bug ni une régression de ce chantier : `open_browser_app_mode()`
(`logx_bootstrap.py`, `--start-maximized --app=url`, sans barre d'adresse/favoris)
n'est appelée QUE si `is_frozen()` est vrai (mode `.exe` figé) — jamais en mode
développeur (`python logx_serveur.py`, comme pendant toute session de travail avec
Claude Code). F4GLD confirme vouloir garder ce comportement tel quel (pas
d'ouverture auto en mode dev) — question posée et tranchée, ne pas revenir dessus
sauf nouvelle demande explicite.
