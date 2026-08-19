---
name: ressources-techniques-veille-2026-07-21
description: État des lieux du document de veille technique LogX_AI_Ressources_Techniques.md (21/07/2026) — ce qui est déjà fait vs ce qui reste
metadata: 
  node_type: memory
  type: reference
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-06T06:59:07.003Z
---

L'utilisateur a fourni `LogX_AI_Ressources_Techniques.md` (présent à la racine du repo, non tracké, + une copie dans `~/Downloads`) : une veille technique de 9 sections (formats ADIF/Cabrillo/EDI, callbook, spots temps réel, CAT/interop, propagation, QSL, projets open-source de référence, communautés). Avant d'agir dessus, vérifié point par point contre le code réel — la plupart des pistes « lot rapide » et « lot moyen » du §9 étaient **déjà implémentées** :

**Déjà fait (vérifié dans le code) :**
- Callbook cascade QRZ→HamQTH→HamDB : [[audit-securite-qualite-2026-07-20]] et `logx_callbook.py`.
- Solaire officiel HamQSL XML (`logx_clusters.py:fetch_solar_data`), cty.dat auto-refresh AD1C (`logx_dxcc.py:update_cty_if_stale`).
- Interop réseau N1MM/DXLog port 12060 UDP `<contactinfo>` : `logx_adifnet.py`.
- RBN : fait en telnet direct (pas via le repli JSON HamQTH suggéré par le doc — piste d'amélioration robustesse restante mais mineure).

**Vrai manque identifié et comblé (21/07/2026, branche `feat/aide-config-websdr-guide`) :**
`logx_activation.py` (POTA/SOTA/IOTA/WWFF/ARLHS/WCA) était **entièrement local/déterministe** — validation de référence + progression depuis le log, aucune connexion à une vraie API. Ajouté `logx_pota.py` : lecture en direct de `GET https://api.pota.app/spot/activator` (API publique sans clé, structure JSON vérifiée par appel réel : `spotId/activator/frequency/mode/reference/parkName/spotTime/spotter/comments/name/locationDesc/grid4/grid6/latitude/longitude/count`), endpoint `/data/pota_spots`, panneau « 🏞️ ACTIVATEURS POTA EN DIRECT » sur `logx_propagation.html`, cache 90 s. Testé en conditions réelles (12 activations réelles récupérées). **Volontairement PAS implémenté** : poster son propre spot (`POST /spot/`) — le doc ne donne pas de format d'authentification vérifié, mieux vaut ne rien faire que deviner sur un service public partagé.

**Pistes du document restant non traitées (à reprendre si utile un jour) :**
- Lots « structurants » (étudier qxsl/Cloudlog/Wavelog pour l'architecture, Tucnak pour la conformité EDI) : veille, pas d'action de code directe.

**TOUT LE RESTE DE CETTE SECTION EST FAIT (vérifié en code le 06/08/2026, session
suivante — la mémoire ci-dessus datait du 21/07 et n'avait pas été mise à jour
par les sessions qui ont ensuite tout implémenté) :**
- SOTA API réelle : `logx_sota.py` (spots api2.sota.org.uk + base sommets
  storage.sota.org.uk/summitslist.csv, ~230k sommets, recherche/validation/
  proximité) + `logx_sota_spot.py` (auto-spot OAuth SSO PKCE, avec gate
  explicite `sota_ai_approval_ack` car les CGU de l'API SOTA interdisent tout
  logiciel généré par IA sans accord préalable — case à cocher dédiée dans
  CONFIG, en plus du clientId). Entièrement câblé (logx_http.py, CONFIG UI,
  tests `test_sota_spot.py`/`test_qrz_sota_http.py`).
- Validation ADIF stricte : `logx_adif_enums.py` (bandes+modes ADIF 3.1.7
  officiel, recopié depuis adif.org — offline-first, le standard change peu),
  utilisé par `logx_import.py`/`logx_qsl.py`.
- Repli RBN JSON (hamqth ou autre) : **recherché et DÉLIBÉRÉMENT écarté**, pas
  oublié — `logx_rbn.py` documente en tête pourquoi (l'endpoint JSON interne
  de reversebeacon.net est non documenté, verrouillé par un hash de version
  qui change à chaque déploiement du site, sans filtre serveur par indicatif ;
  RBN ne publie aucune alternative HTTP fiable pour du temps réel). Ne pas
  relancer cette piste sans nouvelle info — la doc officielle RBN n'offre
  toujours que le telnet 7000.
