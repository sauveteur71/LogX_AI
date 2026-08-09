# API locale — LogX AI

> **Documentation vivante, pas un contrat figé.** Ce document décrit les endpoints HTTP tels qu'ils existent aujourd'hui dans `concours/logx_http.py` (222 routes recensées, toutes actives dans le code). Contrairement à `contest_schema.json` (contrat de définition de concours versionné avec politique de migration, voir EV-6.2 du PRD), cette API HTTP n'a **pas** de numéro de version ni de garantie de compatibilité ascendante : un chemin, un paramètre ou une forme de réponse peut changer d'une version du logiciel à l'autre sans annonce préalable. Un outil tiers qui s'appuie dessus doit prévoir cette possibilité, et se référer au code source en cas de doute — c'est lui qui fait foi, pas cette page.

LogX AI n'expose pas d'API distante : le « serveur » dont il est question ici est le petit serveur HTTP local que le logiciel démarre sur le poste de l'opérateur (`python logx_serveur.py`, ou l'exécutable autonome). Cette page documente ces endpoints dans l'esprit d'EV-6.5 du PRD — s'en inspirer pour un script d'automatisation, un tableau de bord externe, une intégration avec un autre logiciel de station — sur le modèle des API REST locales de Cloudlog ou Wavelog.

## Base et format

- **URL de base** : `http://127.0.0.1:8080` par défaut (port `PORT` dans `logx_utils.py`). Un seul poste peut faire tourner le serveur à la fois (le port n'accepte qu'une instance) ; les autres appareils du réseau local (téléphone, tablette, second PC) s'y connectent par l'IP LAN du poste hôte plutôt que `127.0.0.1` — voir `GET /network/info` pour la découvrir dynamiquement.
- **Format des réponses** : JSON dans l'immense majorité des cas. Exceptions signalées route par route : export Cabrillo/ADIF (texte brut en pièce jointe), GeoJSON, flux binaires (mise à jour, panneau relayé), pages HTML (connexion, callback OAuth SOTA), flux SSE (`text/event-stream`).
- **Encodage** : UTF-8 partout, y compris pour les indicatifs et libellés accentués.
- **Codes d'erreur** : le logiciel renvoie en général `{"error": "..."}` ou `{"ok": false, "error": "..."}` avec un code HTTP explicite (400 validation, 403 non autorisé, 404 introuvable, 409 doublon, 413 corps trop volumineux, 429 limite de fréquence, 502 backend matériel indisponible) — le détail par route est précisé ci-dessous quand il diffère de ce comportement par défaut.

## Sécurité — modèle réel du serveur

LogX AI est pensé pour un réseau local de confiance (une station, un radioclub, une expédition), pas pour être exposé sur l'Internet public. Ce qui suit décrit le comportement **réel** du serveur, vérifié dans `concours/logx_http.py` et `concours/logx_serveur.py` — pas une intention affichée ailleurs :

