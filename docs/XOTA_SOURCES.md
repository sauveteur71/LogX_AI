# Registre central des sources XOTA — LogX AI

Sources officielles retrouvées et **vérifiées en direct** (en-têtes / réponses
réelles inspectées, pas supposées) pour chaque programme « X-on-the-air » dont
LogX AI sait valider et enrichir les références. Ce fichier est la référence
unique : toute évolution d'endpoint se répercute ici.

## Deux architectures selon la source

| Modèle | Quand | Programmes | Redistribution |
|---|---|---|---|
| **Bulk** : export complet téléchargé + cache disque + `nearby` | la source publie un export complet ouvert | POTA, SOTA, WWFF, IOTA, WCA, **WWBOTA**, **DFCF** | copie locale chez l'OM, **jamais dans le dépôt** |
| **Par référence** : l'API/formulaire est interrogé pour LA réf tapée, cache mémoire | pas d'export ouvert, ou base protégée | **GMA**, **ARLHS** | rien n'est copié — on ne lit que la réf demandée |

Le modèle *par référence* est le bon choix quand la base est protégée (ARLHS) ou
quand seule une API par-réf existe (GMA) : le souci de droits ne se pose pas,
puisqu'on ne récupère que la fiche que l'opérateur saisit.

**Cadence de rafraîchissement des bases bulk XOTA : 15 jours** (décision F4GLD),
sauf SOTA (hebdomadaire, choix antérieur). POTA/WWFF historiques restent à 30 j.

## Sources par programme

### DFCF — Diplôme des Forts et Châteaux de France
- **Catalogue** : `https://dfcf.fr/listdept.htm` → ~100 pages `dept/dNN.html`.
- Modèle : bulk (agrégation des pages départementales), cache disque 15 j, fond.
- Pages HTML **irrégulières** (tab/espaces, dates en plage, indicatif collé à la
  commune) → parseur défensif par tokens. Nom + commune ; pas de coordonnées.
- Statut : **intégré** (PR #417). Redistribution : cache local, hors dépôt.

### WWBOTA — World Wide Bunkers on the Air
- **Base maître** : `https://api.wwbota.org/bunkers/?format=CSV`
  (`Scheme,DXCC,Reference,Name,Type,Lat,Long,Locator`, ~31 400 bunkers géoloc.).
- Site : `https://wwbota.net/` · liste `https://wwbota.net/list/` · carte
  `https://wwbota.net/map/` · guide ADIF `https://wwbota.net/adifguide/`.
- Modèle : bulk, cache disque 15 j, `nearby` disponible. Réf « B/F-0001 ».
- Statut : **intégré** (PR #418). Droits : base protégée → cache local, hors dépôt.

### GMA — Global Mountain Activity
- **API par référence** : `https://cqgma.org/api/ref/?REF` (JSON : name, height,
  latitude, longitude, region_name, act_count, wwff, deleted…).
- Site/base HTML : `https://cqgma.org/` · `https://cqgma.org/gmamtninfo.php`.
- Modèle : par référence, cache mémoire. Réf « DL/BE-055 » (schéma SOTA).
- Statut : **intégré** (PR #419). Aucun bulk → aucune redistribution.

### ARLHS — Amateur Radio Lighthouse Society (WLOL)
- **Base WLOL** : `https://wlol.arlhs.com/index.php?mode=search`
  (`section`=préfixe pays + `number`) → fiche HTML (nom, coord DMS, locator,
  activations). Site : `https://arlhs.com/`.
- Modèle : par référence, cache mémoire. Réf « FRA-113 ». Coord DMS → décimal.
- Statut : **intégré** (PR #420). Droits : **« Copyright ARLHS, LLC »** →
  lookup par-réf uniquement, jamais de copie de la base.

### ILLW — International Lighthouse & Lightship Weekend
- **PAS une base permanente** : inscriptions **annuelles** à un événement.
- Site : `https://illw.net/` · règles `https://illw.net/index.php/guidelines` ·
  inscrits `https://illw.net/index.php/entrants-list-YYYY`.
- Modèle à retenir (F4GLD) : **une table par année** (`illw_entries` avec
  `event_year`), pas une base de sites permanente. Distinct d'ARLHS.
- Statut : **à faire** — architecture propre (entrées annuelles), à cadrer.

## Registre machine

```json
{
  "sources": [
    {"program_code": "DFCF", "name": "Diplôme des Forts et Châteaux de France",
     "website": "https://dfcf.fr/", "database": "https://dfcf.fr/listdept.htm",
     "model": "bulk", "refresh_days": 15, "type": "permanent_castle_catalog",
     "status": "integrated", "pr": 417, "redistribution": "local_cache_only"},
    {"program_code": "WWBOTA", "name": "World Wide Bunkers on the Air",
     "website": "https://wwbota.net/", "database": "https://api.wwbota.org/bunkers/?format=CSV",
     "map": "https://wwbota.net/map/", "adif": "https://wwbota.net/adifguide/",
     "model": "bulk", "refresh_days": 15, "type": "permanent_bunker_database",
     "status": "integrated", "pr": 418, "redistribution": "local_cache_only"},
    {"program_code": "GMA", "name": "Global Mountain Activity",
     "website": "https://cqgma.org/", "api": "https://cqgma.org/api/ref/?",
     "database": "https://cqgma.org/gmamtninfo.php",
     "model": "per_reference", "type": "permanent_summit_database",
     "status": "integrated", "pr": 419, "redistribution": "none_per_reference"},
    {"program_code": "ARLHS", "name": "Amateur Radio Lighthouse Society",
     "website": "https://arlhs.com/", "database": "https://wlol.arlhs.com/index.php?mode=search",
     "model": "per_reference", "type": "permanent_lighthouse_database",
     "status": "integrated", "pr": 420, "redistribution": "copyright_per_reference_only"},
    {"program_code": "ILLW", "name": "International Lighthouse and Lightship Weekend",
     "website": "https://illw.net/", "rules": "https://illw.net/index.php/guidelines",
     "entries": "https://illw.net/index.php/entrants-list-YYYY",
     "model": "annual_event_entries", "type": "annual_event",
     "status": "todo", "permanent_reference_database": false}
  ]
}
```

> Rappel : `status: integrated` = base interrogeable par le relevé de saisie
> (`/activation_db/lookup`) et la validation de référence. Les bases marquées
> `local_cache_only` / `copyright_per_reference_only` ne sont **jamais**
> recopiées dans le dépôt — cf. `.gitignore` (caches runtime).
