# Idée à creuser — indicatif spécial multi-postes (ex. TM6KJS), un seul log

> Note d'exploration écrite le 27/08/2026 (F4GLD en sieste, « creuser + point
> ensemble au réveil »). Rien n'a été codé pour ça — c'est un état des lieux.

## Le besoin (F4GLD)

Activer un indicatif spécial (ex. **TM6KJS**) **depuis chez lui** avec **une ou
plusieurs stations** qui n'émettent **jamais sur les mêmes fréquence / bande /
mode** en même temps. Objectif : que **toutes partagent le MÊME log**.

## Ce qui existe déjà (le cœur est couvert)

LogX AI a **trois** mécanismes de log partagé :

| Mécanisme | Fichier | Cas d'usage |
|---|---|---|
| **LAN sync** | `logx_lan_sync.py` | **Postes sur le même WiFi** — pile le scénario « depuis chez nous » |
| Cloud sync | `logx_cloudsync.py` | Multi-site via dossier partagé (Dropbox/Synology) |
| MySQL sync | `logx_mysql_sync.py` | Base de données partagée |

### LAN sync en détail (le pertinent ici)

- **Découverte auto** : beacon UDP broadcast (port 8073), TTL 60 s. Un poste
  éteint disparaît tout seul.
- **Fusion des QSO** : chaque poste **tire** le log des autres (HTTP
  `/log/lan/export`) et **fusionne** (`pull_and_merge`).
- **Déduplication** par clé **call · bande · mode · date · heure** : deux postes
  sur des **bandes différentes** = 2 QSO gardés ; même bande/heure = 1 seul.
  → Le log TM6KJS **unique et fusionné marche déjà**.
- **Sécurité** : jeton d'équipe optionnel (`lan_sync_token`), vérifié en
  `hmac.compare_digest`. Borné pour l'expédition (une socket, un thread, TTL).
- **Activation** : config `lan_sync_enabled` (désactivé par défaut).

### Sérialisation (numéros de série concours)

`/log/next_serial?band=X` alloue le prochain n° **par bande**, scopé au concours
actif, calculé sur le log fusionné. Comme la contrainte est « **jamais 2 postes
sur la même bande** », **aucune collision** : chaque bande a un seul poste qui
alloue. **Déjà bon.**

## Ce qui manque pour que ce soit fluide

Le **partage de log** est là. Ce qui manque, c'est la **coordination visuelle**
entre postes :

1. **🎯 Carte d'occupation des bandes (le vrai ajout)**
   Aujourd'hui le beacon annonce `iid`, `http_port`, `call`, `token` — **pas la
   bande/mode courants**. Pour la règle « jamais 2 sur la même bande », un
   tableau temps réel serait décisif :
   ```
   Poste A (cuisine)  → 20 m · SSB
   Poste B (shack)    → 40 m · CW
   Poste C (portable) → 2 m  · FM
   ```
   **Chantier** : ajouter `band`/`mode` au payload du beacon + au registre de
   pairs (`_peers`), exposer via `/log/status` (ou `/log/lan/peers`), et un
   petit panneau UI. Net, cadré, faisable. Le beacon étant en clair sur le LAN,
   pas de souci de confidentialité à y mettre la bande.

2. **Alerte « déjà en cours » temps réel** (optionnel)
   Le dédup agit à l'enregistrement. Un signal live « Poste B travaille cet
   indicatif sur 20 m » (comme le *partner-typing* du chat multi-op) éviterait
   le double-appel avant même de logger.

## Reco pour le point ensemble

- **Rien à construire** pour le log partagé : activer `lan_sync_enabled` (+
  éventuellement un `lan_sync_token` commun) suffit à avoir le log TM6KJS unique.
- **L'ajout à vraie valeur** = la **carte d'occupation des bandes**, qui rend la
  contrainte « jamais 2 sur la même bande » visuelle et évidente.
- **À décider** : périmètre (juste la carte ? + l'alerte temps réel ?), et si on
  le fait maintenant ou après le chantier tickers.

## Décisions F4GLD (27/08)

- **À distance sur réseaux internet différents = OUI** (Cloud Sync / MySQL, pas
  le LAN qui est même-réseau).
- **Carte d'occupation** : oui, **s'adapte au sync actif avec PRIORITÉ LOCALE** —
  LAN instantané entre postes locaux, bascule auto sur cloud/MySQL pour les
  distants, merge de tous les canaux, sans config manuelle.
- **Option** : un **assistant de session** « Activer un log partagé »
  (radioclub / expédition / activation spéciale) qui préconfigure indicatif
  commun + sync conseillé + affiche la carte.

## Plan d'implémentation (incrémental, TDD)

1. ✅ **Cœur pur** (`logx_occupancy.vue_occupation`) — vue + conflits (bande/mode).
2. ✅ **Registre serveur** (`poser_mon_statut` / `enregistrer_pair` / `vue`) —
   mon statut + pairs, TTL, thread-safe. Priorité locale = latest-ts-wins.
3. **Endpoints HTTP** (additifs) :
   - `POST /occupancy/heartbeat {band,mode}` → `poser_mon_statut` (le client
     LOGBOOK envoie sa bande/mode courantes, seul à les connaître en direct) ;
   - `GET /data/occupancy` → `vue()` (le panneau lit).
4. **Canaux** (transport SÉPARÉ du log → le sync du carnet n'est jamais touché) :
   - **LAN** : band/mode dans le beacon UDP + collecte des pairs (instantané) ;
   - **Cloud** : petit fichier `logx_occupancy_<call>_<iid>.json` par poste,
     lu par les autres (distant) ;
   - **MySQL** : table `occupancy` (upsert + lecture) (distant temps réel).
   - Chaque canal appelle `enregistrer_pair`.
5. **UI** : panneau « occupation des bandes » sur LOGBOOK (qui est où, conflits
   en rouge) + heartbeat client (currentBand/currentMode).
6. **Assistant de session** (radioclub / expé / activation) : préréglage.

**Risque** : l'étape 4 touche les modules de sync — d'où le transport SÉPARÉ
(fichiers/table/champ dédiés) pour ne jamais casser le log. Étapes 5-6 = UI, à
valider en navigateur avec F4GLD.

## Questions ouvertes (pour le point)

- Combien de postes en pratique (2 ? 3 ?) ?
- MySQL déjà en place chez toi (radioclub) ou on part sur Cloud folder ?
- La carte : panneau sur LOGBOOK, ou une page dédiée ?
