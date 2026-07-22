# -*- coding: utf-8 -*-
"""WWFF (World Wide Flora & Fauna) — spots en direct + base des réserves.

Deux sources officielles, publiques, sans clé :
  - Spots en direct : spots.wwff.co/static/spots.json, documenté sur
    wwff.co/spotline/ (« Spotline » — le service officiel de spots WWFF,
    rafraîchissement conseillé toutes les 30s). NB : wwff.co/dx-cluster/ (page
    donnée par l'utilisateur) est une ancienne page morte — le vrai service a
    migré vers ce sous-domaine séparé.
  - Base des réserves : wwff.co/wwff-data/wwff_directory.csv, l'export CSV
    officiel complet (~24 Mo, ~68 000 références, toutes préfixes pays
    confondus, ex. FFF pour la France). Sert à VALIDER une référence saisie et
    à la RECHERCHER par code ou par nom, comme pour SOTA/POTA.
"""
import csv
import json
import time

from logx_activation_db import ActivationDatabase

WWFF_SPOTS_URL = 'https://spots.wwff.co/static/spots.json'
SPOTS_CACHE_TTL = 60  # secondes, conforme au rafraîchissement conseillé (30-60s)
_spots_cache = {'data': None, 'ts': 0}


# ─── SPOTS EN DIRECT ─────────────────────────────────────────────────────────

def fetch_wwff_spots():
    """Spots d'activateurs WWFF en direct, format générique du logiciel (mêmes
    clés que logx_pota.fetch_pota_spots / logx_sota.fetch_sota_spots). Cache
    court ; en cas d'échec réseau, renvoie le dernier résultat connu plutôt
    qu'une liste vide (dégrade proprement, comme les autres sources)."""
    if _spots_cache['data'] is not None and time.time() - _spots_cache['ts'] < SPOTS_CACHE_TTL:
        return _spots_cache['data']
    from logx_utils import fetch_url
    raw = fetch_url(WWFF_SPOTS_URL, timeout=10)
    if not raw:
        return _spots_cache['data'] or []
    try:
        items = json.loads(raw)
    except (ValueError, TypeError):
        return _spots_cache['data'] or []
    if not isinstance(items, list):
        return _spots_cache['data'] or []

    from logx_scoring import _band_from_freq
    spots = []
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            freq_khz = float(it.get('frequency_khz') or 0)  # déjà en kHz, cohérent avec les autres sources
        except (TypeError, ValueError):
            freq_khz = 0
        spots.append({
            'call': str(it.get('activator', '')).upper(),
            'freq': freq_khz,
            'band': _band_from_freq(freq_khz),
            'mode': str(it.get('mode', '')).upper(),
            'reference': it.get('reference', ''),
            'park_name': it.get('reference_name', ''),
            'lat': it.get('latitude'),
            'lon': it.get('longitude'),
            'comment': it.get('remarks', ''),
            'spotter': it.get('spotter', ''),
            'time': it.get('spot_time_formatted', ''),
            'source': 'wwff',
        })
    _spots_cache['data'] = spots
    _spots_cache['ts'] = time.time()
    return spots


# ─── BASE DES RÉSERVES ────────────────────────────────────────────────────────

WWFF_DIRECTORY_URL = 'https://wwff.co/wwff-data/wwff_directory.csv'
DIRECTORY_FILE = 'wwff_directory.csv'


def _looks_valid_directory_csv(content):
    """Garde-fou avant d'écraser le cache : jamais un fichier tronqué ou une
    page d'erreur à la place du vrai export (~24 Mo, ~68 000 lignes)."""
    if not content or len(content) < 5_000_000:
        return False
    return content.count('reference,status,name') >= 1 and content.count(',') > 500_000


def _parse_directory_csv(content):
    """CSV -> liste de dicts. En-têtes réels (vérifiés en direct) :
    reference,status,name,program,dxcc,state,county,continent,iota,
    iaruLocator,latitude,longitude,IUCNcat,validFrom,validTo,notes,..."""
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
            'region': (row.get('state') or '').strip(),
            'country': (row.get('country') or '').strip(),
            'continent': (row.get('continent') or '').strip(),
            'iota': (row.get('iota') or '').strip(),
            'status': (row.get('status') or '').strip(),
            'lat': lat,
            'lon': lon,
        })
    return out


directory_db = ActivationDatabase(
    label='WWFF',
    source_url=WWFF_DIRECTORY_URL,
    cache_file=DIRECTORY_FILE,
    parse_fn=_parse_directory_csv,
    valid_fn=_looks_valid_directory_csv,
    max_age_days=30,
    fetch_timeout=90,
)
