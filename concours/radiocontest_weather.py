# -*- coding: utf-8 -*-
"""Météo locale du point haut — Open-Meteo (gratuit, sans clé API).

Pour la sécurité du matériel portable en /P (vent et rafales sur les
antennes, pluie, gel). Coordonnées dérivées du locator courant. Cache 10 min.
Dégrade proprement sans réseau (retourne le dernier cache ou une erreur).
"""
import time

_cache = {'ts': 0, 'data': None, 'key': ''}
CACHE_S = 600

# Codes météo WMO → libellé + emoji
WMO = {
    0: ('Ciel clair', '☀️'), 1: ('Peu nuageux', '🌤️'), 2: ('Partiellement nuageux', '⛅'),
    3: ('Couvert', '☁️'), 45: ('Brouillard', '🌫️'), 48: ('Brouillard givrant', '🌫️'),
    51: ('Bruine légère', '🌦️'), 53: ('Bruine', '🌦️'), 55: ('Bruine dense', '🌧️'),
    56: ('Bruine verglaçante', '🌧️'), 57: ('Bruine verglaçante dense', '🌧️'),
    61: ('Pluie faible', '🌦️'), 63: ('Pluie', '🌧️'), 65: ('Forte pluie', '🌧️'),
    66: ('Pluie verglaçante', '🌧️'), 67: ('Pluie verglaçante forte', '🌧️'),
    71: ('Neige faible', '🌨️'), 73: ('Neige', '🌨️'), 75: ('Forte neige', '❄️'),
    77: ('Grésil', '🌨️'),
    80: ('Averses', '🌦️'), 81: ('Averses', '🌧️'), 82: ('Fortes averses', '⛈️'),
    85: ('Averses de neige', '🌨️'), 86: ('Fortes averses de neige', '❄️'),
    95: ('Orage', '⛈️'), 96: ('Orage + grêle', '⛈️'), 99: ('Violent orage', '⛈️'),
}


def get_weather(lat, lon):
    """Météo courante au point (lat, lon). {'ok', 'temp', 'wind', 'gust',
    'precip', 'desc', 'icon', 'warn'} — warn si conditions à risque matériel."""
    if lat is None or lon is None:
        return {'ok': False, 'error': 'Locator station non défini'}
    key = f'{lat:.2f},{lon:.2f}'
    if _cache['data'] and _cache['key'] == key and time.time() - _cache['ts'] < CACHE_S:
        return _cache['data']

    from radiocontest_utils import fetch_url
    import json
    url = (f'https://api.open-meteo.com/v1/forecast?latitude={lat:.4f}'
           f'&longitude={lon:.4f}&current=temperature_2m,wind_speed_10m,'
           f'wind_gusts_10m,precipitation,weather_code&wind_speed_unit=kmh')
    raw = fetch_url(url, timeout=15)
    if not raw:
        return _cache['data'] or {'ok': False, 'error': 'Météo injoignable'}
    try:
        cur = json.loads(raw).get('current', {})
        # `.get(x, 0)` ne protège PAS d'une valeur présente mais null → `or 0`
        def num(field):
            v = cur.get(field)
            return v if isinstance(v, (int, float)) else 0
        code = int(num('weather_code'))
        desc, icon = WMO.get(code, ('—', '🌡️'))
        gust = num('wind_gusts_10m')
        wind = num('wind_speed_10m')
        precip = num('precipitation')
        temp = num('temperature_2m')
        # Alerte matériel — TOUTES les conditions à risque cumulées (l'orage,
        # danger foudre, ne doit jamais être masqué par une simple rafale).
        warns = []
        if code in (95, 96, 99):
            warns.append('⚠️ ORAGE — débranche les antennes' +
                         (f' (rafales {gust:.0f} km/h)' if gust >= 40 else ''))
        if gust >= 60:
            warns.append(f'⚠️ RAFALES {gust:.0f} km/h — sécurise les antennes')
        elif gust >= 40 and code not in (95, 96, 99):
            warns.append(f'⚠️ Rafales {gust:.0f} km/h — surveille le pylône')
        if temp <= 0:
            warns.append('❄️ Gel — attention au givre sur les éléments')
        data = {'ok': True, 'temp': round(temp), 'wind': round(wind),
                'gust': round(gust), 'precip': precip, 'desc': desc,
                'icon': icon, 'warn': ' · '.join(warns)}
        _cache.update(ts=time.time(), data=data, key=key)
        return data
    except Exception as e:
        return _cache['data'] or {'ok': False, 'error': f'Météo illisible ({e})'}
