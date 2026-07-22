# -*- coding: utf-8 -*-
"""IOTA (Islands On The Air) — base des groupes d'îles (pas de spots en direct).

Source officielle, publique, sans clé, documentée par IOTA elle-même pour un
usage tiers (téléchargement direct, rafraîchi chaque jour à 00:00 UTC) :
  - https://www.iota-world.org/islands-on-the-air/downloads/download-file.html?path=groups.json
    (~750 groupes, un par référence IOTA — ex. EU-064 — avec une boîte
    englobante lat/lon min/max plutôt qu'un point unique, une île pouvant
    couvrir une zone étendue).
  - .../download-file.html?path=islands.json (~10 000 îles individuelles,
    chacune rattachée à un refno de groupe, sans coordonnées propres) — sert
    UNIQUEMENT à enrichir la recherche par nom (ex. chercher "Agalega" doit
    trouver AF-001 même si le nom du GROUPE diffère du nom de l'île).

Pas de spots en direct : la seule source trouvée (iota-world.org/iotamaps/
index_tools.php?what=getclusterdata) est un endpoint AJAX interne non
documenté, mélangeant des spots DX généraux tagués IOTA plutôt que des spots
IOTA propres — écartée par le même principe que ham365.net/sotamaps.org
(cf. logx_sota.py) : pas assez fiable pour être présentée au même niveau de
confiance que POTA/SOTA/WWFF.
"""
import json

from logx_activation_db import ActivationDatabase

GROUPS_URL = 'https://www.iota-world.org/islands-on-the-air/downloads/download-file.html?path=groups.json'
ISLANDS_URL = 'https://www.iota-world.org/islands-on-the-air/downloads/download-file.html?path=islands.json'
GROUPS_FILE = 'iota_groups.json'
ISLANDS_FILE = 'iota_islands.json'


def _looks_valid_groups_json(content):
    """Garde-fou avant d'écraser le cache : jamais un fichier tronqué ou une
    page d'erreur à la place du vrai export (~750 groupes, ~290 Ko)."""
    if not content or len(content) < 100_000:
        return False
    return content.count('"refno"') > 500


def _parse_groups_json(content):
    """JSON -> liste de dicts. Clés réelles (vérifiées en direct) : refno,
    name, dxcc_num, latitude_max/min, longitude_max/min, grp_region,
    whitelist, pc_credited, comment. Le centre de la boîte englobante sert de
    coordonnée approximative pour nearby() — moins précis qu'un point unique,
    mais suffisant pour « quelle île à proximité » à l'échelle d'un groupe."""
    try:
        items = json.loads(content)
    except (ValueError, TypeError):
        return []
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        code = (it.get('refno') or '').strip().upper()
        if not code:
            continue
        try:
            lat = (float(it['latitude_max']) + float(it['latitude_min'])) / 2
            lon_min = float(it['longitude_min'])
            lon_max = float(it['longitude_max'])
            # Groupe à cheval sur l'antiméridien (ex. Fidji : min=177, max=-178) :
            # la moyenne arithmétique donnerait ~0° (golfe de Guinée, à 19 000 km).
            # On déroule sur [0,360[ avant de moyenner, puis on renormalise.
            if lon_max < lon_min:
                lon_max += 360
            lon = (lon_max + lon_min) / 2
            if lon > 180:
                lon -= 360
        except (KeyError, TypeError, ValueError):
            lat = lon = None
        out.append({
            'code': code,
            'name': (it.get('name') or '').strip(),
            'dxcc_num': it.get('dxcc_num'),
            'island_names': [],  # rempli par _enrich_with_islands()
            'lat': lat,
            'lon': lon,
        })
    return out


def _read_islands_cache():
    """Contenu du cache islands.json sur disque, ou None s'il est absent ou
    manifestement tronqué (même seuil que le téléchargement)."""
    try:
        with open(ISLANDS_FILE, encoding='utf-8') as f:
            raw = f.read()
    except OSError:
        return None
    return raw if raw and len(raw) >= 100_000 else None