- **Le serveur écoute sur `0.0.0.0`** (toutes les interfaces réseau du poste), pas seulement `127.0.0.1`. C'est voulu : c'est ce qui permet à un autre poste du même WiFi (multi-opérateur, écran mural d'expédition, téléphone terrain) d'ouvrir le logbook sans rien installer. Corollaire à connaître : si le port est redirigé vers l'Internet public (NAT/port-forwarding sur un routeur), le serveur devient joignable depuis n'importe où — à éviter ; aucune protection listée ici ne remplace un pare-feu correctement configuré.
- **Aucun mot de passe par défaut.** Tant qu'aucun mot de passe d'accès n'est configuré (`POST /auth/set_password`), un jeton de session (cookie `rc_token`, `SameSite=Strict`) est distribué automatiquement à tout navigateur qui charge une page du logiciel — n'importe quel appareil du LAN capable d'ouvrir `http://<IP>:8080/` l'obtient donc sans rien saisir. C'est le même modèle de confiance qu'un dossier partagé non protégé sur le réseau d'un club.
- **Toutes les routes qui écrivent (POST, DELETE) exigent ce jeton**, envoyé soit via le cookie `rc_token` (cas du navigateur), soit via l'en-tête `X-RC-Token: <jeton>` (cas d'un script qui n'est pas un navigateur). Seule `POST /auth/login` y échappe, puisque c'est elle qui le distribue. Pour un outil tiers qui tourne sur la **même machine** que le serveur, le jeton est lisible directement dans le fichier `.auth_token` du dossier de données (voir `docs/GUIDE_UTILISATEUR.md`, section « Où sont vos données ? », pour son emplacement exact selon l'OS).
- **La plupart des routes de lecture (GET) ne demandent rien** — même logique que `GET /log/status` : un pair légitime du réseau local n'a pas à s'authentifier pour consulter le score ou la liste des QSO en train de se construire. Quelques GET sensibles (secrets de configuration, journal d'erreurs Python, diagnostics réseau) exigent quand même le jeton — précisé route par route ci-dessous quand c'est le cas.
- **Mot de passe d'accès optionnel** (`POST /auth/set_password`) : bascule le comportement par défaut — le cookie n'est plus distribué automatiquement à l'ouverture d'une page, `GET /auth/login` devient le seul point d'entrée pour l'obtenir, le mot de passe est vérifié en temps constant contre un hash PBKDF2-HMAC-SHA256 salé (jamais stocké en clair), et les tentatives sont limitées en fréquence par IP (anti-bruteforce, 5 essais/minute). Utile pour un radioclub sur un WiFi partagé avec des visiteurs.
- **Pas de TLS.** Le trafic — y compris les identifiants de services tiers transmis via `POST /config/save` (ON4KST, QRZ, LoTW...) — circule en clair sur le réseau local. C'est un compromis assumé pour un logiciel qui doit rester un exécutable autonome sans certificat à gérer : ne pas l'utiliser sur un réseau qui n'est pas de confiance.
- Quelques routes sont **spécifiquement réservées à des postes LogX AI du même LAN** (relais de mise à jour `/app/update_relay`, `/app/gateway_status`, `/app/update_serve*`, export `/log/lan/export`) : elles répondent 403 à une IP qui ne s'est jamais fait connaître comme pair de ce serveur, indépendamment du jeton de session — mécanisme anti-SSRF détaillé route par route plus bas.

## Comment s'authentifier depuis un script tiers

Pour un outil externe (ligne de commande, tableau de bord, intégration avec un autre logiciel) qui doit appeler une route d'écriture :

1. Localiser `.auth_token` dans le dossier de données du serveur (si le script tourne sur la même machine), ou récupérer le cookie `rc_token` en ouvrant une page du logiciel dans un client HTTP qui conserve les cookies.
2. Envoyer ce jeton dans l'en-tête `X-RC-Token` de chaque requête d'écriture.
3. Si un mot de passe d'accès est configuré, passer d'abord par `POST /auth/login` (ou lire `.auth_token` localement, qui reste valide indépendamment du mot de passe une fois le serveur démarré).

Les routes de lecture qui ne touchent pas à des données sensibles n'ont besoin d'aucun de ces trois points.

## Statut de ce document

Cette page recense **222 routes** actives de `concours/logx_http.py` (221 routes extraites automatiquement + `DELETE /qtc/delete/<id>`, retrouvée en relisant le code pendant la vérification de cette documentation), regroupées en **27 catégories** fonctionnelles. Chaque entrée précise la méthode HTTP, les paramètres attendus, la forme de la réponse et, quand c'est pertinent, les prérequis (clé API IA, matériel connecté, service tiers, mode `debug`...). Les routes qui ne servent aujourd'hui qu'à l'interface interne du logiciel (état d'un job IA en tâche de fond, flux SSE, pages HTML de connexion) sont documentées elles aussi : un outil tiers peut vouloir les rejouer, même si elles n'ont pas été conçues pour ça au départ.

## Sommaire

- [Journal de trafic (log)](#journal)
- [Configuration et authentification](#config)
- [Callbook et historique d'indicatifs](#callbook)
- [Règlements et calendrier des concours](#rules)
- [Vérification d'échange](#exchange)
- [Diplômes et récompenses (awards)](#awards)
- [Chasse géographique (départements, DXCC, cartes)](#geochase)
- [Programmes d'activation (POTA/SOTA/IOTA/WWFF/WCA)](#activation)
- [DXpeditions](#dxpeditions)
- [École CW](#cwschool)
- [Propagation, astronomie et écoute à distance](#propagation)
- [WebSDR](#websdr)
- [Cluster DX, spots et band map](#cluster)
- [Radio (CAT), SO2R et panadapter](#radio)
- [Amplificateur](#amp)
- [Rotor d'antenne](#rotor)
- [Station Control (relais)](#relay)
- [Manipulateur CW (WinKeyer) et keyer vocal (DVK)](#cwkeyer)
- [FT8 / WSJT-X et Wait-and-Pounce](#ft8)
- [Multi-opérateur : chat, écran mural, planning, synchro LAN](#multiop)
- [Synchronisation, sauvegarde et score en direct](#sync)
- [QSL](#qsl)
- [Assistant IA (coach, agent, proxy)](#ai)
- [Mise à jour logicielle](#update)
- [Réseau, diagnostic et télémétrie](#network)
- [Système et divers](#misc)
- [Recherche et fichiers statiques](#static)

---

## Journal de trafic (log)

<a id="journal"></a>

### GET `/log/list`

Liste tous les QSO du journal partagé (shared_log), avec synchronisation différentielle et détection d'inchangé pour limiter la bande passante des pollings répétés.

- **Paramètres** : v (version connue du client, évite un renvoi si inchangé) ; since/boot (synchro différentielle, ne renvoie que les QSO modifiés + IDs supprimés depuis) ; ver (version logicielle déclarative du poste, filtrée par regex)
- **Réponse** : {unchanged:true,...} si rien n'a changé, sinon {qsos ou delta+qsos/deleted, total, peers, score, version, boot}
- **Note** : Filtré par la portée du concours actif (contest+année) en mode concours/expédition ; enregistre l'IP du client comme pair connecté.

**Exemple** :

```bash
curl "http://127.0.0.1:8080/log/list"
```

### GET `/log/next_serial`

Alloue (ou aperçoit avec ?peek=1) le prochain numéro de série pour une bande donnée, côté serveur, pour éviter les doublons entre postes en multi-poste.

- **Paramètres** : band (bande concernée) ; peek (1/true = aperçu sans consommer le compteur)
- **Réponse** : {serial: '001'}
- **Note** : ?peek=1 est ouvert au LAN sans jeton ; la consommation réelle (sans peek) exige le jeton de session. Portée par concours+année (scope_id).

### GET `/log/check`

Vérifie le statut d'un indicatif à la frappe : nouveau, doublon, ou nouveau multiplicateur, en réutilisant le moteur de scoring.

- **Paramètres** : call, band, mode
- **Réponse** : {status: 'inconnu'|'doublon'|'nouveau'|'nouveau_mult', points, mult_type, explanation}
- **Note** : Aucune règle de doublon appliquée si usage_mode='simple' (logbook simple).

### GET `/log/validate`

Valide le log complet avant soumission : départements/locators/doublons/fenêtre du concours (spécial REF).

- **Paramètres** : aucun
- **Réponse** : objet validator.validate_log(log_copy, contest, cfg_snap)
- **Note** : Lecture seule.

### GET `/log/audit/state`

État d'un audit IA du log lancé en tâche de fond par POST /log/audit.

- **Paramètres** : id (identifiant de la tâche d'audit)
- **Réponse** : {id, status, ...}

### GET `/log/archives`

Liste des archives de concours (dossiers permanents) déjà clôturées.

- **Paramètres** : aucun
- **Réponse** : {'archives':[...]}

### GET `/qtc/list`

Total et détail des QTC (relais de trafic WAE) pour la portée courante (concours/année).

- **Paramètres** : aucun
- **Réponse** : {'total':int,'entries':[...50 derniers...]}
- **Note** : spécifique au règlement WAE (QTC)

### GET `/log/export/cabrillo`

Exporte le log de la portée courante (concours+année) au format Cabrillo v3, en pièce jointe téléchargeable.

- **Paramètres** : aucun (contest lu en config)
- **Réponse** : corps texte/plain, en-tête Content-Disposition attachment, fichier .cbr
- **Note** : nom de fichier et indicatif assainis (anti-injection d'en-tête)

**Exemple** :

```bash
curl -o mon_log.cbr "http://127.0.0.1:8080/log/export/cabrillo"
```

### GET `/log/export/adif`

Exporte le log de la portée courante (concours+année) au format ADIF 3, en pièce jointe téléchargeable.

- **Paramètres** : aucun (contest lu en config)
- **Réponse** : corps texte/plain, en-tête Content-Disposition attachment, fichier .adi
- **Note** : nom de fichier et indicatif assainis (anti-injection d'en-tête)

**Exemple** :

```bash
curl -o mon_log.adi "http://127.0.0.1:8080/log/export/adif"
```

### POST `/qtc/add`

Enregistre une série QTC (règlement WAE) émise ou reçue avec une station.

- **Paramètres** : JSON {call, direction:'sent'|'recv', band?, mode?, series_number?, entries?:[{time,call,nr}] (1 à 10), count?}
- **Réponse** : {ok:true, total, with_call, id} ou {ok:false, error}
- **Note** : Plafond réglementaire WAE : 10 QTC maximum par station et par portée concours/année.

### DELETE `/qtc/delete/<id>`

Supprime une série QTC mal saisie par son id (numéro dans l'URL).

- **Paramètres** : id entier dans le chemin d'URL (`/qtc/delete/12`) ; aucun corps JSON
- **Réponse** : `{'ok': true, 'deleted': N}`
- **Note** : Route absente de l'extraction automatique de départ, retrouvée en relisant `do_DELETE` dans `concours/logx_http.py` pendant la vérification de ce document — même modèle d'authentification que `DELETE /log/delete/<id>` (jeton de session requis).

### POST `/log/update`

Corrige un QSO déjà présent dans le journal (remplacement complet de l'entrée par son id).

- **Paramètres** : Corps JSON : QSO complet incluant 'id'
- **Réponse** : {'ok':true} ou {'ok':false,'error':...} 404 si le QSO id a déjà été supprimé entre-temps par un autre poste
- **Note** : Détecte un changement de portée concours+année (correction de date) et déclenche mark_hard_reset() pour la synchro différentielle entre postes (/log/list?since=)

**Exemple** :

```bash
curl -X POST "http://127.0.0.1:8080/log/update" \
  -H "Content-Type: application/json" \
  -H "X-RC-Token: $(cat .auth_token)" \
  -d '{"id":42,"call":"F4GLD","band":"20m","mode":"SSB","rst_sent":"59","rst_rcvd":"59"}'
```

### POST `/log/add`

Ajoute un nouveau QSO au journal partagé.

- **Paramètres** : Corps JSON : QSO avec 'call' requis, 'force' optionnel (bool, pour forcer malgré un doublon détecté)
- **Réponse** : {'ok':true,'total':N,'duplicate':false} ; ou {'ok':false,'duplicate':true,'existing':{...},'error':...} code 409 si doublon détecté (même indicatif/bande/mode) sans force=true

**Exemple** :

```bash
curl -X POST "http://127.0.0.1:8080/log/add" \
  -H "Content-Type: application/json" \
  -H "X-RC-Token: $(cat .auth_token)" \
  -d '{"call":"F4GLD","band":"20m","mode":"SSB","rst_sent":"59","rst_rcvd":"59"}'
```

### POST `/log/delete/<id>`

Supprime un QSO par son id (variante POST, équivalente à DELETE /log/delete/<id> vu ailleurs dans le fichier).

- **Paramètres** : id entier dans le chemin d'URL
- **Réponse** : {'ok':true,'deleted':N}
- **Note** : Pose un tombstone (mark_qso_deleted) pour la synchro différentielle entre postes, et supprime le fichier de scan QSL attaché s'il existe (logx_qsl_scan.delete_scan)

**Exemple** :

```bash
curl -X POST "http://127.0.0.1:8080/log/delete/42" \
  -H "X-RC-Token: $(cat .auth_token)"
```

### POST `/log/import_adif/preview`

Aperçu d'un import ADIF SANS rien écrire : compte les QSO nouveaux, doublons et erreurs.

- **Paramètres** : Corps JSON : adif (texte ADIF brut)
- **Réponse** : Résultat de logx_import.preview_import(adif, snapshot) — statistiques d'aperçu, code 200 si ok sinon 400

### POST `/log/import_adif/commit`

Importe réellement les QSO neufs d'un fichier ADIF dans le journal partagé (écriture disque unique, sans push Club Log Live car import historique).

- **Paramètres** : Corps JSON : adif (texte ADIF brut)
- **Réponse** : {'ok':true,'imported':N,'errors':[...],'total':N}
- **Note** : IDs QSO alloués sous verrou de manière autoritaire pour éviter une collision avec un /log/add concurrent

### POST `/log/import_adif/etats`

Enrichit les QSO déjà au journal avec l'état US (diplôme WAS) et fusionne les confirmations QSL à partir d'un rapport ADIF LoTW/ClubLog — n'ajoute aucun nouveau QSO.

- **Paramètres** : Corps JSON : adif (texte ADIF de confirmations)
- **Réponse** : {'ok':true,'states_filled':N,'calls':N,'confirmations':N}
- **Note** : Invalide aussi le cache des diplômes (logx_awards.invalidate())

### POST `/log/reset`

Réinitialise complètement le journal courant après archivage permanent par portée (concours+année) dans un dossier (log.json + Cabrillo + ADIF + résumé), y compris les séries QTC associées.

- **Paramètres** : Corps JSON : confirm doit valoir exactement 'RESET'
- **Réponse** : {'ok':true,'archived':...,'folders':[...]} ou {'error':'Confirmation requise'} 400
- **Note** : Action destructive protégée par confirmation explicite ; ne retire du journal que les QSO effectivement archivés (par id), pas ceux ajoutés pendant l'archivage

### POST `/log/archive`

Archive le concours ACTIF (portée courante) dans un dossier permanent, sans effacer sauf clear=true.

- **Paramètres** : Corps JSON : clear (bool optionnel, vide aussi le journal courant après archivage réussi)
- **Réponse** : Résultat de arch.archive_log(...), avec 'cleared':true si clear demandé et réussi ; code 200 si ok sinon 400
- **Note** : Sans concours sélectionné (ou logbook 'simple'), ne porte que sur les QSO non tagués — jamais tout le journal


## Configuration et authentification

<a id="config"></a>

### GET `/config`

Config PUBLIQUE de l'écran mural d'expédition (whitelist stricte, aucun secret) : callsign, locator, concours, mode d'usage, etc.

- **Paramètres** : aucun
- **Réponse** : objet config restreinte aux champs non sensibles

**Exemple** :

```bash
curl "http://127.0.0.1:8080/config"
```

### GET `/config.json`

Sert le fichier config.json (structure imbriquée station/contest lue par la page mobile), en retirant systématiquement la section 'server' (jeton/debug).

- **Paramètres** : aucun
- **Réponse** : contenu JSON de config.json sans la clé 'server'
- **Note** : le fichier brut est bloqué au service statique pour ne jamais fuiter le jeton

### GET `/config/secrets`

Sert séparément les champs de configuration secrets (mots de passe, clés API, jetons) au client authentifié, pour éviter de les garder en clair dans localStorage.

- **Paramètres** : aucun
- **Réponse** : objet {champ: valeur} pour les champs de logx_crypto.SECRET_FIELDS
- **Note** : nécessite jeton d'authentification (_require_auth)

### GET `/auth/status`

État courant du mot de passe d'accès optionnel : activé ou non, et si le client courant est déjà autorisé.

- **Paramètres** : aucun
- **Réponse** : {'enabled':bool,'authorized':bool}
- **Note** : jamais le hash du mot de passe

**Exemple** :

```bash
curl "http://127.0.0.1:8080/auth/status"
```

### GET `/auth/login`

Page de connexion HTML : seule porte d'entrée du jeton d'écriture quand un mot de passe d'accès est configuré.

- **Paramètres** : next (string, URL de redirection après connexion)
- **Réponse** : page HTML du formulaire de connexion
- **Note** : reste joignable même quand la protection est active

### POST `/config/save`

Sauvegarde/remplace intégralement la configuration courante du serveur.

- **Paramètres** : Corps JSON = objet configuration complet
- **Réponse** : {ok:true} ou {error}
- **Note** : REMPLACE tout current_config (jamais un patch partiel) ; refuse si deux transverters actifs sur la même FI ; change la portée visible du journal (concours+année).

**Exemple** :

```bash
curl -X POST "http://127.0.0.1:8080/config/save" \
  -H "Content-Type: application/json" \
  -H "X-RC-Token: $(cat .auth_token)" \
  -d @config.json
```

### POST `/auth/set_password`

Définit (mot de passe non vide) ou désactive (vide) le mot de passe d'accès au serveur.

- **Paramètres** : JSON {password: string}
- **Réponse** : {ok, enabled}
- **Note** : Mot de passe non vide : 4 caractères minimum ; repose immédiatement un cookie rc_token valide après rotation du jeton.

### POST `/ui/theme`

Définit le thème jour/nuit, partagé entre tous les postes connectés en multi-poste.

- **Paramètres** : JSON {theme: 'day'|'night'}
- **Réponse** : {ok:true} ou {error}
- **Note** : Ne modifie que cette clé de la config, jamais un remplacement complet (à la différence de /config/save).


## Callbook et historique d'indicatifs

<a id="callbook"></a>

### GET `/calldb/lookup/<call>`

Résout un indicatif en locator/pays : cherche d'abord dans le cache local calldb.json, puis interroge HamQTH si inconnu, et persiste le résultat par fusion dans calldb.json.

- **Paramètres** : <call> dans le chemin (indicatif à résoudre)
- **Réponse** : {call, locator, dept?, country?, source: 'local'|'hamqth'|'none'} ou {error} en 400
- **Note** : Appel réseau HamQTH (service tiers) si absent du cache local ; écriture-lecture-modification sous calldb_lock pour éviter les écrasements concurrents.

**Exemple** :

```bash
curl "http://127.0.0.1:8080/calldb/lookup/9A1CIG"
```

### GET `/qrz/lookup`

Recherche d'un indicatif en cascade : QRZ.com (si identifiants configurés) puis HamQTH puis HamDB.

- **Paramètres** : call (indicatif recherché)
- **Réponse** : résultat de callbook.lookup(...) enrichi de {enabled: true}
- **Note** : Nécessite éventuellement des identifiants QRZ configurés côté serveur (lus depuis la config, jamais depuis la requête) ; service tiers.

### GET `/log/bulk_resolve/status`

Renvoie la progression de la re-résolution en masse des indicatifs démarrée par POST /log/bulk_resolve/start.

- **Paramètres** : aucun
- **Réponse** : objet callbook.bulk_resolve_status()
- **Note** : Pollé côté client pendant une opération de fond déjà lancée.

### GET `/call/index`

Index d'indicatifs fusionné (MASTER.SCP + calldb + archives + qso_archive + log courant) pour le Super Check Partial, enrichi de qso_count/worked/last_date.

- **Paramètres** : aucun (utilise le concours actif de la config)
- **Réponse** : objet callhistory.export_index(log_copy, contest=...)
- **Note** : Le concours actif surclasse dept/locator/nom/section/zone avec le Call History N1MM importé pour ce concours.

### GET `/call/history`

Historique complet (toute la vie du log) des QSO avec une station donnée, plus statut 'nouveau à vie', besoin LoTW, état US/province, et si la station uploade vers LoTW.

- **Paramètres** : call, band (optionnel), mode (optionnel)
- **Réponse** : objet awards.history(...) enrichi de new_one/lotw_need/state/lotw_user/lotw_last

### GET `/call/near`

Vérification 'N+1' (busted call check façon N1MM) : indicatifs connus à distance de Damerau-Levenshtein 1 de celui tapé.

- **Paramètres** : call (indicatif tapé)
- **Réponse** : {matches: [...]}
- **Note** : Calcul 100% local, aucun réseau.

### GET `/callhistory/status`

État des imports (bouton CONFIG) : nombre d'indicatifs MASTER.SCP importés et nombre de fiches Call History pour le concours actif.

- **Paramètres** : contest (optionnel, prioritaire sur la config serveur sauvegardée)
- **Réponse** : {master_scp_count, contest, call_history_count}

### POST `/calldb/update`

Met à jour manuellement le locator et/ou le département d'un indicatif dans calldb.json.

- **Paramètres** : Corps JSON : call (requis), locator, dept optionnels
- **Réponse** : {'ok':true}
- **Note** : Lecture-modification-écriture protégée en ENTIER par calldb_lock (pas seulement l'écriture) pour éviter qu'une correction concurrente n'écrase l'autre

### POST `/callhistory/import_scp`

Importe un fichier MASTER.SCP (Super Check Partial N1MM) dans l'index de suggestion d'indicatifs de logx_callhistory.py.

- **Paramètres** : Corps JSON : text (contenu brut du fichier, requis)
- **Réponse** : Résultat de callhistory.import_master_scp(text), code 200 si ok sinon 400
- **Note** : Traitement 100% local (parsing texte), aucun appel réseau

### POST `/callhistory/import_n1mm`

Importe un fichier Call History au format N1MM pour préremplir dept/locator/nom/section/zone d'UN concours précis.

- **Paramètres** : Corps JSON : text (requis), contest (optionnel, repli sur le concours actif de la config)
- **Réponse** : Résultat de callhistory.import_call_history_n1mm(contest, text), code 200 si ok sinon 400

### POST `/log/bulk_resolve/start`

Démarre en tâche de fond une re-résolution en masse (locator/état) des QSO via la cascade callbook existante (cty/QRZ/ClubLog).

- **Paramètres** : Corps JSON : ids (liste d'IDs QSO ciblés, optionnel — absent/vide = tout le log), overwrite (bool, écrase aussi les champs déjà renseignés)
- **Réponse** : {'ok':bool,'error':msg si échec}
- **Note** : Job asynchrone (voir logx_callbook.bulk_resolve_start), ne comble par défaut que les champs vides


## Règlements et calendrier des concours

<a id="rules"></a>

### GET `/data/contests`

Liste les identifiants de tous les concours connus du moteur de scoring.

- **Paramètres** : aucun
- **Réponse** : liste JSON des clés de CONTEST_SCORING

### GET `/data/external_contests`

Renvoie le calendrier de concours externe issu de WA7BNM Contest Calendar, avec cache par année.

- **Paramètres** : year (optionnel, année ciblée, défaut année courante)
- **Réponse** : {year, contests, total, updated, source}
- **Note** : Service tiers (contestcalendar.com) ; utilise/rafraîchit un cache mémoire EXTERNAL_CONTESTS_CACHE.

### GET `/data/refresh_external`

Force un rafraîchissement asynchrone (thread daemon) du calendrier WA7BNM.

- **Paramètres** : aucun
- **Réponse** : {ok:true, message}
- **Note** : Lance un thread de fond, ne bloque pas la réponse ; dépend d'un service tiers (contestcalendar.com).

### GET `/data/calendar`

Calendrier complet des concours définis localement (CONTEST_DEFINITIONS) avec dates calculées automatiquement (calc_all_dates), trié par date croissante.

- **Paramètres** : aucun paramètre significatif utilisé (startswith seulement)
- **Réponse** : {year, contests: [...détails par concours...], last_update, alerts}

### GET `/rules/export_custom`

Exporte les concours personnalisés validés (custom_contests.json) pour partage communautaire entre stations.

- **Paramètres** : aucun
- **Réponse** : {format: 'logx-custom-contests', version, exported_at, exported_by, contests}

### GET `/data/update_rules`

Déclenche une mise à jour asynchrone (thread daemon) des règlements de concours pour l'année courante.

- **Paramètres** : aucun
- **Réponse** : {ok:true, message}
- **Note** : Requiert le jeton de session (écriture de rules_db) ; lance run_annual_update en tâche de fond.

### GET `/contest/geo_mode`

Détermine le mode de chasse géographique d'un concours : département, département+DXCC, DXCC seul, ou autre.

- **Paramètres** : contest (optionnel, sinon celui de la config)
- **Réponse** : {contest, mode}
- **Note** : Sert à faire basculer l'onglet entre chasse aux départements et chasse aux pays côté client.

### GET `/data/rules_status`

État du système de règlements de concours : année, dernière mise à jour, alertes, nombre de concours définis.

- **Paramètres** : aucun
- **Réponse** : {'year','last_update','alerts','contests_count','current_year','next_update'}

### POST `/rules/analyze`

Télécharge ou reçoit le texte d'un règlement de concours et le fait analyser par l'IA configurée pour proposer une définition structurée.

- **Paramètres** : JSON {url?, text?, name?}
- **Réponse** : résultat de analyze_rules(...) — proposition de définition + niveau de confiance
- **Note** : Nécessite une clé API IA configurée ; ne sauvegarde rien (voir /rules/save_definition).

### POST `/rules/save_definition`

Enregistre une définition de concours personnalisée après relecture/correction humaine.

- **Paramètres** : JSON {id: string, definition: object, source_url?, confidence?}
- **Réponse** : {ok, message} ou {ok:false, validation_errors}
- **Note** : La définition est revalidée côté serveur avant écriture sur disque.

### POST `/rules/import_custom`

Importe un lot de définitions de concours personnalisées partagées par une autre station.

- **Paramètres** : JSON {contests: {id: {definition, ...}}} (ou dict direct id→entrée)
- **Réponse** : {ok, imported:[...], updated:[...], skipped_builtin:[...], errors:{...}}
- **Note** : Chaque définition est revalidée avant import ; ignore les concours déjà présents dans la base intégrée.

### POST `/rules/delete_custom`

Supprime une définition de concours personnalisée.

- **Paramètres** : JSON {id: string}
- **Réponse** : {ok, message}


## Vérification d'échange

<a id="exchange"></a>

### GET `/exchange/check`

Garde-fou 'multiplicateur fantôme' : vérifie que la zone CQ saisie correspond à ce que cty.dat attend pour cet indicatif.

- **Paramètres** : call, value (valeur saisie), kind (défaut 'cq_zone')
- **Réponse** : {kind, ok, match, ...} pour kind='cq_zone' ; sinon {ok:false, match:null, kind}
- **Note** : Déterministe (aucun LLM, aucun réseau) ; seul kind='cq_zone' est actuellement implémenté.


## Diplômes et récompenses (awards)

<a id="awards"></a>

### GET `/awards/summary`

Tableau de bord diplômes : DXCC/départements travaillés et confirmés sur toute la vie de la station.

- **Paramètres** : aucun
- **Réponse** : objet awards.award_summary(log_copy)

### GET `/awards/carres`

Carrés QRA (grid squares) travaillés pour une bande donnée, pour la carte VUCC.

- **Paramètres** : band
- **Réponse** : objet awards.carres_travailles(log_copy, bande)
- **Note** : Le VUCC se compte bande par bande, jamais toutes bandes confondues.

### GET `/awards/matrix`

Worked Matrix : grille bande × CW/Phone/Digital, sur toute la vie de la station par défaut, ou restreinte au concours actif avec ?scope=contest.

- **Paramètres** : scope (optionnel, 'contest' pour restreindre au concours configuré)
- **Réponse** : objet awards.worked_matrix(log_copy, scope_id)

### GET `/awards/activity`

Activité par jour (toute la vie du log) pour le petit graphique statistique du popup Diplômes.

- **Paramètres** : days (optionnel, défaut 30, borné entre 1 et 3650)
- **Réponse** : {days: [...]}
- **Note** : Borne haute imposée pour éviter une réponse de taille arbitraire.

### GET `/data/dx_records`

Record DX par bande, calculé par haversine depuis le vrai locator de chaque QSO archivé.

- **Paramètres** : aucun (utilise le locator de la config)
- **Réponse** : objet awards.dx_records(locator, log_copy)
- **Note** : Remplace un ancien champ manuel record_dx à valeur unique.


## Chasse géographique (départements, DXCC, cartes)

<a id="geochase"></a>

### GET `/data/departments_worked`

Tableau de chasse des départements REF : contactés vs total, calculé depuis le log dans la portée du concours actif.

- **Paramètres** : aucun
- **Réponse** : objet dep.departments_progress(log_copy, scope_id)

### GET `/departments/targets`

Départements manquants et stations connues, croisés avec les spots cluster actuels pour identifier des cibles immédiates.

- **Paramètres** : aucun
- **Réponse** : objet dep.department_targets(...)

### GET `/data/france_geojson`

Sert le GeoJSON des départements français depuis un cache disque (téléchargé une fois, réutilisable hors ligne ensuite).

- **Paramètres** : aucun
- **Réponse** : corps JSON brut du GeoJSON, ou {error} en 503 si indisponible
- **Note** : Réponse envoyée manuellement (Content-Length explicite) plutôt que via _json ; Cache-Control max-age=86400.

### GET `/data/world_geojson`

Sert le GeoJSON mondial des pays (sélecteur d'échelle Europe/continent/monde) depuis un cache disque.

- **Paramètres** : aucun
- **Réponse** : corps JSON brut du GeoJSON, ou {error} en 503 si indisponible
- **Note** : Même patron que /data/france_geojson (réponse manuelle, Cache-Control 86400).

### GET `/data/world_worked`

Statut travaillé/non par pays pour la choroplèthe monde, projeté depuis les entités DXCC contactées.

- **Paramètres** : aucun
- **Réponse** : objet wm.worked_by_country(log_copy, scope_id)
- **Note** : Même calcul de base que /data/countries_worked.

### GET `/data/countries_worked`

Progression de la chasse aux pays (DXCC), variante internationale de la chasse aux départements.

- **Paramètres** : aucun
- **Réponse** : objet co.countries_progress(log_copy, scope_id)

### GET `/countries/targets`

Cibles de chasse DXCC : pays manquants croisés avec les spots cluster actuels.

- **Paramètres** : aucun
- **Réponse** : objet co.country_targets(log_copy, scope_id, spots)


## Programmes d'activation (POTA/SOTA/IOTA/WWFF/WCA)

<a id="activation"></a>

### GET `/activation/state`

Avancement en direct d'une activation POTA/SOTA/IOTA/WWFF : nombre de QSO/minute, QSO Park-to-Park (P2P).

- **Paramètres** : aucun (utilise activation_program/my_activation_ref de la config)
- **Réponse** : {active:false, programs} si pas d'activation configurée, sinon état complet + programs

### GET `/data/pota_spots`

Spots d'activateurs POTA en direct (source api.pota.app, cache 90 s).

- **Paramètres** : aucun
- **Réponse** : {'spots':[...]}
- **Note** : service tiers api.pota.app

### GET `/data/sota_spots`

Spots d'activateurs SOTA en direct (source api2.sota.org.uk, cache 60 s).

- **Paramètres** : aucun
- **Réponse** : {'spots':[...]}
- **Note** : service tiers api2.sota.org.uk

### GET `/sota/status`

État de la connexion SOTA SSO pour l'auto-spot (clientId configuré, jeton présent, case d'approbation IA cochée).

- **Paramètres** : aucun
- **Réponse** : objet statut (logx_sota_spot.status)
- **Note** : nécessite une config OAuth SOTA SSO

### GET `/sota/oauth/start`

Lance la connexion SOTA SSO (Authorization Code + PKCE), redirige vers le serveur SSO SOTA officiel.

- **Paramètres** : aucun (lit la config serveur)
- **Réponse** : redirection HTTP 302 vers SOTA SSO, ou {'ok':false,'error'} si non configuré
- **Note** : nécessite client OAuth SOTA configuré

### GET `/sota/oauth/callback`

Callback de retour depuis SOTA SSO : échange le code d'autorisation contre un jeton, affiche une page HTML de confirmation.

- **Paramètres** : code (string), state (string), error_description/error (optionnels)
- **Réponse** : page HTML de confirmation (succès ou échec)
- **Note** : redirect_uri enregistré = ce serveur local ; échappement HTML du message

### GET `/data/wwff_spots`

Spots d'activateurs WWFF en direct (source spots.wwff.co, cache 60 s).

- **Paramètres** : aucun
- **Réponse** : {'spots':[...]}
- **Note** : service tiers spots.wwff.co

### GET `/data/iota_spots`

Références IOTA reconnues dans les commentaires des spots cluster déjà en cache (pas de source réseau dédiée, aucune fiable).

- **Paramètres** : aucun
- **Réponse** : {'spots':[...]}
- **Note** : pas de fetch réseau propre, dérivé du cache cluster

### GET `/data/wca_planned`

Activations WCA/COTA annoncées à l'avance (flux RSS wcagroup.org) — pas des spots confirmés sur l'air.

- **Paramètres** : aucun
- **Réponse** : {'items':[...]}
- **Note** : service tiers wcagroup.org (RSS)

### GET `/activation_db/search`

Recherche par code ou nom dans la base de références du programme d'activation choisi (POTA/SOTA/IOTA/WWFF/WCA), pour l'auto-complétion.

- **Paramètres** : program (string), q (string)
- **Réponse** : {'results':[...],'status':{...}}
- **Note** : base téléchargée en tâche de fond au premier appel, non bloquant

### GET `/activation_db/lookup`

Détails d'une référence exacte d'activation, pour valider le champ « ma référence activée » contre la vraie base.

- **Paramètres** : program (string), ref (string)
- **Réponse** : {'entry':{...}|null,'status':{...}}

### GET `/activation_db/nearby`

Références d'activation les plus proches d'un point donné (par défaut le locator de la station), équivalent du Range Calculator SOTA généralisé aux autres programmes avec coordonnées GPS (sauf WCA).

- **Paramètres** : program (string), lat/lon (float, optionnels, défaut locator config), max_km (float, défaut 100)
- **Réponse** : {'entries':[...],'status':{...}}

### POST `/pota/spot`

Publie un auto-spot d'activation POTA sur l'API publique api.pota.app.

- **Paramètres** : JSON {reference?, freq_khz ou freq_mhz, mode?, comment?}
- **Réponse** : résultat de logx_pota.post_spot(...)
- **Note** : Nécessite un indicatif configuré ; l'indicatif spotté provient toujours de la config station, jamais du corps.

### POST `/sota/spot`

Publie un auto-spot d'activation SOTA via SOTA SSO et api2.sota.org.uk.

- **Paramètres** : JSON {reference?, freq_khz ou freq_mhz, mode?, comment?}
- **Réponse** : résultat de logx_sota_spot.post_spot(...)
- **Note** : Nécessite un clientId SOTA SSO configuré et l'approbation IA activée ; reste inactif tant que ce n'est pas le cas.


## DXpeditions

<a id="dxpeditions"></a>

### GET `/data/dxpeditions`

Liste des DXpeditions annoncées (source NG3K ADXO), chaque entrée annotée 'worked' selon les pays déjà travaillés.

- **Paramètres** : aucun
- **Réponse** : {expeditions: [...]}
- **Note** : Service tiers NG3K ADXO.

### GET `/data/dxpeditions_active`

Variante du panneau CHASSE des DXpeditions NG3K : annotées 'status' (active/upcoming) avec fréquence live si repérée sur le cluster, expéditions terminées retirées.

- **Paramètres** : aucun
- **Réponse** : {expeditions: [...]}
- **Note** : Service tiers NG3K ADXO + cluster agrégé (_spots_from_caches).


## École CW

<a id="cwschool"></a>

### GET `/cw/serie`

Génère une série d'entraînement CW tirée de l'index du poste, avec l'échange réellement demandé par le concours choisi (École de CW).

- **Paramètres** : n (nombre d'items, 1 à 60, défaut 20)
- **Réponse** : {serie, contest, exchange, indicatifs_disponibles}
- **Note** : Aucun réseau ni IA ; le morse est généré côté navigateur, rien n'est émis sur l'air.

### POST `/cw/corriger`

Corrige une série de copie CW saisie par l'élève et calcule le barème plus la vitesse suivante recommandée.

- **Paramètres** : JSON {serie: [...] (max 200 éléments), reponses: [...], wpm?: int}
- **Réponse** : bilan (score/taux) avec vitesse_suivante ajoutée


## Propagation, astronomie et écoute à distance

<a id="propagation"></a>

### GET `/data/bande_segments`

Découpage CW/numérique/phonie d'une bande donnée, pour dessiner la réglette des fenêtres de surveillance.

- **Paramètres** : band (bande concernée)
- **Réponse** : {segments: [...]} (ou vide si non trouvé)
- **Note** : Lecture seule, aucun accès au log.

### GET `/data/sat`

Prédiction satellite complète en un seul appel : prochain passage, liste des suivants, position instantanée, Doppler, âge du jeu TLE et état du suivi rotor.

- **Paramètres** : sat (nom du satellite, défaut ISS ou config) ; hours (1-168, défaut 24) ; min_el (0-89, défaut 0) ; freq (MHz, défaut 145.8)
- **Réponse** : {available, sat, tle_age, satellites, tracking?, rotor_enabled?, passages, position?, doppler_hz?, freq_mhz?, error?}
- **Note** : Aucun accès réseau dans le handler : les TLE sont téléchargés en tâche de fond, le handler ne lit que le cache disque ; nécessite un locator valide en config, et un rotor (matériel) pour le suivi.

### GET `/data/eme_moon`

Position de la Lune depuis le QTH configuré (azimut/élévation) plus heures de lever/coucher, calculé localement via PyEphem.

- **Paramètres** : aucun (utilise le locator de la config)
- **Réponse** : fusion de eme.moon_position(...) et eme.moon_rise_set(...)
- **Note** : Aucune donnée réseau ; nécessite un locator valide en config.

### GET `/data/eme_doppler`

Décalage Doppler estimé pour l'EME à la fréquence courante, plus la perte de trajet radar en dB.

- **Paramètres** : freq (MHz, défaut 144.1)
- **Réponse** : objet eme.doppler_shift_hz(...) enrichi de path_loss_db/distance_km si disponible
- **Note** : Nécessite un locator valide en config ; calcul 100% local.

### GET `/data/eme_window`

Calcule la fenêtre commune où la Lune est visible simultanément depuis mon QTH et celui d'un correspondant identifié par son locator.

- **Paramètres** : locator (locator du correspondant, ex FN31pr) ; hours (1-168, défaut 48)
- **Réponse** : objet eme.common_window(lat1, lon1, lat2, lon2, hours)
- **Note** : hours est borné dur (1-168) pour éviter de bloquer un thread HTTP en boucle CPU sur une valeur excessive ou NaN/inf.

### GET `/beacons/now`

Indique quelle balise NCDXF/IBP émet actuellement sur chaque bande, avec distance et azimut depuis le locator configuré.

- **Paramètres** : aucun
- **Réponse** : {beacons: [...]} chaque entrée enrichie de dist_km/bearing/cardinal si locator disponible
- **Note** : Calcul pur, aucun appel réseau (positions des balises connues localement).

### GET `/data/heard_where`

Où mon signal a été décodé, via PSK Reporter (carte d'ouverture de propagation).

- **Paramètres** : aucun (utilise callsign_contest/callsign et locator de la config)
- **Réponse** : objet psk.heard_where(call, locator)
- **Note** : Service tiers PSK Reporter.

### GET `/data/weather`

Météo du point haut (via open-meteo, sans clé API) — utile pour la sécurité matériel en /P.

- **Paramètres** : aucun (utilise le locator de la config)
- **Réponse** : objet weather.get_weather_cached(lat, lon)
- **Note** : Lecture cache seule dans le handler ; le rafraîchissement réseau se fait en tâche de fond.

### GET `/data/tropo`

Prévision de propagation troposphérique (ducting) basée sur le gradient de réfractivité (open-meteo, niveaux de pression).

- **Paramètres** : aucun (utilise le locator de la config)
- **Réponse** : objet tropo.tropo_forecast(lat, lon)
- **Note** : Service tiers open-meteo.

### GET `/data/meteors`

Calendrier des essaims météores utiles au Meteor Scatter VHF — déterministe, sans appel réseau.

- **Paramètres** : aucun
- **Réponse** : objet qualité MS (logx_meteors.ms_quality)

### GET `/data/es_opening`

Indice d'ouverture VHF (Sporadic-E et au-delà), statistique basée sur le flux de spots déjà collecté — pas une prévision physique.

- **Paramètres** : aucun (locator lu en config)
- **Réponse** : {'50':{...},'144':{...}}

### GET `/data/openings`

Ouvertures de propagation par région depuis le QTH (probabilité par bande), avec détail si une région est précisée.

- **Paramètres** : region (string, optionnel, ex. 'EU' ; sinon survol de toutes les régions)
- **Réponse** : {'ok':true,'detail':{...}} ou {'ok':true,'regions':[...]}, ou {'ok':false,'error'} si locator non défini

### GET `/data/timeofday`

Widget jour/nuit comparant HOME et un DX optionnel (locator du correspondant en cours de saisie).

- **Paramètres** : dx (string, locator, optionnel)
- **Réponse** : objet état jour/nuit (logx_paths.time_of_day_state)

### GET `/data/propmap`

Carte de propagation mondiale (grille colorée) pour la surcouche carte IA, par bande et décalage horaire.

- **Paramètres** : band (string, défaut 'best'), hour (int 0-24, défaut 0)
- **Réponse** : {'ok':true,'band','hour','when_utc','step':15,'my':{lat,lon},'cells':[...]}, ou {'ok':false,'error'} si locator non défini

### GET `/data/rbn`

Où le signal CW de la station est entendu, via les skimmers du Reverse Beacon Network.

- **Paramètres** : aucun (callsign lu en config)
- **Réponse** : objet (logx_rbn.where_heard)
- **Note** : service tiers RBN

### GET `/data/propagation`

Indices solaires (N0NBH) et MUF réelle (KC2G), plus un verdict par bande calculé depuis le QTH (bornes haute et basse).

- **Paramètres** : aucun (locator lu en config)
- **Réponse** : {'solar':{...},'muf':{...},'etat_bandes':{...}|null}
- **Note** : lecture cache seule (caches 15 min), rafraîchissement réseau en tâche de fond

### GET `/data/focus`

Endpoint agrégé de la page FOCUS BANDE : spots classés, ouvertures régionales, bandes à proposer, calendrier concours, carrés manquants, suggestions IA, classement des bandes — en un seul appel.

- **Paramètres** : band (string), mode (string)
- **Réponse** : objet volumineux {'ok':true,'band','mode','bandes','suggestions','classement','spots','regions','concours','carres_manquants','contest_actif'}
- **Note** : conçu pour un 2e écran pollé toutes les 15 s ; agrège plusieurs sous-systèmes


## WebSDR

<a id="websdr"></a>

### GET `/data/websdr/ecouter`

Choisit côté serveur UN récepteur WebSDR à écouter (proximité du DX si lat/lon/locator fournis, sinon meilleur SNR près du QTH) et renvoie l'URL réglée sur la fréquence/mode.

- **Paramètres** : khz (float), lat/lon (float, optionnels), loc (grille, optionnel, repli si pas de lat/lon), mode (string)
- **Réponse** : {'ok':true,'nom','snr','dist_km','url','pres_du_dx':bool} ou {'ok':false}
- **Note** : route testée AVANT /data/websdr (préfixe commun)

### GET `/data/websdr`

Annuaire complet des récepteurs WebSDR distants (~880 stations, ~350 Ko), avec une suggestion du meilleur récepteur près du QTH.

- **Paramètres** : aucun
- **Réponse** : {'stations':[...],'suggestion':{...}|null,...}
- **Note** : pas d'appel réseau ici, cache alimenté en tâche de fond


## Cluster DX, spots et band map

<a id="cluster"></a>

### GET `/data/spots_ranked`

Liste complète des spots cluster classés par valeur (multiplicateurs, points, alertes), annotés LoTW et besoin DXCC, filtrés selon les réglages du filtre de spots.

- **Paramètres** : aucun (lit config + spot_filter + alert_rules)
- **Réponse** : {'spots':[...40 max...],'meta':{...},'alert_matches':[...],'filtre':{...}}
- **Note** : annotation LoTW via liste tierce ; filtre appliqué après évaluation des alertes

### GET `/bandmap/local`

Band map Search & Pounce : stations entendues manuellement par l'opérateur, partagées entre postes.

- **Paramètres** : aucun
- **Réponse** : {'ok':true,'spots':[...]}
- **Note** : état côté serveur, partagé entre postes SO2R

### GET `/data/clusters`

Annuaire de nœuds DX cluster publics, pour le sélecteur CONFIG.

- **Paramètres** : aucun
- **Réponse** : {'nodes':[...]}

### POST `/data/spots`

Réception de spots cluster poussés depuis le navigateur (contournement du blocage HTTPS côté serveur pour certaines sources).

- **Paramètres** : corps JSON : tableau de spots
- **Réponse** : {'ok':true,'count':int} ou {'ok':false,'error'}
- **Note** : cache limité aux 200 premiers spots ; nécessite jeton d'authentification (comme tout POST hors /auth/login)

**Exemple** :

```bash
curl -X POST "http://127.0.0.1:8080/data/spots" \
  -H "Content-Type: application/json" \
  -H "X-RC-Token: $(cat .auth_token)" \
  -d '[{"spotter":"F4GLD","dx":"9A1CIG","freq":14025.0,"info":"CQ CQ","time":"1234Z"}]'
```

### POST `/spots/filter`

Définit les réglages de filtrage d'affichage des spots, partagés entre tous les postes connectés.

- **Paramètres** : JSON = réglages de filtre (voir logx_spotfilter.reglages_valides)
- **Réponse** : {ok:true, spot_filter, actif}

### POST `/bandmap/add`

Ajoute une entrée manuelle sur la carte de bande.

- **Paramètres** : JSON {call, freq_khz, band?, mode?, note?}
- **Réponse** : résultat de logx_bandmap.ajouter(...)

### POST `/bandmap/delete`

Supprime une entrée de la carte de bande.

- **Paramètres** : JSON {call, freq_khz}
- **Réponse** : résultat de logx_bandmap.supprimer(...)

### POST `/bandmap/clear`

Vide entièrement la carte de bande.

- **Paramètres** : aucun
- **Réponse** : résultat de logx_bandmap.vider()

### POST `/cluster/spot`

Publie son propre spot (self-spot) avec sa fréquence sur le cluster DX configuré.

- **Paramètres** : JSON {freq_khz ou freq_mhz, comment?}
- **Réponse** : résultat de logx_clusters.publish_self_spot(...)
- **Note** : Nécessite le self-spot activé et un indicatif configuré dans CONFIG ; l'indicatif spotté est toujours celui de l'opérateur, jamais celui fourni dans le corps.


## Radio (CAT), SO2R et panadapter

<a id="radio"></a>

### GET `/rig/state`

État courant de la radio pilotée par CAT (natif/TCI/rigctld/flrig), pollé par le logbook ; en SO2R suit la radio ayant le focus.

- **Paramètres** : aucun
- **Réponse** : objet état radio (fréquence, mode, PTT...)
- **Note** : nécessite une radio CAT configurée et connectée

### GET `/so2r/state`

État SO2R : quelle radio a le focus/émet, paramètres SO2R activés, TX actif.

- **Paramètres** : aucun
- **Réponse** : objet état SO2R
- **Note** : état côté serveur, identique sur toutes les pages ouvertes

### GET `/rig/ports`

Liste des ports série disponibles sur ce poste, pour le sélecteur CONFIG de la radio CAT native.

- **Paramètres** : aucun
- **Réponse** : {'ports':[...]}

### GET `/rig/scope_available`

Indique si le scope CI-V 0x27 (panadapter natif Icom) est disponible pour le modèle de radio configuré en CAT natif.

- **Paramètres** : aucun
- **Réponse** : objet disponibilité (booléen + détails modèle)
- **Note** : nécessite CAT natif + modèle Icom publiant le flux scope

### GET `/rig/scope_line`

Une ligne de spectre scope CI-V déjà réassemblée (475 pixels, amplitude 0-160), pollée par le panadapter quand la source CI-V est active.

- **Paramètres** : aucun
- **Réponse** : objet ligne spectre, ok=false si radio muette/paquets incomplets (reste HTTP 200)
- **Note** : nécessite CAT natif Icom avec scope

### GET `/rig/tci_spectrum_available`

Indique si la source spectre TCI (3e source panadapter) est disponible selon le pilotage TCI actif.

- **Paramètres** : aucun
- **Réponse** : objet disponibilité
- **Note** : nécessite pilotage TCI actif

### GET `/rig/tci_spectrum_line`

Une ligne de spectre TCI déjà calculée côté serveur (FFT pure Python sur flux IQ brut, échelle 0-255), pollée par le panadapter en source TCI.

- **Paramètres** : aucun
- **Réponse** : objet ligne spectre, ok=false si buffer pas prêt (reste HTTP 200)
- **Note** : nécessite pilotage TCI actif ; FFT calculée en Python pur côté serveur

### GET `/rig/pending_detections`

Détections de branchement radio en attente (watcher de fond, indice passif VID:PID/numéro de série), jamais appliquées sans confirmation utilisateur.

- **Paramètres** : aucun
- **Réponse** : {'detections':[...]}
- **Note** : pollé par CONFIG toutes les ~2s

### GET `/station`

État complet de la station physique (antennes, rotors, amplis) et ce qui sert sur une bande donnée si précisée.

- **Paramètres** : bande (string, optionnel)
- **Réponse** : objet station + 'resume' + 'pour_bande' si bande fournie
- **Note** : source unique lue par CONFIG, logbook, band map

### GET `/hardware/state`

État matériel groupé (radio+ampli+WSJT-X+rotor+PGXL+ACOM) en une seule requête au lieu de 5-6 séparées ; en SO2R la clé 'rig' suit le focus.

- **Paramètres** : aucun
- **Réponse** : {'rig':{...},'amp':{...},'wsjtx':{...},'rotor':{...},'pgxl':{...},'acom':{...}}
- **Note** : regroupe /rig/state, /amp/state, /wsjtx/state, /rotor/state et l'état PowerGenius XL/ACOM

### POST `/rig/connect_test`

Teste une connexion radio éphémère sans rien sauvegarder (natif série, TCI, rigctld, flrig, OmniRig, FlexRadio, Icom réseau).

- **Paramètres** : JSON {mode, host?, port?, brand?, model?, baudrate?, civ_addr?, rig_num?}
- **Réponse** : résultat de test_connection(...) selon le backend choisi
- **Note** : Nécessite le matériel/logiciel tiers correspondant au mode choisi (ex. OmniRig, SmartSDR pour FlexRadio).

### POST `/rig/autodetect`

Auto-détecte marque/modèle radio CAT native en balayant les vitesses série courantes sur le port.

- **Paramètres** : JSON {port: string}
- **Réponse** : résultat de logx_cat.autodetect_scan(...)
- **Note** : Nécessite une radio effectivement branchée sur le port indiqué.

### POST `/rig/dismiss_detection`

Écarte une détection de branchement CAT en attente (bandeau CONFIG).

- **Paramètres** : JSON {device: string}
- **Réponse** : {ok:true}

### POST `/rig/scope_configure`

Configure le scope CI-V 0x27 d'une radio Icom (mode et span) sur la connexion série déjà ouverte pour le CAT.

- **Paramètres** : JSON {mode?: string, span_hz?: int}
- **Réponse** : résultat de logx_cat.scope_configure(...)
- **Note** : span_hz doit être l'une des 8 valeurs valides (2.5 à 500 kHz) ; nécessite une radio Icom CI-V en mode natif.

### POST `/rig/tci_spectrum_configure`

Démarre ou arrête le flux spectre IQ TCI (IQ_SAMPLERATE + DDS + IQ_START/STOP).

- **Paramètres** : JSON {enabled: bool, sample_rate_hz?: int}
- **Réponse** : résultat de logx_tci.tci_spectrum_configure(...)
- **Note** : sample_rate_hz doit être l'une des 4 valeurs valides si enabled=true ; nécessite une connexion TCI active.

### POST `/rig/qsy`

Change la fréquence (et éventuellement le mode) de la radio ayant le focus SO2R actif, via le backend CAT configuré.

- **Paramètres** : JSON {freq_hz ou freq_khz, mode?}
- **Réponse** : résultat selon backend (ok/erreur)
- **Note** : Applique la conversion transverter FI↔RF si configuré ; non supporté en mode FlexRadio (hors périmètre du module).

### POST `/rig/cw`

Envoie un texte en CW (manipulation) via WinKeyer si activé, sinon via le backend CAT natif/TCI, sur la radio ayant le focus SO2R.

- **Paramètres** : JSON {text: string}
- **Réponse** : résultat selon backend (ok/erreur)
- **Note** : Prend un verrou d'exclusivité TX SO2R avant émission ; non disponible en mode flrig/OmniRig/FlexRadio/Icom réseau (utiliser WinKeyer ou rigctld/TCI).

### POST `/rig/stop`

Arrête l'émission CW en cours sur la radio ayant le focus SO2R, quel que soit le backend.

- **Paramètres** : aucun
- **Réponse** : résultat selon backend (ok/erreur)
- **Note** : Relâche toujours le verrou TX de la radio qui le détient réellement, même si le focus a changé entretemps.

### POST `/rig/ptt`

Active/désactive le PTT explicitement, sans passer par le keyer vocal (utilisé notamment par le décodeur FT8 natif).

- **Paramètres** : JSON {on: bool}
- **Réponse** : résultat de logx_voicekeyer.set_ptt(...)
- **Note** : Prend/relâche le verrou d'exclusivité TX SO2R.

### POST `/so2r/focus`

Bascule le focus d'émission entre les deux radios en configuration SO2R.

- **Paramètres** : JSON {radio: identifiant de la radio cible}
- **Réponse** : résultat de logx_so2r.basculer(...)

### POST `/so2r/test`

Teste la connexion au contrôleur SO2R.

- **Paramètres** : JSON {port?: string} — le port saisi prime sur celui déjà enregistré
- **Réponse** : résultat de logx_so2r.tester(...)
- **Note** : Nécessite un contrôleur SO2R matériel.


## Amplificateur

<a id="amp"></a>

### GET `/amp/state`

État courant de l'amplificateur HF (Elecraft KPA500/1500, Icom PW-1/PW2, SPE Expert) : puissance/SWR/défaut/operate.

- **Paramètres** : aucun
- **Réponse** : objet état ampli
- **Note** : nécessite un amplificateur configuré et connecté (série ou réseau)

### POST `/amp/operate`

Bascule l'amplificateur HF entre standby et operate.

- **Paramètres** : JSON {on: bool}
- **Réponse** : résultat de logx_amp.set_operate(...)
- **Note** : Nécessite un amplificateur connecté (série ou réseau).

### POST `/amp/band`

Change la bande sélectionnée sur l'amplificateur HF.

- **Paramètres** : JSON {band: string}
- **Réponse** : résultat de logx_amp.set_band(...)

### POST `/amp/clear_fault`

Acquitte un défaut sur l'amplificateur HF.

- **Paramètres** : aucun
- **Réponse** : résultat de logx_amp.clear_fault(...)

### POST `/amp/power`

Met sous/hors tension l'amplificateur HF à distance.

- **Paramètres** : JSON {on: bool}
- **Réponse** : résultat de logx_amp.power_toggle(...)

### POST `/amp/test`

Teste la connexion à l'amplificateur HF (bouton CONFIG).

- **Paramètres** : JSON {brand, port, baudrate?, civ_addr?, conn_mode?, host?, net_port?}
- **Réponse** : résultat de logx_amp.test_connection(...)

### POST `/pgxl/test`

Teste la connexion réseau à un amplificateur PowerGenius XL (4O3A).

- **Paramètres** : JSON {host, port?, timeout?}
- **Réponse** : résultat de logx_powergenius.test_connection(...)
- **Note** : Pas de route operate/standby pour ce modèle : commande non confirmée par la doc officielle, refusée volontairement (pilotage au panneau avant ou via SmartSDR).

### POST `/acom/test`

Teste la connexion série à un amplificateur ACOM (500S/600S/700S/1200S/2020S).

- **Paramètres** : JSON {port, model?, timeout?}
- **Réponse** : résultat de logx_acom.test_connection(...) — inclut la télémétrie décodée si succès (statut, puissances, ROS, température, bande, ventilateur).
- **Note** : doc communautaire, pas officielle ACOM — voir la docstring de logx_acom.py pour les sources exactes.

### POST `/acom/operate`

Bascule OPERATE/STANDBY/OFF sur l'ACOM — DIFFÉREMMENT de `/pgxl/test` ci-dessus, cette commande est confirmée par le code source réel (gestionnaires de bouton nommés explicitement).

- **Paramètres** : JSON {mode} — `mode` ∈ {"operate", "standby", "off"}
- **Réponse** : résultat de logx_acom.set_operate(...)


## Rotor d'antenne

<a id="rotor"></a>

### GET `/rotor/state`

Position courante du rotor d'antenne (rotctld), pollée par le logbook.

- **Paramètres** : aucun
- **Réponse** : objet état rotor
- **Note** : nécessite un rotor configuré et connecté

### GET `/rotor/models`

Catalogue statique des marques/modèles de rotor (protocole + élévation), pour les listes déroulantes de CONFIG.

- **Paramètres** : aucun
- **Réponse** : {'brands':[...]}
- **Note** : statique, aucune I/O

### POST `/rotor/sat_track`

Démarre le suivi automatique du rotor pour un passage satellite.

- **Paramètres** : JSON {sat: string (nom du satellite)}
- **Réponse** : {ok:true} ou {ok:false, error}
- **Note** : Refuse (synchrone) si rotor éteint, satellite inconnu, ou passage trop lointain.

### POST `/rotor/sat_track_stop`

Arrête le suivi automatique du rotor satellite en cours.

- **Paramètres** : aucun
- **Réponse** : {ok:true}

### POST `/rotor/point`

Pointe un rotor d'antenne vers un azimut/élévation donné.

- **Paramètres** : JSON {azimuth: number, elevation?: number, bande?: string, rotor_id?: string}
- **Réponse** : résultat de logx_rotor.set_position(...)
- **Note** : Sélection du rotor par bande d'antenne active ou par rotor_id ; applique le décalage mécanique du pylône si configuré. Nécessite rotctld/matériel rotor.

### POST `/rotor/stop`

Arrête le mouvement du rotor.

- **Paramètres** : JSON {bande?: string, rotor_id?: string}
- **Réponse** : résultat de logx_rotor.stop(...)


## Station Control (relais)

<a id="relay"></a>

### POST `/relay/set`

Bascule manuellement un relais du panneau Station Control (WebSwitch/KMTronic/Denkovi/série générique).

- **Paramètres** : JSON {relay: int, on: bool}
- **Réponse** : résultat de logx_relay.set_relay(...)
- **Note** : Nécessite un panneau de relais configuré.

### POST `/relay/test`

Teste la connexion au panneau de relais Station Control.

- **Paramètres** : aucun (utilise la config enregistrée)
- **Réponse** : résultat de logx_relay.test_connection(...)


## Manipulateur CW (WinKeyer) et keyer vocal (DVK)

<a id="cwkeyer"></a>

### GET `/voicekeyer/devices`

Liste les périphériques audio de sortie et les voix TTS installées, pour les menus déroulants de CONFIG.

- **Paramètres** : aucun
- **Réponse** : {'devices':[...],'voices':[...]}
- **Note** : appelé une fois, pas en polling

### GET `/voice/slots`

Emplacements DVK (messages vocaux pré-enregistrés) réellement disponibles et leur durée.

- **Paramètres** : aucun
- **Réponse** : {'ok':true,'slots':[...]}
- **Note** : état côté serveur, identique sur tous les postes

### POST `/winkeyer/test`

Teste la présence d'un WinKeyer en ouvrant une session et en lisant la version du micrologiciel.

- **Paramètres** : JSON {port?: string, wpm?: int}
- **Réponse** : résultat de logx_winkeyer.tester(...)
- **Note** : Nécessite un manipulateur WinKeyer USB branché ; port saisi prime sur celui déjà enregistré.

### POST `/voice/save`

Enregistre un message vocal pré-enregistré (WAV) dans un emplacement mémoire.

- **Paramètres** : JSON {slot: string, wav_base64: string}
- **Réponse** : résultat de logx_voicekeyer.enregistrer_message(...)
- **Note** : Accepte aussi une data URL complète (data:audio/wav;base64,...).

### POST `/voice/play`

Joue un message vocal pré-enregistré via le PTT de la radio active.

- **Paramètres** : JSON {slot: string}
- **Réponse** : résultat de logx_voicekeyer.envoyer_message(...)
- **Note** : Prend un verrou d'exclusivité TX SO2R pendant toute la durée de la lecture (bloquant).

### POST `/voice/delete`

Supprime un message vocal pré-enregistré.

- **Paramètres** : JSON {slot: string}
- **Réponse** : résultat de logx_voicekeyer.supprimer_message(...)

### POST `/rig/voice`

Synthétise (TTS) et émet un message vocal dynamique (indicatif/report épelés phonétiquement) via le PTT de la radio.

- **Paramètres** : JSON {template ou text, call?, mycall?, rst_sent?, rst_rcvd?, nr?, skip_ptt?}
- **Réponse** : résultat de logx_voicekeyer.send_voice_message(...)
- **Note** : Synthèse multi-voix selon la langue détectée ; skip_ptt réservé au bouton Test de CONFIG (sinon prend le verrou TX SO2R).


## FT8 / WSJT-X et Wait-and-Pounce

<a id="ft8"></a>

### GET `/wsjtx/strategy/state`

État d'une stratégie pile-up FT8 calculée par l'IA.

- **Paramètres** : id (string)
- **Réponse** : objet état (status, stratégie...)
- **Note** : nécessite qu'une analyse ait été lancée via POST /wsjtx/strategy ; utilise une clé API IA

### GET `/pounce/state`

État de la session d'appel automatique (Wait-and-Pounce) : minuterie restante, appel en cours, journal des envois — désarme automatiquement une session expirée.

- **Paramètres** : aucun
- **Réponse** : objet état session (logx_pounce.session.etat)
- **Note** : consultable depuis n'importe quel poste

### GET `/wsjtx/state`

État de la liaison UDP avec WSJT-X (FT8/FT4), pollé par le logbook.

- **Paramètres** : aucun
- **Réponse** : objet état WSJT-X
- **Note** : nécessite WSJT-X lancé et configuré en UDP vers ce poste

### GET `/adifnet/state`

État de l'écoute réseau ADIF générique (N1MM/DXLog) ; démarre l'écouteur à chaud si activé en config.

- **Paramètres** : aucun
- **Réponse** : objet état (statut + réglages fusionnés)
- **Note** : démarre un listener UDP/TCP idempotent si listen=true en config

### POST `/pounce/armer`

Arme l'appel automatique FT8 (niveaux 3 et 4 de Wait-and-Pounce).

- **Paramètres** : JSON : critères d'armement (voir logx_pounce.Session.armer), notamment duree_min
- **Réponse** : résultat de pounce.session.armer(...)
- **Note** : Autorise la station à émettre sans intervention manuelle ; toujours borné dans le temps.

### POST `/pounce/desarmer`

Désarme l'appel automatique et coupe immédiatement toute émission WSJT-X en cours.

- **Paramètres** : aucun
- **Réponse** : résultat de pounce.session.desarmer(...)
- **Note** : Fonctionne sans condition (coupe-circuit).

### POST `/wsjtx/repondre`

Prépare WSJT-X à répondre à un indicatif décodé (indicatif rempli, décalage audio calé) sans émettre.

- **Paramètres** : JSON {call: string}
- **Réponse** : résultat de logx_wsjtx.repondre_a(...)
- **Note** : N'émet rien : c'est l'opérateur qui déclenche ensuite Enable TX dans WSJT-X.

### POST `/wsjtx/couper`

Coupe-circuit : arrête l'émission WSJT-X en cours.

- **Paramètres** : JSON {auto_seulement?: bool}
- **Réponse** : résultat de logx_wsjtx.couper_emission(...)


## Multi-opérateur : chat, écran mural, planning, synchro LAN

<a id="multiop"></a>

### GET `/chat/list`

Récupère les messages du chat multi-opérateur postés depuis un id donné, plus l'état de frappe en cours.

- **Paramètres** : since (id du dernier message déjà reçu par le client)
- **Réponse** : {messages: [...], last_id, typing}

### GET `/data/wall`

État de l'écran mural d'expédition : agrégation du log commun en temps réel, filtré sur le concours actif si applicable.

- **Paramètres** : aucun
- **Réponse** : objet état mural (logx_wall.wall_state)

### GET `/log/lan/export`

Export du log complet pour qu'un poste pair du LAN le tire et le fusionne (synchro LAN directe) ; désactivé si la synchro LAN n'est pas activée.

- **Paramètres** : token (string, requis seulement si lan_sync_token configuré)
- **Réponse** : {'enabled':false,'qsos':[]} si désactivé ; {'enabled':true,'iid','callsign','qsos':[...]} sinon ; 403 si jeton invalide
- **Note** : non protégé par défaut (comme /log/status), jeton d'équipe optionnel via HMAC

### GET `/log/lan/peers`

État de la synchro LAN : liste des pairs découverts sur le réseau local.

- **Paramètres** : aucun
- **Réponse** : {'peers':[...]}

### GET `/shifts/list`

Planning de roulement des opérateurs pour l'écran mural, trié par heure de début.

- **Paramètres** : aucun
- **Réponse** : {'shifts':[...]}

### POST `/shifts/add`

Ajoute un créneau de roulement pour un opérateur au planning de l'écran mural.

- **Paramètres** : Corps JSON : call, start, end (requis), name, date, note, mode ('ssb'/'cw'/'digi') optionnels
- **Réponse** : {'ok':true,'shift':{...}} avec éventuellement 'warning' si l'opérateur n'est pas déclaré qualifié pour le mode choisi ; {'ok':false,'error':...} 400 si champs requis manquants ou opérateur inconnu de la config
- **Note** : Refus uniquement si l'indicatif n'existe pas dans config.operators — outil purement informatif, une qualification de mode manquante n'empêche jamais la création (juste un avertissement)

### POST `/shifts/delete/<id>`

Supprime un créneau de planning par son id (numéro dans l'URL).

- **Paramètres** : id entier dans le chemin d'URL (/shifts/delete/42) ; aucun corps JSON
- **Réponse** : {'ok':true,'deleted':N}
- **Note** : POST plutôt que DELETE HTTP, choix assumé pour ce module (contrairement à /log/delete qui, lui, répond aussi à DELETE)

### POST `/chat/send`

Envoie un message dans le chat interne partagé entre postes (multi-opérateur en réseau local).

- **Paramètres** : Corps JSON : op, call, text (texte tronqué à 500 caractères)
- **Réponse** : {'ok':true,'id':N}
- **Note** : Historique en mémoire limité à 200 messages (FIFO), pas de persistance disque

### POST `/chat/typing`

Diffuse l'état éphémère « en train de taper » d'un opérateur (vue PARTNER), écrasé à chaque frappe.

- **Paramètres** : Corps JSON : op (requis, tronqué à 10 car.), label, band, mode, text (tronqué à 20 car.)
- **Réponse** : {'ok':true}
- **Note** : État purement en mémoire (typing_state), jamais persisté sur disque ; payload volontairement minuscule, appelé au throttle ~3/s côté client


## Synchronisation, sauvegarde et score en direct

<a id="sync"></a>

### GET `/scoreboard/status`

État du module scoreboard (config + dernière synchronisation).

- **Paramètres** : aucun
- **Réponse** : objet statut (logx_scoreboard.status)

### GET `/backup/status`

État du module de sauvegarde automatique.

- **Paramètres** : aucun
- **Réponse** : objet statut (logx_backup.status)

### GET `/cloudsync/status`

État de la synchronisation cloud (dossier partagé/NAS).

- **Paramètres** : aucun
- **Réponse** : objet statut (logx_cloudsync.status)

### POST `/scoreboard/push`

Publie le score courant sur un scoreboard en ligne (contestonlinescore).

- **Paramètres** : aucun
- **Réponse** : résultat de logx_scoreboard.push(...)
- **Note** : Nécessite un service scoreboard tiers configuré.

### POST `/backup/now`

Déclenche une sauvegarde manuelle immédiate du journal vers le dossier configuré (cloud/NAS).

- **Paramètres** : aucun
- **Réponse** : résultat de logx_backup.run_backup(...)

### POST `/backup/pick_folder`

Ouvre un sélecteur de dossier natif Windows pour choisir le dossier de sauvegarde.

- **Paramètres** : JSON {initial_dir?: string}
- **Réponse** : résultat de logx_winshell.pick_folder(...)
- **Note** : Bloque le thread de la requête jusqu'à la réponse de l'utilisateur ; nécessite Windows (message de repli sinon).

### POST `/cloudsync/now`

Déclenche une synchronisation cloud manuelle immédiate du journal.

- **Paramètres** : JSON {cloudsync_mode?, cloudsync_folder?} — surchargent la config déjà enregistrée
- **Réponse** : résultat de logx_cloudsync.sync_now(...)

### POST `/mysql/now`

Déclenche une synchronisation MySQL manuelle immédiate du journal.

- **Paramètres** : JSON {mysql_mode?, mysql_host?, mysql_port?, mysql_user?, mysql_password?, mysql_database?} — surchargent la config déjà enregistrée
- **Réponse** : résultat de logx_mysql_sync.sync_now(...)
- **Note** : Nécessite un serveur MySQL accessible.

### POST `/mysql/test`

Teste une connexion MySQL éphémère (bouton CONFIG) et crée le schéma s'il est absent.

- **Paramètres** : JSON {host, port, user, password, database}
- **Réponse** : résultat de logx_mysql_sync.test_connection(...)
- **Note** : Nécessite un serveur MySQL accessible.


## QSL

<a id="qsl"></a>

### GET `/qsl/status`

État de configuration QSL (ex: eQSL/LoTW/Club Log) et horodatage des dernières synchronisations.

- **Paramètres** : aucun
- **Réponse** : objet qsl.qsl_status(cfg_snapshot)

### POST `/qsl/upload`

Upload du log (portée concours courante ou explicite) vers un service QSL en ligne (eQSL/ClubLog/QRZCQ/HRDLog).

- **Paramètres** : corps JSON : service (string), contest (string, optionnel)
- **Réponse** : {'ok':bool,...,'qso_count':int} ou {'ok':false,'error':'Aucun QSO à envoyer'} (400)
- **Note** : identifiants du service lus/gérés côté serveur, jamais transmis au client ; nécessite un compte/API du service QSL choisi

### POST `/qsl_scan/upload`

Upload d'un scan de carte QSL papier (multipart : champs qso_id + file) attaché à un QSO existant, stocké sur disque.

- **Paramètres** : corps multipart/form-data : qso_id (int), file (fichier)
- **Réponse** : {'ok': True, 'qsl_scan': '<chemin relatif>'} ; ou {'ok': False, 'error': ...} (400 si qso_id/fichier manquant ou invalide, 404 si le QSO a disparu entre-temps)
- **Note** : référence stockée dans le champ qsl_scan du QSO ; ancien scan supprimé si remplacé ; servi ensuite via GET /qsl_scans/xxx

### POST `/qsl/sync`

Importe les confirmations QSL LoTW et marque les QSO correspondants comme confirmés.

- **Paramètres** : JSON {since?: date}
- **Réponse** : résultat de logx_qsl.sync_lotw(...)
- **Note** : Nécessite des identifiants LoTW configurés.

### POST `/qrz_logbook/test`

Vérifie la validité de la clé API QRZ Logbook (ACTION=STATUS) sans insérer de QSO factice.

- **Paramètres** : aucun (utilise la config enregistrée)
- **Réponse** : résultat de logx_qrz_push.test_connection(...)
- **Note** : Nécessite une clé API QRZ Logbook configurée.


## Assistant IA (coach, agent, proxy)

<a id="ai"></a>

### GET `/data/refresh`

Déclenche un rafraîchissement des données IA (clusters + logs + scoring) à partir de la config passée en query string.

- **Paramètres** : config passée via query string (lue par _load_config_from_query)
- **Réponse** : résultat de do_refresh(cfg) en JSON, ou {error} en 500

### GET `/data/system_prompt`

Renvoie le prompt système actuellement utilisé pour l'assistant IA, construit à partir de la config.

- **Paramètres** : config via query string
- **Réponse** : {system_prompt}

### GET `/coach/state`

État structuré du coach de stratégie (sans appel IA) : suggestions, densité de nouveaux multiplicateurs sur le cluster, indice K, et cibles jamais travaillées à vie repérées sur le cluster.

- **Paramètres** : lang (langue des textes, défaut fr) ; nudges=1 (calcule en plus une phrase d'action événementielle)
- **Réponse** : objet coach.build_coach_state(...) enrichi de hints/new_targets et éventuellement nudge
- **Note** : DXMaps interrogé en réseau uniquement pour concours VHF+ avec cache 10 min ; reste des données 100% cache/local.

### GET `/coach/debrief`

Débrief post-concours : statistiques déterministes du log plus un prompt prêt à envoyer à l'IA (le client l'envoie ensuite à /proxy/ai).

- **Paramètres** : aucun
- **Réponse** : objet coach.build_debrief(cfg_snap, log_copy)
- **Note** : La clé API IA reste côté serveur, ce endpoint ne fait qu'un calcul déterministe.

### GET `/coach/answer`

Réponse déterministe (zéro LLM) à un sujet du chat rapide, utilisée comme repli hors-ligne quand l'IA est injoignable.

- **Paramètres** : topic (sujet demandé) ; lang (langue, défaut fr)
- **Réponse** : {ok, topic, text}
- **Note** : Aucun réseau : l'indice K vient uniquement du cache.

### GET `/agent/analyze/state`

État d'une analyse IA lancée côté serveur (pour reprendre l'affichage après un changement de page).

- **Paramètres** : id (string)
- **Réponse** : objet état de l'analyse (status, texte...)
- **Note** : nécessite qu'une analyse ait été démarrée via POST /agent/analyze

### GET `/agent/analyze/stream`

Flux SSE d'une analyse IA en cours, pousse la réponse token par token au lieu d'attendre le texte complet.

- **Paramètres** : id (string)
- **Réponse** : flux Server-Sent Events (text/event-stream)
- **Note** : la génération tourne dans un thread de fond indépendant ; repli possible sur /agent/analyze/state (polling)

### GET `/agent/act/state`

État d'une chasse assistée par IA (tool-use) : texte + action proposée à confirmer par l'opérateur.

- **Paramètres** : id (string)
- **Réponse** : objet état (status, action proposée...)
- **Note** : nécessite qu'une session ait été lancée via POST /agent/act ; utilise une clé API IA

### POST `/wsjtx/strategy`

Lance en tâche de fond une analyse IA de la série de décodages FT8 d'une station DX pour conseiller où/quand l'appeler dans un pile-up (stratégie pile-up FT8).

- **Paramètres** : Corps JSON : call (indicatif requis)
- **Réponse** : {'id':aid,'status':'running'} — résultat récupérable via GET /wsjtx/strategy/state (voir ci-dessus)
- **Note** : Nécessite une clé API IA configurée (CONFIG) ; purement consultatif, aucune émission ; requiert au moins 2 décodages récents sinon message d'attente

### POST `/agent/act`

Lance en tâche de fond un agent IA qui PROPOSE une action physique (pointer le rotor / QSY) via tool-use — le serveur n'exécute rien, c'est le clic client qui appelle ensuite /rotor/point ou /rig/qsy.

- **Paramètres** : Corps JSON : message (optionnel, question par défaut pré-remplie), needs_context (bool, défaut true), system (prompt système optionnel)
- **Réponse** : {'id':aid,'status':'running'} — résultat récupérable via GET /agent/act/state (voir ci-dessus)
- **Note** : Nécessite une clé API IA configurée ; single-shot ; fournisseur non-Anthropic retombe en texte seul (pas de tool-use)

### POST `/log/audit`

Lance en tâche de fond un audit IA du journal avant dépôt du log, en plus du vérificateur déterministe existant.

- **Paramètres** : Aucun corps requis (utilise le journal courant et la config du serveur)
- **Réponse** : {'id':aid,'status':'running','truncated':bool,'count':N} ; {'error':'Aucun QSO à auditer'} 400 si journal vide
- **Note** : Nécessite une clé API IA configurée ; sortie LLM forcée en JSON structuré (schéma AUDIT_SCHEMA)

### POST `/agent/analyze`

Lance en tâche de fond une analyse/réponse IA en streaming (chat assistant), le résultat étant bufferisé pour être récupéré par polling ou par flux SSE.

- **Paramètres** : Corps JSON : messages (historique), message (texte brut optionnel), needs_context (bool), system (prompt optionnel), max_tokens (défaut 4096)
- **Réponse** : {'id':aid,'status':'running'} — à suivre via GET /agent/analyze/state (polling) ou GET /agent/analyze/stream (SSE, voir ci-dessus)
- **Note** : Le modèle demandé par la page cliente est ignoré, c'est le réglage de CONFIG qui fait foi ; job de fond survit à un changement d'onglet

### POST `/proxy/ai`

Proxy IA universel côté serveur vers Anthropic, ou tout fournisseur compatible OpenAI (OpenAI/Mistral/xAI/DeepSeek), ou Gemini, selon le fournisseur choisi en CONFIG — évite d'exposer la clé API au navigateur.

- **Paramètres** : Corps JSON : messages (requis), system (prompt optionnel), max_tokens (défaut 4096) ; le modèle est toujours celui réglé en CONFIG, jamais celui envoyé par la page appelante
- **Réponse** : Réponse normalisée au format Anthropic : {'content':[{'type':'text','text':...}]} ; {'error':{'message':...}} en cas d'échec (ex. 400 si aucune clé API configurée)
- **Note** : Alias exact : POST /proxy/anthropic répond de manière identique ; nécessite une clé API IA configurée en CONFIG

### POST `/proxy/anthropic`

Alias strictement identique à POST /proxy/ai (même bloc de code, self.path in ('/proxy/ai','/proxy/anthropic')).

- **Paramètres** : Voir /proxy/ai
- **Réponse** : Voir /proxy/ai
- **Note** : Route alias — documenter une seule fois avec /proxy/ai suffit


## Mise à jour logicielle

<a id="update"></a>

### GET `/app/update_check`

Dernière release GitHub connue pour la mise à jour logicielle (cache 6h, jamais d'appel réseau dans ce thread).

- **Paramètres** : aucun
- **Réponse** : objet check (logx_update.get_cached_check)
- **Note** : service tiers GitHub, cache seul ici

### GET `/app/update_status`

Progression du téléchargement de mise à jour en cours (idle/downloading/done/error).

- **Paramètres** : aucun
- **Réponse** : objet statut téléchargement

### GET `/app/gateway_status`

Indique si ce poste a un accès internet confirmé récemment (donc capable de relayer une requête GitHub pour un autre poste du LAN) — interrogé backend-à-backend.

- **Paramètres** : aucun
- **Réponse** : objet statut passerelle (logx_update.gateway_status)
- **Note** : réservé au LAN (403 sinon)

### GET `/app/update_relay`

Relais réel : ce poste (déclaré passerelle) télécharge l'asset GitHub officiel et relaie les octets en flux à un poste pair sans internet.

- **Paramètres** : tag (string), platform (string)
- **Réponse** : flux binaire de l'asset relayé
- **Note** : réservé au LAN, limité en fréquence par IP, vérifie tag/plateforme côté serveur (anti-SSRF)

### GET `/app/update_serve_status`

État du fichier de mise à jour déjà téléchargé et vérifié (SHA-256) que ce poste peut servir en secours à un pair sans internet.

- **Paramètres** : aucun
- **Réponse** : objet statut (logx_update.serve_status)
- **Note** : réservé au LAN

### GET `/app/update_serve`

Sert en flux le fichier de mise à jour déjà vérifié (chemin interne fixe, jamais un paramètre client) à un poste pair du LAN.

- **Paramètres** : aucun
- **Réponse** : flux binaire du fichier vérifié, ou erreur 404 si aucun disponible
- **Note** : réservé au LAN, limité en fréquence par IP

### POST `/app/update_download`

Démarre le téléchargement de la nouvelle version depuis GitHub (intégrité vérifiée en flux par SHA-256).

- **Paramètres** : aucun
- **Réponse** : {ok:true} ou {error}
- **Note** : Déclenché uniquement par un clic opérateur, jamais automatiquement.

### POST `/app/update_network_scan`

Sonde les postes du réseau local déjà connus pour trouver une passerelle ou un pair servant l'exécutable en secours.

- **Paramètres** : JSON {ips?: [string]} — filtré aux seules IP déjà connues comme pairs réels
- **Réponse** : résultat de logx_update.scan_network_candidates(...)
- **Note** : Anti-SSRF : n'accepte que des IP déjà vues comme pairs par ce serveur, jamais un hôte arbitraire fourni dans le corps.

### POST `/app/update_download_via_network`

Déclenche le téléchargement de la mise à jour via un poste candidat du réseau local (passerelle ou pair).

- **Paramètres** : JSON {mode: string, ips?: [string]}
- **Réponse** : {ok:true} ou {error}
- **Note** : Anti-SSRF identique à /app/update_network_scan ; refuse si le poste source n'a pas lui-même de référence SHA-256 vérifiée auprès de GitHub.

### POST `/app/update_install`

Applique la mise à jour préalablement téléchargée et relance l'application.

- **Paramètres** : aucun
- **Réponse** : {ok:true, restarting:true} ou {error}
- **Note** : Refuse si le téléchargement n'est pas terminé ou non vérifié (SHA-256) ; redémarre le serveur/processus.


## Réseau, diagnostic et télémétrie

<a id="network"></a>

### GET `/network/info`

Renvoie l'IP locale du serveur, le port, les URLs prêtes à l'emploi pour le logbook et la version mobile terrain, le nombre de pairs connectés et la version de l'application.

- **Paramètres** : aucun
- **Réponse** : {local_ip, port, url_logbook, url_terrain, peers, app_version}
- **Note** : Sans authentification ; app_version sert de référence au client pour se comparer plus tard à /log/status.

### GET `/debug/errors`

Renvoie les erreurs Python récentes capturées par sys.excepthook/threading.excepthook (module logx_errorlog), pour le bouton « Signaler un problème ».

- **Paramètres** : aucun
- **Réponse** : {errors: [...], log_path}
- **Note** : Nécessite le jeton de session (_require_auth) mais volontairement EXCLU du gate 'debug' global — reste utilisable par n'importe quel testeur.

### GET `/debug/*`

Garde-fou générique : tout chemin sous /debug/ (hors /debug/errors) est désactivé par défaut et renvoie 404 tant que server.debug=true n'est pas activé dans config.json ou la config envoyée par le client.

- **Paramètres** : aucun (contrôle uniquement le flag debug)
- **Réponse** : 404 {'error': "Endpoints /debug/* désactivés (server.debug=true dans config.json pour activer)"} si désactivé, sinon laisse passer vers la route spécifique
- **Note** : Porte d'entrée commune à toutes les routes /debug/* suivantes ; nécessite server.debug=true dans config.json.

### GET `/debug/test_on4kst`

Teste la connexion au chat ON4KST avec les identifiants sauvegardés côté serveur (jamais depuis la requête) et renvoie la sortie brute du serveur ON4KST.

- **Paramètres** : chat (optionnel, ex: salon 144/432) ; cmd (optionnel, commande ON4KST ex: /show users)
- **Réponse** : {ok, error, raw}
- **Note** : Nécessite server.debug=true ET le jeton de session ; identifiants et service tiers (ON4KST) requis côté serveur ; le mot de passe n'apparaît jamais dans la réponse.

### GET `/log/status`

Statut réseau global : nombre de pairs connectés, nombre de QSO, spots cluster en cache, version de l'application et liste détaillée des pairs (IP/version/dernier contact).

- **Paramètres** : aucun
- **Réponse** : {peers, qso_count, spots, app_version, peer_list}
- **Note** : Purge les entrées de pairs périmées (TTL) avant lecture.

### GET `/debug/spots`

Test direct des flux de spots DXSummit HF (3 bandes) plus un appel direct à fetch_dxsummit_hf, à but de diagnostic.

- **Paramètres** : aucun
- **Réponse** : objet avec un résultat ou message d'erreur par bande, plus fetch_dxsummit_hf_nofilter
- **Note** : Requiert server.debug=true, jeton de session ET limite de fréquence (_relay_rate_limited) ; déclenche de vraies requêtes réseau sortantes.

### GET `/debug/cluster`

Diagnostic exhaustif des clusters DX : teste plusieurs API HTTP et connexions telnet (ports 80/23/7300) vers divers serveurs cluster, plus les variables d'environnement proxy.

- **Paramètres** : aucun
- **Réponse** : objet avec un résultat par cluster/port testé + env_proxy
- **Note** : Requiert server.debug=true, jeton de session ET limite de fréquence ; peut prendre jusqu'à ~90 secondes (9 requêtes HTTP + 7 telnet).

### GET `/data/lan_url`

Renvoie les URL LAN utilisables pour connecter un téléphone/tablette (terrain/expédition) au logbook, installable en PWA.

- **Paramètres** : aucun
- **Réponse** : {port, ips, urls}

### GET `/data/network_status`

Dégradations réseau à signaler discrètement côté client (barre de statut) : disjoncteur callbook, état solaire, cloud sync, synchro MySQL.

- **Paramètres** : aucun
- **Réponse** : {'callbook':{...},'solar':{...},'cloudsync':{...},'mysql_sync':{...}}
- **Note** : pollable à intervalle rapproché, appels bornés en durée (ex. timeout SMB)

### POST `/telemetry/test`

Envoie immédiatement un heartbeat de télémétrie de test.

- **Paramètres** : JSON {endpoint?: string}
- **Réponse** : résultat de logx_telemetry.send_heartbeat(...)
- **Note** : Force temporairement telemetry_enabled=true pour ce test ; l'endpoint saisi prime sur celui déjà enregistré.


## Système et divers

<a id="misc"></a>

### GET `/shortcut/status`

Indique si la bannière « Créer un raccourci bureau ? » doit être affichée au premier lancement.

- **Paramètres** : aucun
- **Réponse** : {'show':bool}

### POST `/shortcut/create_desktop`

Crée un raccourci sur le bureau vers l'exécutable et marque la bannière comme traitée.

- **Paramètres** : aucun
- **Réponse** : résultat de logx_shortcut.create_and_mark()

### POST `/shortcut/dismiss`

Marque la bannière de proposition de raccourci bureau comme refusée, sans rien créer.

- **Paramètres** : aucun
- **Réponse** : {ok:true}


## Recherche et fichiers statiques

<a id="static"></a>

### GET `/search`

Recherche plein-texte dans le contenu visible des pages HTML (widget de la barre de nav, logx_search.js).

- **Paramètres** : q (query string, texte recherché)
- **Réponse** : {query, results: [...]} — résultats renvoyés par logx_search.search(q)
- **Note** : Aucun jeton requis (même logique que /network/info) : pas de donnée secrète exposée.

### GET `/` et fichiers statiques (`.html`, `.js`, `.css`, `.json`, `.svg`, `.png`, `.jpg`, `.gif`, `.webp`, `.pdf`, `.webmanifest`)

Sert les fichiers statiques du dossier de l'application (pages HTML, JS, CSS, assets) ; racine '/' redirige vers logx_configuration.html ; anciennes URLs pré-renommage redirigées vers leur équivalent logx_*.

- **Paramètres** : aucun (chemin dans l'URL)
- **Réponse** : contenu du fichier avec Content-Type déduit de l'extension, ou 404 si absent
- **Note** : pose le cookie rc_token si aucun mot de passe configuré ; redirige vers /auth/login sinon pour les pages .html
