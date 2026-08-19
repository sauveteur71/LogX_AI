---
name: projet-migration-repo-vers-logx-ai-planifiee
description: Migration planifiée (pas encore faite) — tout rapatrier sur le dépôt sauveteur71/LogX_AI plutôt que sur radioaamateur-program-Contest
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-12T13:47:52.388Z
---

F4GLD a demandé (12/08/2026) de finir par consolider les deux dépôts GitHub
sous le nom `LogX_AI` — actuellement le CODE vit sur
`sauveteur71/radioaamateur-program-Contest` et seul le SITE DE PRÉSENTATION
+ WIKI (16 pages) vivent sur `sauveteur71/LogX_AI` (repo séparé, découvert
en préparant [[chantier-version-1.0-preparation-2026-08-12]]).

**Décision explicite : PAS maintenant.** Chantier séparé et planifié, à
faire quand F4GLD le demandera — pas dans la foulée de la sortie de la 1.0.

**Contrainte confirmée par F4GLD** : l'URL actuelle du site
(`sauveteur71.github.io/LogX_AI/`) n'a PAS encore été diffusée publiquement
(groups.io, forum, QRZ...) — donc pas besoin de préserver cette URL exacte
lors de la migration, un changement d'adresse est acceptable.

## Pourquoi c'est délicat (analysé le 12/08, pas juste une copie de dossier)

1. **Mise à jour automatique** : `GITHUB_REPO = 'sauveteur71/radioaamateur-program-Contest'`
   dans `concours/logx_update.py` — chaque installation de LogX AI (y compris
   tous les postes qui ont déjà téléchargé la v1.0) vérifie les nouvelles
   releases sur CE nom de dépôt précis. À changer en même temps que la
   migration, pas après.
2. **Collision avec le site existant** : `LogX_AI` héberge déjà le site
   vitrine (`index.html` à la racine de sa branche `main`, GitHub Pages).
   Le dépôt de code a aussi besoin de la racine (`README.md`, `concours/`,
   `docs/`...) — réorganisation nécessaire (site dans un sous-dossier ou une
   branche `gh-pages` dédiée) pour ne pas écraser l'un avec l'autre.
3. **Wiki** : attaché au dépôt `LogX_AI` spécifiquement, ne suit pas
   automatiquement un renommage d'un AUTRE dépôt — recopie manuelle
   nécessaire (clone du wiki + push vers le wiki du dépôt final).
4. **Historique Git** : deux historiques séparés (~46 PR de développement
   côté code) — pas une simple copie, un renommage GitHub (préserve tout +
   redirection auto) est la voie la plus sûre plutôt qu'un nouveau push.
5. **Références à mettre à jour** : `docs/GROUPSIO_LOGX_AI.md`,
   `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `concours/logx_statusbar.js`
   (bouton « signaler un problème »), remote git local du poste de F4GLD.

## Plan retenu (à exécuter le jour venu, pas figé si mieux trouvé)

1. Renommer l'actuel `sauveteur71/LogX_AI` (site) vers un autre nom pour
   libérer « LogX_AI ».
2. Renommer `sauveteur71/radioaamateur-program-Contest` → `LogX_AI` (garde
   tout l'historique, les PR #1-#46 restent valides, redirection auto de
   l'ancienne URL).
3. Mettre à jour `GITHUB_REPO` dans `logx_update.py` (+ tout autre endroit
   listé ci-dessus) vers le nouveau nom, PR + release pour que la mise à
   jour auto le propage aux postes existants.
4. Recopier les 16 pages du wiki vers le wiki du dépôt renommé (clone +
   push, le wiki ne suit pas automatiquement).
5. Réintégrer le contenu du site vitrine (sous-dossier ou branche dédiée)
   sans écraser le code.
