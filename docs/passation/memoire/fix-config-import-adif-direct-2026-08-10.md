---
name: fix-config-import-adif-direct-2026-08-10
description: CONFIG "Importer un log existant" ouvre maintenant le sélecteur de fichier directement, sans passer par LOGBOOK, PR #20
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-11T04:58:51.408Z
---

Signalé par F4GLD juste après le merge de [[chantier-score-a-battre-import-anciens-logs-2026-08-10]] :
« dans config : importer un log renvoie sur la page logbbok! ». Confirmé
par capture d'écran : ce n'était PAS le nouveau panneau « IMPORTER
D'ANCIENS LOGS » (score à battre), mais un bouton PRÉEXISTANT (avant cette
session, 09/08/2026) tout en haut de la barre latérale CONFIG, « Importer
un log existant », qui naviguait vers `logx_logbook.html?action=import`
puis rouvrait là-bas le menu DÉBUT/FIN pour atteindre `triggerImport()`.

## Correctif (PR #20)

Le bouton ouvre maintenant directement le sélecteur de fichier natif, EN
RESTANT sur CONFIG : nouvelle fonction `triggerConfigImportAdif()` +
`_previewConfigImportAdif()` dans `logx_configuration.js`, qui appellent
les MÊMES endpoints serveur que LOGBOOK (`/log/import_adif/preview` puis
`/commit`, `logx_import_adif.js`) — aucune logique serveur dupliquée.
L'aperçu (QSO nouveaux/doublons/erreurs) et la confirmation passent par
l'infra bandeau/toast déjà en place sur CONFIG (`_confirmConfigBanner()`/
`_configToast()`, chantier dialogues non bloquants du 10/08), pas la
modale `#importOverlay` propre à LOGBOOK (absente de cette page).

Code mort corrigé côté LOGBOOK : le handler `?action=import` dans
`logx_logbook.js` (qui rouvrait le menu DÉBUT/FIN à l'arrivée) n'avait
plus qu'un seul appelant — supprimé avec le changement du bouton CONFIG.

## Piège évité (documenté par le commentaire d'origine, pas re-découvert)

Le commentaire du code de 09/08/2026 expliquait pourquoi CONFIG ne
déclenchait pas `triggerImport()` directement à l'époque : un sélecteur
de fichier (`<input type=file>.click()`) exige un geste utilisateur réel,
qu'une navigation de page NE GARANTIT PAS de façon fiable selon les
navigateurs — appeler `.click()` automatiquement APRÈS un chargement de
page (sur LOGBOOK, après la redirection) n'est pas un geste utilisateur
valide partout. Ce piège ne s'applique PAS au nouveau code : le
`.click()` est appelé en réponse SYNCHRONE au clic du bouton CONFIG
lui-même, sans navigation entre les deux — geste valide dans tous les
navigateurs. Vérifié en le disant explicitement dans le commentaire du
correctif pour qu'une future relecture ne réintroduise pas l'ancien
détour par erreur.

## Vérification faite

Suite pytest complète + `ruff check` verts. Navigateur réel (port isolé
8099) : `_previewConfigImportAdif()` appelé avec un ADIF de test → bandeau
d'aperçu affiché (« 2 QSO dans le fichier — 2 nouveaux, 0 déjà dans le
log »), URL jamais changée (reste `logx_configuration.html`) → clic
« Importer » → toast de résultat (« Import terminé : 2 QSO importés »)
→ confirmé via `GET /log/list` que les 2 QSO sont réellement dans le log
partagé (`source: "adif_import"`), pas juste une UI qui ment.

PR #20 fusionnée sur main le 10/08/2026.
