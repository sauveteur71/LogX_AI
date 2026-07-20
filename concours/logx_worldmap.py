# -*- coding: utf-8 -*-
"""Carte du monde par pays DXCC (Europe / continent / monde) — extension
géographique de la chasse aux pays (logx_countries.py), qui reste la
seule source de vérité pour le calcul « travaillé » (par préfixe DXCC). Ce
module se contente d'associer chaque entité DXCC à un polygone du GeoJSON
mondial via un test point-dans-polygone sur le centroïde cty.dat — aucune
table de correspondance manuelle pays↔DXCC à maintenir, purement géographique
(comme le fait déjà logx_departments.py pour le locator → département).

GeoJSON : Natural Earth, admin-0 countries, échelle 110m (léger, cache disque
comme france_departements.geojson — re-téléchargé au 1er accès si absent).
"""
import json
import os

WORLD_GEOJSON_FILE = 'world_countries.geojson'
WORLD_GEOJSON_URL = ('https://raw.githubusercontent.com/nvkelso/'
                      'natural-earth-vector/master/geojson/'
                      'ne_110m_admin_0_countries.geojson')

_cache = {'features': None, 'entity_feature': None}


def load_world_geojson():
    """Contenu du GeoJSON mondial (cache disque, re-téléchargé s'il manque).
    Retourne le texte JSON ou '' si indisponible hors ligne."""
    if os.path.exists(WORLD_GEOJSON_FILE):
        try:
            with open(WORLD_GEOJSON_FILE, encoding='utf-8') as f:
                return f.read()
        except Exception:
            pass
    from logx_utils import fetch_url
    data = fetch_url(WORLD_GEOJSON_URL, timeout=30)
    if data and len(data) > 100000 and 'FeatureCollection' in data:
        try:
            with open(WORLD_GEOJSON_FILE, 'w', encoding='utf-8', newline='') as f:
                f.write(data)
        except Exception:
            pass
        return data
    return ''


# ─── POINT DANS POLYGONE (ray casting standard) ──────────────────────────────

def _point_in_ring(lon, lat, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            x_at_lat = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_at_lat:
                inside = not inside
        j = i
    return inside


def _point_in_geometry(lon, lat, geometry):
    """geometry = geometry GeoJSON (Polygon ou MultiPolygon). Ne teste que
    l'anneau extérieur de chaque polygone (les trous éventuels n'affectent
    pas un centroïde de pays à cette échelle simplifiée)."""
    gtype = (geometry or {}).get('type')
    coords = (geometry or {}).get('coordinates') or []
    if gtype == 'Polygon':
        polys = [coords]
    elif gtype == 'MultiPolygon':
        polys = coords
    else:
        return False
    for poly in polys:
        if poly and _point_in_ring(lon, lat, poly[0]):
            return True
    return False


def _load_features():
    """Liste des features du GeoJSON mondial, mise en cache mémoire (le
    fichier ne change qu'au 1er téléchargement)."""
    if _cache['features'] is not None:
        return _cache['features']
    feats = []
    raw = load_world_geojson()
    if raw:
        try:
            gj = json.loads(raw)
            for f in gj.get('features', []):
                props = f.get('properties', {}) or {}
                fid = props.get('ISO_A3') or props.get('ADM0_A3') or props.get('NAME')
                if not fid:
                    continue
                feats.append({
                    'id': fid,
                    'name': props.get('NAME') or props.get('ADMIN', ''),
                    'continent': props.get('CONTINENT', ''),
                    'geometry': f.get('geometry') or {},
                })
        except Exception:
            feats = []
    _cache['features'] = feats
    return feats


def invalidate_cache():
    """À appeler si world_countries.geojson ou cty.dat sont remplacés."""
    _cache['features'] = None
    _cache['entity_feature'] = None


def entity_to_feature_id(lat, lon, features=None):
    """Centroïde DXCC (lat, lon) -> id de feature GeoJSON dans lequel il
    tombe, ou None (mer, entité trop petite pour la simplification 110m...)."""
    if lat is None or lon is None:
        return None
    for f in (features if features is not None else _load_features()):
        if _point_in_geometry(lon, lat, f['geometry']):
            return f['id']
    return None


def _entity_feature_map():
    """{préfixe DXCC: id de feature}, calculé une fois (géométrie statique)."""
    if _cache['entity_feature'] is not None:
        return _cache['entity_feature']
    import logx_dxcc as dxcc
    features = _load_features()
    mapping = {}
    for e in dxcc.list_entities():
        fid = entity_to_feature_id(e['lat'], e['lon'], features)
        if fid:
            mapping[e['prefix']] = fid
    _cache['entity_feature'] = mapping
    return mapping


def worked_by_country(shared_log, contest_id=''):
    """{feature_id: {'name', 'continent', 'worked'}} pour chaque pays du
    GeoJSON mondial, calculé à partir des entités DXCC contactées
    (logx_countries, même logique que la chasse aux pays en liste)."""
    from logx_countries import _worked_keys
    worked_prefixes = _worked_keys(shared_log, contest_id)
    mapping = _entity_feature_map()

    out = {}
    for f in _load_features():
        out[f['id']] = {'name': f['name'], 'continent': f['continent'], 'worked': False}
    for prefix, fid in mapping.items():
        if prefix in worked_prefixes and fid in out:
            out[fid]['worked'] = True
    return out
