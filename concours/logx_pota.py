# -*- coding: utf-8 -*-
"""Spots d'activateurs POTA (Parks On The Air) en direct + base des parcs.

Complète le mode Activation (logx_activation.py, purement local/déterministe :
validation de référence + progression depuis le log) par une vue en direct de
qui active quoi ACTUELLEMENT dans le monde, utile aussi bien à un chasseur
(hunter) qu'à un activateur qui veut repérer les parcs déjà occupés à
proximité. Lecture seule : ce module ne poste jamais de spot (l'API publique
de soumission n'a pas de format d'authentification vérifié avec certitude à
la date d'écriture — mieux vaut ne rien implémenter que deviner et risquer un
spot mal formé sur un service public partagé).

Spots en direct, endpoint public sans clé : https://api.pota.app/spot/activator
Doc communautaire : https://docs.pota.app/

Base des parcs : https://pota.app/all_parks_ext.csv, l'export CSV complet
(~9 Mo, ~50 000 parcs) proposé en téléchargement direct par POTA lui-même
(lié depuis leur page « Park Search »). Comme pour SOTA (logx_sota.py), sert
à VALIDER une référence saisie (nom, localisation) et à la RECHERCHER par
code ou par nom — via le moteur générique logx_activation_db.py."""
import csv
import json
import time

from logx_activation_db import ActivationDatabase

POTA_SPOTS_URL = 'https://api.pota.app/spot/activator'
CACHE_TTL = 90  # secondes — assez réactif sans marteler l'API publique

_cache = {'data': None, 'ts': 0}


def fetch_pota_spots():
    """Spots activateurs POTA en direct, au format spot générique du logiciel
    (mêmes clés que les autres sources : call/freq/band/mode/info/time/...).
    Cache court ; en cas d'échec réseau, renvoie le dernier résultat connu
    plutôt qu'une liste vide (dégrade proprement, comme les autres sources)."""
    if _cache['data'] is not None and time.time() - _cache['ts'] < CACHE_TTL:
        return _cache['data']
    from logx_utils import fetch_url  # import local : mockable par les tests (monkeypatch sur logx_utils)
    raw = fetch_url(POTA_SPOTS_URL, timeout=10)
    if not raw:
        return _cache['data'] or []
    try:
        items = json.loads(raw)
    except (ValueError, TypeError):
        return _cache['data'] or []
    if not isinstance(items, list):
        return _cache['data'] or []

    from logx_scoring import _band_from_freq
    spots = []
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            freq_khz = float(it.get('frequency') or 0)
        except (TypeError, ValueError):
            freq_khz = 0
        spots.append({
            'call': str(it.get('activator', '')).upper(),
            'freq': freq_khz,  # kHz, cohérent avec les autres sources de spots
            'band': _band_from_freq(freq_khz),
            'mode': str(it.get('mode', '')).upper(),
            'reference': it.get('reference', ''),
            'park_name': it.get('name') or it.get('parkName') or '',
            'location': it.get('locationDesc', ''),
            'grid': it.get('grid6') or it.get('grid4') or '',
            'lat': it.get('latitude'),
            'lon': it.get('longitude'),
            'comment': it.get('comments', ''),
            'spotter': it.get('spotter', ''),
            'time': it.get('spotTime', ''),
            'count': it.get('count', 0),
            'source': 'pota',
        })
    _cache['data'] = spots
    _cache['ts'] = time.time()
    return spots


# ─── BASE DES PARCS ───────────────────────────────────────────────────────────

POTA_PARKS_URL = 'https://pota.app/all_parks_ext.csv'
PARKS_FILE = 'pota_parks.csv'


def _looks_valid_parks_csv(content):
    """Garde-fou avant d'écraser le cache : jamais un fichier tronqué ou une
    page d'erreur à la place du vrai export (~9 Mo, ~50 000 lignes)."""
    if not content or len(content) < 500_000:
        return False
    return content.count('"reference"') >= 1 and content.count(',') > 50_000


def _parse_parks_csv(content):
    """CSV -> liste de dicts. En-têtes réels (vérifiés en direct) :
    reference,name,active,entityId,locationDesc,latitude,longitude,grid."""
    reader = csv.DictReader(content.splitlines())
    out = []
    for row in reader:
        code = (row.get('reference') or '').strip().upper()
        if not code:
            continue
        try:
            lat = float(row.get('latitude') or '')
            lon = float(row.get('longitude') or '')
        except ValueError:
            lat = lon = None
        out.append({
            'code': code,
            'name': (row.get('name') or '').strip(),
            'location': (row.get('locationDesc') or '').strip(),
            'grid': (row.get('grid') or '').strip(),
            'active': (row.get('active') or '') == '1',
            'lat': lat,
            'lon': lon,
        })
    return out


parks_db = ActivationDatabase(
    label='POTA',
    source_url=POTA_PARKS_URL,
    cache_file=PARKS_FILE,
    parse_fn=_parse_parks_csv,
    valid_fn=_looks_valid_parks_csv,
    max_age_days=30,
    fetch_timeout=60,
)
