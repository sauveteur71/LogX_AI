# -*- coding: utf-8 -*-
"""Spots d'activateurs POTA (Parks On The Air) en direct — api.pota.app.

Complète le mode Activation (logx_activation.py, purement local/déterministe :
validation de référence + progression depuis le log) par une vue en direct de
qui active quoi ACTUELLEMENT dans le monde, utile aussi bien à un chasseur
(hunter) qu'à un activateur qui veut repérer les parcs déjà occupés à
proximité. Lecture seule : ce module ne poste jamais de spot (l'API publique
de soumission n'a pas de format d'authentification vérifié avec certitude à
la date d'écriture — mieux vaut ne rien implémenter que deviner et risquer un
spot mal formé sur un service public partagé).

Endpoint public, sans clé : https://api.pota.app/spot/activator
Doc communautaire : https://docs.pota.app/
"""
import json
import time

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
