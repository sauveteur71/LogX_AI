# -*- coding: utf-8 -*-
"""IOTA (Islands On The Air) — base des groupes d'îles + spots en direct.

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

Pas de source de spots DÉDIÉE : la seule trouvée (iota-world.org/iotamaps/
index_tools.php?what=getclusterdata) est un endpoint AJAX interne non
documenté, mélangeant des spots DX généraux tagués IOTA plutôt que des spots
IOTA propres — écartée par le même principe que ham365.net/sotamaps.org
(cf. logx_sota.py) : pas assez fiable pour être présentée au même niveau de
confiance que POTA/SOTA/WWFF.

Spots en direct SANS dépendance externe fragile (spots_from_clusters ci-
dessous) : les spots cluster classiques déjà collectés par logx_clusters.py
(F5LEN, DXSummit, DXWatch, telnet...) portent très souvent la référence IOTA
en commentaire ("IOTA EU-045", "TNX EU-123 QSL VIA..."). On reconnaît le
format CC-NNN dans ce commentaire et on le valide contre groups_db (la vraie
base ci-dessus) avant de taguer le spot IOTA — un simple motif CC-NNN qui
n'existe PAS comme référence réelle (numéro de série, etc.) est écarté.
"""
import json
import re

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
    """Contenu du cache islands.json sur disque, ou None s'il est absent,
    illisible (encodage corrompu) ou manifestement tronqué (même seuil que le
    téléchargement)."""
    try:
        with open(ISLANDS_FILE, encoding='utf-8', errors='replace') as f:
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
    items = groups_db.items()
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


# ─── SPOTS EN DIRECT (dérivés des commentaires de spots cluster) ────────────

IOTA_REF_RE = re.compile(r'\b([A-Z]{2}-\d{3})\b')


def _spot_info_and_call(spot):
    """(commentaire, indicatif) d'un spot cluster brut, quel que soit son
    format de collecte : dict normalisé (clé 'info' — la quasi-totalité des
    sources, cf. logx_clusters._normalize_spot et fetch_dxsummit_hf/
    fetch_dxwatch_hf/fetch_telnet_cluster) ou liste brute de cellules HTML
    (F5LEN, seule source qui ne passe pas par _normalize_spot). Même
    distinction déjà utilisée par logx_departments.department_targets et
    logx_scoring.build_ranked_spots pour la même raison (formats hétérogènes
    accumulés dans SPOTS_CACHE au fil des sources).

    Cette fonction elle-même NE tronque PAS l'indicatif au premier '/' : utile
    pour les activations IOTA signées avec un préfixe DXpedition (ex.
    '9A/DF5WC') dont on veut garder l'indicatif de base après le préfixe.
    ANGLE MORT connu : pour les spots VHF (buckets '144'/'432' de SPOTS_CACHE,
    et tout spot dict issu de logx_clusters.fetch_all_vhf_spots — DXSummit VHF,
    DXWatch VHF, HamQTH, HamSpirit, DXMaps), _normalize_spot a DÉJÀ coupé
    l'indicatif à la première '/' en amont (ne gardant que le suffixe '/P' pour
    l'affichage carte) : cette fonction reçoit alors un indicatif déjà tronqué
    et ne peut pas restaurer le préfixe perdu. La préservation complète ne
    s'applique donc réellement qu'aux sources qui n'ont jamais transité par
    _normalize_spot : le bucket HF générique (dxsummit_hf/dxwatch_hf/telnet,
    dicts bruts + f5len_hf, liste de cellules brutes) et le bucket 50 MHz
    (fetch_cluster_f5len appelé directement, sans passer par
    fetch_all_vhf_spots). POTA/SOTA/WWFF gardent d'ailleurs eux aussi
    l'indicatif complet tel quel dans leurs spots (cf. fetch_pota_spots)."""
    if isinstance(spot, dict):
        call = str(spot.get('call') or spot.get('dx') or '').upper()
        return str(spot.get('info') or ''), call
    if isinstance(spot, (list, tuple)) and spot:
        call = str(spot[0]).upper()
        return ' '.join(str(c) for c in spot[1:]), call
    return '', ''


