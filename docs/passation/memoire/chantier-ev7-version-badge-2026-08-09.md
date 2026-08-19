---
name: chantier-ev7-version-badge-2026-08-09
description: "EV-7 35e incrément — extraction BADGE VERSION RÉSEAU vers logx_version_badge.js (09/08, merge e289adb)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T10:52:51.280Z
---

35e incrément de la campagne EV-7 (LogX AI) : extraction de 8 fonctions
(~164 lignes) depuis `logx_logbook.js` vers `concours/logx_version_badge.js` :
`_versionMismatches()`, `updateVersionStatus()`, `findNetworkUpdatePath()`,
`_renderNetworkUpdatePath()`, `startNetworkUpdate()`,
`_pollNetworkUpdateStatus()`, `installNetworkUpdate()`,
`_pollServerBackUpAfterNetworkUpdate()`. Dernier des 2 candidats FAIBLE du
4e inventaire (voir [[chantier-ev7-shortcut-offer-2026-08-09]] pour le
premier). Fusionné sur main : commit e289adb (merge), 3c7b499 (contenu).

**Particularité inédite dans la campagne : l'ÉTAT reste dans le coeur, seules
les FONCTIONS bougent.** Contrairement à tous les incréments précédents (où
état + fonctions migrent ensemble), les 3 variables `_myVersion`/
`_lastServerVersion`/`_lastPeerList` sont restées dans `logx_logbook.js` :
`_myVersion` est écrite par `initShareLink()` (coeur, depuis `/network/info`)
et lue par `fetchLog()` (coeur, paramètre `?ver=`) — deux sites du coeur
totalement en dehors du bloc extrait, donc l'état ne pouvait pas suivre les
fonctions sans casser cette dépendance interne au coeur.
`_lastServerVersion`/`_lastPeerList` sont écrites par `updateVersionStatus()`
et lues par `findNetworkUpdatePath()` — toutes deux dans le NOUVEAU fichier,
donc sans risque d'ordre entre elles malgré leur déclaration restée ailleurs.

**How to apply :** avant de supposer qu'un bloc candidat doit migrer en bloc
(état + fonctions), vérifier explicitement CHAQUE variable d'état pour des
lecteurs/écrivains situés HORS du bloc candidat — si un seul lecteur/écrivain
externe existe, l'état doit rester dans le coeur et seule la logique qui
l'utilise à l'intérieur du bloc migre. Un nouveau motif à surveiller pour les
incréments futurs.

**Revue adversariale (Workflow, 2 dimensions) : 2 constats mineurs
confirmés**, tous deux des commentaires d'en-tête inexacts, sans impact
fonctionnel — corrigés dans le commit :
1. `logx_verif_panel.js` affirmait que `logx_version_badge.js` charge AVANT
   lui ; c'est l'inverse (logx_verif_panel.js charge en premier).
2. `logx_version_badge.js` attribuait l'écriture de `_myVersion` à l'endpoint
   `/log/status` ; c'est en réalité `/network/info` (via `initShareLink()`).
   Erreur préexistante déjà présente dans un commentaire de `logx_logbook.js`
   non touché par cet incrément — le 35e incrément l'a seulement recopiée
   dans le nouvel en-tête plutôt que de l'introduire.

**3e constat rejeté (attendu, sans action)** : dérive `custom_contests.json`
hors périmètre — confirmé par la revue comme non lié, jamais staged, comme
convenu depuis le début de la campagne.

Suite pytest 100% verte, vérification navigateur réelle (serveur prod port
8080, jamais redémarré) : `_versionMismatches()` exercée avec des valeurs
synthétiques (fonction pure), `updateVersionStatus()` exercée avec un objet
synthétique (effet DOM réel observé puis remis à zéro pour ne pas polluer la
session live). `findNetworkUpdatePath()`/`startNetworkUpdate()`/
`installNetworkUpdate()` volontairement NON exercées en conditions réelles
(effets de bord réseau réels : scan, téléchargement, installation/redémarrage)
— seul leur `typeof` vérifié.

**Contexte inhabituel de ce commit** : appliqué par-dessus un commit sans
rapport (001e5f5, feature UI « faciliter l'import de log ») poussé
directement sur main entre le début et la fin de ce chantier — géré sans
incident car les deux touchent des zones non-chevauchantes de
`logx_logbook.js` (voir aussi la technique de séparation de hunks documentée
dans la mémoire de session si besoin de la répliquer).

**Fin du 4e inventaire** : les 2 seuls candidats FAIBLE identifiés
(raccourci bureau=34e, badge version=35e) sont maintenant tous deux
fusionnés — cet inventaire est épuisé.
