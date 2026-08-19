---
name: chantier-programmes-activation-cw-dxpeditions-2026-07-22
description: "DXpeditions (NG3K), décodeur CW audio, et intégration complète POTA/SOTA/WWFF/IOTA/WCA (bases de références + spots) sur la branche feat/aide-config-websdr-guide"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-22T09:06:09.991Z
---

Chantier étalé sur plusieurs tours de la même session (22/07/2026), branche
`feat/aide-config-websdr-guide` : chasse aux DXpeditions (NG3K RSS), décodeur
CW audio temps réel, puis extension complète des programmes d'activation
(POTA/SOTA/WWFF/IOTA/WCA) avec bases de références téléchargées + spots en
direct où c'est légitime. Suite directe de [[rebrand-logx-ai]].

**Principe méthodologique central (à réutiliser pour tout futur programme
d'activation ou source externe)** : une source est UTILISABLE si documentée
pour un usage tiers, ou un flux RSS/JSON/CSV explicitement offert en
téléchargement, ou un endpoint qui répond proprement à un simple fetch sans
session de navigateur. Elle est REJETÉE si elle exige une auth par session
(Keycloak vu sur sotamaps.org), renvoie une erreur hors navigateur (ham365.net
`/IndexAjax/OnAirDxPedition` → HTTP 500), ou est visiblement un endpoint AJAX
interne. Sources ACCEPTÉES cette session : NG3K adxo.xml (DXpeditions),
api2.sota.org.uk + storage.sota.org.uk/summitslist.csv (SOTA), pota.app/
all_parks_ext.csv (POTA parcs), spots.wwff.co/static/spots.json +
wwff.co/wwff-data/wwff_directory.csv (WWFF), iota-world.org groups.json/
islands.json (IOTA, doc officielle, refresh quotidien 00:00 UTC), wcagroup.org/
FORMS/WCALIST.ods + `?feed=rss2` (WCA). REJETÉES : ham365.net, sotamaps.org.

**ARLHS n'a PAS été intégré** (ni base ni spots) : wlol.arlhs.com exige
explicitement une « written permission from ARLHS » dans son propre avis de
copyright pour toute réutilisation — contrairement à SOTA/WWFF/POTA dont les
exports sont librement offerts en téléchargement. Ce n'est pas un rejet
technique comme ham365/sotamaps, mais une vraie contrainte légale.
**Si l'utilisateur veut la base ARLHS, il doit d'abord obtenir cette
permission par email** — ne pas scraper sans ça.

**IOTA : spots en direct délibérément NON construits.** Le seul endpoint
trouvé (`iotamaps/index_tools.php?what=getclusterdata`) est non documenté et
mélange des spots DX généraux tagués IOTA plutôt que des spots IOTA propres —
seule la base de référence (groups.json + islands.json, ~1178 groupes) a été
construite, avec nearby() approximatif (centre de la boîte englobante, pas un
point unique).

**WCA n'a aucune coordonnée GPS dans sa source** (classeur .ods, colonnes :
№ WCA, № CASTLES, PREFIX, NAME OF CASTLE, LOCATION, INFORMATION) → pas de
fonction nearby() possible pour les châteaux, contrairement aux 4 autres
programmes. Ses « spots » (`?feed=rss2`) sont des activations ANNONCÉES À
L'AVANCE par les opérateurs sur leur blog, PAS des spots confirmés sur l'air —
étiquetés différemment dans l'UI pour ne pas induire en erreur.

**Architecture retenue** : moteur générique [logx_activation_db.py](../../../../SynologyDrive/RADIOAMATEUR/Programme%20pour%20contest/concours/logx_activation_db.py)
(`ActivationDatabase` — thread de fond, cache disque avec péremption,
recherche insensible aux accents, nearby par haversine) réutilisé par POTA/
WWFF/IOTA. `logx_sota.py` (déjà en prod, déjà testé) n'a PAS été migré vers ce
moteur pour ne pas risquer de régression sur du code qui marchait. WCA n'utilise
pas non plus le moteur générique (source binaire .ods à dézipper, pas de
coordonnées) — parsing dédié dans `logx_wca.py`. Endpoints HTTP génériques
`/activation_db/{search,lookup,nearby}?program=XXX` remplacent les anciens
`/sota/search` etc. (dispatch via `_activation_db_adapter()` dans
`logx_http.py`), et le JS de `logx_configuration.html` (config
`ACTIVATION_DB_PROGRAMS`) est paramétré par programme au lieu d'être dupliqué.

**Décodeur CW audio** (`logx_cwdecoder.js`, panneau flottant dans
`logx_logbook.html`) : deux bugs DSP réels trouvés SEULEMENT via test contre
de l'audio synthétique réel (OfflineAudioContext + oscillateur gaté), pas de
simples séquences de timing idéalisées — (1) biais de détection par blocs de
512 échantillons qui mesure les "marks" trop longs et les "gaps" trop courts
d'environ une durée de bloc (~11.6ms), corrigé en compensant chaque mesure ;
(2) boucle de rétroaction destructrice dans l'estimation adaptative de
l'unité de temps (EMA alimentée par un tiret mal classé en point → dérive
l'estimation → le tiret SUIVANT aussi mal classé...), corrigée en remplaçant
l'EMA par un MINIMUM glissant sur 12 marks (un point mal classé ne peut jamais
faire REMONTER un minimum). Leçon méthodologique : toujours tester un DSP
temps réel contre de l'audio réellement rendu, pas contre des données de
timing idéalisées.

**Pièges de vérification rencontrés cette session** (non-bugs produit) :
- curl échoue avec `schannel: CRYPT_E_NO_REVOCATION_CHECK` sur ce poste
  (interception antivirus, cf. [[robustesse-reseau-diffusion-publique]]) —
  ajouter `--ssl-no-revoke` pour les tests manuels en ligne de commande.
- Deux interpréteurs Python distincts : `python3` (pas de pytest) vs `python`
  (pytest 9.1.1 installé) — toujours utiliser `python -m pytest`, jamais
  `python3 -m pytest`.
- Des threads `daemon=True` de chargement de base tournant dans un process
  `python3 -c` tué en fin de script (`srv.shutdown()` puis sortie du process)
  peuvent laisser un fichier `.tmp` orphelin de `tempfile.mkstemp` si le kill
  survient entre l'écriture et `os.replace()` — inoffensif (jamais de
  corruption du fichier cible) mais peut laisser un fichier `*.NNNNNN.tmp` à
  nettoyer manuellement après des tests agressifs.

**Reste pour plus tard, non traité (pas demandé)** : GMA (Global Mountain
Activity, cqgma.org) et ILLW (International Lighthouse/Lightship Weekend,
illw.net, distinct d'ARLHS) — surfacés par la recherche mais jamais demandés
par l'utilisateur, à ne construire que sur demande explicite.
