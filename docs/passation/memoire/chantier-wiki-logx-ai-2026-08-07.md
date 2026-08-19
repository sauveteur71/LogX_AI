---
name: chantier-wiki-logx-ai-2026-08-07
description: "Wiki GitHub créé sur sauveteur71/LogX_AI (pas le dépôt de code), 17 pages découpées depuis docs/GUIDE_UTILISATEUR.md"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T05:48:13.540Z
---

Demande F4GLD (07/08/2026, capture d'écran de la page wiki vide) : « peux
tu me faire le wiki ». Livré : https://github.com/sauveteur71/LogX_AI/wiki
— voir [[piege-deux-depots-github-distincts-logx-ai]] pour le piège de
dépôt rencontré en le faisant.

**Contenu** : `Home.md` + `_Sidebar.md` + 15 pages de contenu, découpées
mécaniquement (script Python, split sur `^## N. Titre`) depuis
`docs/GUIDE_UTILISATEUR.md` (1363 lignes, 15 sections) — pas réécrit à la
main, pour rester en phase avec le guide source sans double maintenance.
Les ancres internes du sommaire (`](#5-configurer-sa-station...)`) ont été
réécrites vers les noms de page wiki correspondants par regex.

**Piège technique rencontré** : un wiki GitHub vide n'a AUCUN dépôt git
tant que la première page n'a pas été créée via l'UI web (« Create the
first page ») — ni `git clone` ni `git push` direct sur
`<repo>.wiki.git` ne fonctionnent avant, avec le même message trompeur
« Repository not found » qu'une erreur d'auth ou de mauvais dépôt. Pas de
solution API (les wikis GitHub ne sont pas exposés par l'API REST/Contents,
seulement en git pur). Contourné en demandant à F4GLD de cliquer une fois
sur le bouton (30 secondes), après quoi le clone/push a fonctionné
normalement.

**Pourquoi pas fait via navigateur automatisé** : tenté d'abord via
`mcp__claude-in-chrome` (le vrai Chrome de l'utilisateur) en supposant que
la session GitHub y serait déjà connectée — faux, l'onglet ouvert montrait
« Sign in »/« Sign up », donc pas de session active dans ce profil Chrome.
Jamais tenté de se connecter (identifiants interdits) — juste demandé le
clic à l'utilisateur à la place.

**Comment mettre à jour ce wiki plus tard** : `git clone
https://github.com/sauveteur71/LogX_AI.wiki.git`, éditer les `.md`, commit,
`git push origin master` (les wikis GitHub utilisent `master`, pas `main`,
indépendamment de la branche par défaut du dépôt de code).
