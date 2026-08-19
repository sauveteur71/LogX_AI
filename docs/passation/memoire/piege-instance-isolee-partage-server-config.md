---
name: piege-instance-isolee-partage-server-config
description: "Une \"instance isolée\" (autre port) pour vérifier CONFIG en navigateur écrit quand même dans le VRAI .server_config.json partagé — testAmpConnection() n'est pas dangereux, saveConfig() l'est"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-06T06:59:42.895Z
---

Une instance de `logx_serveur.py`/`logx_http.py` lancée sur un AUTRE port
(ex. 8099, pour ne jamais toucher le serveur de production réel sur 8080,
règle standard de cette session) N'EST PAS réellement isolée dès qu'un test
appelle `saveConfig()`/`POST /config/save` — les deux processus tournent
depuis le MÊME répertoire (`concours/`) et lisent/écrivent le MÊME fichier
`.server_config.json` (chemin relatif codé en dur dans `logx_http.py`,
`SERVER_CONFIG_FILE = '.server_config.json'`). Un port différent isole le
RÉSEAU (aucun risque de piloter du vrai matériel via le port de production
en vie), mais pas le DISQUE.

Trouvé en vérifiant les nouveaux champs réseau KPA1500 (06/08/2026) : un
onglet navigateur pointé sur `http://127.0.0.1:8099` avait déjà, dans SON
`localStorage` (persistant, laissé par une vérification antérieure sur ce
même port lors d'une session précédente), la vraie config F4GLD/REF_RPH —
`loadSavedConfig()` la restaure dans le DOM au chargement (`hasLocal=true`),
donc la page a l'air "normale". Modifier 3 champs de test (amp_conn_mode/
amp_host/amp_net_port) puis appeler `saveConfig(true)` pour vérifier le
round-trip a réécrit le VRAI fichier partagé avec ces 3 valeurs de test —
zéro autre champ touché (callsign/mots de passe/CAT intacts, vérifié par
déchiffrement direct via `logx_crypto.decrypt_config()` et comparaison des
146 clés), mais un vrai effet de bord sur disque quand même. Le serveur de
production (8080) n'a rien vu tant qu'il ne redémarre pas (son
`current_config` est en mémoire, chargé une seule fois au démarrage) — mais
un redémarrage ultérieur aurait chargé les valeurs de test.

**Piège annexe rencontré en essayant de vérifier "rien d'autre n'a changé"** :
`fetch('/config.json')` (utilisé par `loadFromServerConfig()` comme repli
navigateur) lit un fichier `config.json` **totalement différent** et sans
rapport (config avancée station/contest/api, séparée, souvent absente/vide
sur cette installation) — PAS `.server_config.json`. Comparer les deux
serveurs via cet endpoint a fait croire un instant que les deux configs
étaient identiques (les deux renvoyaient `{}`), ce qui était un faux
négatif complet et aurait pu masquer un vrai problème. Le seul moyen fiable
de lire le VRAI `current_config` partagé est de déchiffrer
`.server_config.json` directement en Python (`logx_crypto.decrypt_config`),
pas de taper un endpoint HTTP au hasard qui porte un nom qui y ressemble.

**Comment réparer sans confiance aveugle** : la correction du fichier
partagé (retirer les clés injectées par erreur) a été refusée par le
classifieur auto-mode (écriture jugée sensible, à raison) — il a fallu
s'arrêter et demander la permission explicite à l'utilisateur plutôt que de
contourner. Cette pause était la bonne réaction, pas un blocage à éviter.

**Why:** Le port différent protège le matériel radio réel (jamais de risque
de PTT involontaire sur la vraie station), mais donne une fausse impression
de sandbox complet — le fichier de config, lui, n'est isolé par AUCUN
mécanisme existant (pas de `--config-dir`, pas de variable d'environnement
pour changer `SERVER_CONFIG_FILE`).

**How to apply:** Avant toute vérification navigateur qui touche
CONFIG/logx_configuration.html sur une "instance isolée" :
1. Ne JAMAIS appeler une action qui persiste (`saveConfig()`, tout ce qui
   POST vers `/config/save`, `/ui/theme`, `/data/spot_filter`...) sans avoir
   d'abord vérifié que ce port n'a pas de `localStorage['logx_config']`
   préexistant contenant de vraies données (`localStorage.getItem(...)`).
2. Pour tester UNIQUEMENT le rendu/la visibilité de champs (comme
   `updateAmpFieldsVisibility()`), lire `getComputedStyle(...).display` ou
   `.value` suffit — pas besoin de sauvegarder.
2bis. Pour tester un endpoint d'action éphémère non persistante (comme
   `/amp/test`, qui n'écrit jamais `current_config`), c'est totalement
   sans risque — le distinguer clairement d'un endpoint qui PERSISTE avant
   de décider si un appel est sûr.
3. Si une sauvegarde réelle est nécessaire pour le test, envisager de
   sauvegarder l'état du disque AVANT (copier `.server_config.json`) pour
   pouvoir restaurer par un simple `cp` plutôt que de reconstruire l'état
   depuis zéro après coup.
4. Pour lire l'état RÉEL partagé (production) sans passer par un endpoint
   HTTP dont on n'est pas sûr du fichier source, déchiffrer directement
   `.server_config.json` en Python via `logx_crypto.decrypt_config()`.

Voir aussi [[chantier-cat-plug-and-play-2026-08]] et les autres chantiers de
vérification navigateur de cette session — le motif "instance isolée port
différent" est la pratique standard recommandée par CLAUDE.md pour vérifier
les deux thèmes jour/nuit ; ce piège ne remet pas cette pratique en cause,
il ajoute juste une précaution supplémentaire spécifique à CONFIG.