def _spot_raw_freq(spot, is_dict):
    """Fréquence BRUTE d'un spot cluster, unité NON normalisée : clé 'freq'
    pour le format dict, cellule spot[1] pour le format liste (F5LEN — même
    cellule que celle parsée par logx_clusters.fetch_all_vhf_spots et
    logx_http._fetch_spots_hf_src pour la clé de dédoublonnage). Auparavant
    cette fonction n'existait pas et le format liste recevait toujours 0.0 :
    la vraie fréquence était pourtant présente en clair dans spot[1], jamais
    lue. 0.0 si absente/illisible (la bande retombe alors sur le libellé du
    bucket, cf. spots_from_clusters)."""
    try:
        if is_dict:
            return float(spot.get('freq') or 0)
        if isinstance(spot, (list, tuple)) and len(spot) > 1:
            return float(re.sub(r'[^\d.]', '', str(spot[1])))
    except (TypeError, ValueError):
        pass
    return 0.0


def spots_from_clusters(spots_by_band=None):
    """Spots IOTA en direct, DÉDUITS des spots cluster déjà collectés — jamais
    un appel réseau propre à ce module (cf. docstring de tête). `spots_by_band`
    est le même format que celui consommé par logx_scoring.build_ranked_spots
    ({label: [spots]}) ; à défaut, on lit directement logx_clusters.SPOTS_CACHE
    (copie superficielle : les fetchs remplacent une clé entière plutôt que de
    muter une liste en place, une copie du dict suffit contre un changement de
    taille pendant l'itération).

    Un spot cluster est tagué IOTA quand son commentaire contient une
    référence au format CC-NNN qui existe RÉELLEMENT dans groups_db — garde-
    fou contre un faux positif (numéro de série, etc. qui ressemblerait au
    format sans être une vraie référence).

    Format générique du logiciel, mêmes clés que logx_pota.fetch_pota_spots /
    logx_sota.fetch_sota_spots / logx_wwff.fetch_wwff_spots — dont la
    convention 'freq' TOUJOURS en kHz (cf. leurs docstrings respectifs)."""
    if spots_by_band is None:
        from logx_clusters import SPOTS_CACHE
        spots_by_band = dict(SPOTS_CACHE)
    groups_db.ensure_loading_started()
    from logx_scoring import _band_from_freq

    out = []
    seen = set()
    for band_label, spots in (spots_by_band or {}).items():
        for spot in spots or []:
            info, call = _spot_info_and_call(spot)
            if not call or len(call) < 3 or not info:
                continue
            code = None
            for m in IOTA_REF_RE.finditer(info.upper()):
                if groups_db.get(m.group(1)):
                    code = m.group(1)
                    break
            if not code:
                continue
            key = (call, code)
            if key in seen:
                continue
            seen.add(key)
            is_dict = isinstance(spot, dict)
            raw_freq = _spot_raw_freq(spot, is_dict)
            band = _band_from_freq(raw_freq) or str(band_label).replace(' MHz', '').replace(' GHz', '')
            # Unité de sortie TOUJOURS en kHz (convention POTA/WWFF) : selon la
            # source, raw_freq est en MHz (spots VHF, ex. F5LEN "50.185") ou
            # déjà en kHz (spots HF normalisés, ex. DXSummit 14260.0) — même
            # heuristique de magnitude que _band_from_freq ci-dessus, pour ne
            # jamais mélanger les deux unités dans le champ exposé.
            freq_khz = raw_freq * 1000 if 0 < raw_freq <= 1000 else raw_freq
            group = groups_db.get(code) or {}
            out.append({
                'call': call,
                'freq': freq_khz,
                'band': band,
                'mode': str(spot.get('mode') or '') if is_dict else '',
                'reference': code,
                'island_name': group.get('name', ''),
                'lat': group.get('lat'),
                'lon': group.get('lon'),
                'comment': info.strip(),
                'spotter': str(spot.get('spotter') or '') if is_dict else '',
                'time': str(spot.get('time') or '') if is_dict else '',
                'source': 'iota-cluster',
            })
    return out