def _enrich_with_islands(groups):
    """Ajoute à chaque groupe la liste des noms d'îles individuelles qui le
    composent (islands.json), pour que la recherche par nom d'île retrouve le
    bon refno même si le nom du groupe est différent. Non bloquant : sans
    islands.json (ni réseau ni cache), les groupes restent utilisables tels
    quels (juste sans cet enrichissement de recherche).

    Le cache disque est LU avant tout appel réseau (il était auparavant en
    écriture seule : re-téléchargement de ~10 000 îles à chaque démarrage, et
    recherche par nom d'île morte hors-ligne malgré un fichier valide posé sur
    le disque). Un cache de moins de 30 jours évite le réseau ; un cache plus
    vieux sert de repli si le téléchargement échoue (activation portable /P)."""
    import os
    import time
    raw = None
    try:
        age_days = (time.time() - os.path.getmtime(ISLANDS_FILE)) / 86400
    except OSError:
        age_days = None
    if age_days is not None and age_days < 30:
        raw = _read_islands_cache()
    if raw is None:
        from logx_utils import fetch_url
        fetched = fetch_url(ISLANDS_URL, timeout=30)
        if fetched and len(fetched) >= 100_000:
            raw = fetched
            try:
                from logx_activation_db import atomic_write
                atomic_write(ISLANDS_FILE, raw)
            except OSError:
                pass
        else:
            raw = _read_islands_cache()  # repli : cache périmé accepté hors-ligne
    if not raw:
        return groups
    try:
        islands = json.loads(raw)
    except (ValueError, TypeError):
        return groups
    if not isinstance(islands, list):
        return groups
    by_code = {g['code']: g for g in groups}
    for isl in islands:
        if not isinstance(isl, dict):
            continue
        code = (isl.get('refno') or '').strip().upper()
        name = (isl.get('name') or '').strip()
        g = by_code.get(code)
        if g and name:
            g['island_names'].append(name)
    return groups


def _parse_and_enrich(content):
    groups = _parse_groups_json(content)
    return _enrich_with_islands(groups)


groups_db = ActivationDatabase(
    label='IOTA',
    source_url=GROUPS_URL,
    cache_file=GROUPS_FILE,
    parse_fn=_parse_and_enrich,
    valid_fn=_looks_valid_groups_json,
    # IOTA republie chaque jour à 00:00 UTC, mais le moteur générique traite un
    # cache expiré comme INEXISTANT (pas de repli sur cache périmé) : avec 1 jour,
    # 24 h sans réseau suffisaient à perdre toute la base malgré un fichier valide
    # sur disque. 30 jours = même politique que POTA/WWFF ; une base de référence
    # quasi statique n'a pas besoin d'être à J+0.
    max_age_days=30,
    fetch_timeout=30,
)


def search_groups(query, limit=25):
    """Comme ActivationDatabase.search(), mais cherche aussi dans les noms
    d'îles individuelles (island_names), pas seulement le nom du groupe."""
    groups_db.ensure_loading_started()
    query = (query or '').strip()
    if len(query) < 2:
        return []
    q_upper = query.upper()
    from logx_activation_db import strip_accents
    q_folded = strip_accents(query).lower()
    with groups_db._lock:
        items = groups_db._state['list']
        if not items:
            return []
        by_code_prefix = [it for it in items if it['code'].startswith(q_upper)]
        if len(by_code_prefix) >= limit:
            return by_code_prefix[:limit]

        def matches(it):
            if q_folded in strip_accents(it.get('name', '')).lower():
                return True
            return any(q_folded in strip_accents(n).lower() for n in it.get('island_names', []))

        by_name = [it for it in items if matches(it)]
        seen = {it['code'] for it in by_code_prefix}
        merged = by_code_prefix + [it for it in by_name if it['code'] not in seen]
        return merged[:limit]
