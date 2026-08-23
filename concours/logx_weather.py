# -*- coding: utf-8 -*-
"""Météo locale du point haut — Open-Meteo (gratuit, sans clé API).

Pour la sécurité du matériel portable en /P (vent et rafales sur les
antennes, pluie, gel). Coordonnées dérivées du locator courant. Cache 10 min.
Dégrade proprement sans réseau (retourne le dernier cache ou une erreur).
"""
import threading
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

    from logx_utils import fetch_url
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
        # Température : distinguer « absente/null » de « 0 °C réel ». Le repli à
        # 0 de num() convient au vent/rafales/précip mais déclencherait une
        # fausse alerte GEL (temp <= 0) dès qu'open-meteo n'envoie pas de
        # température. None quand absente/null.
        _t = cur.get('temperature_2m')
        temp = _t if isinstance(_t, (int, float)) else None
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
        if temp is not None and temp <= 0:
            warns.append('❄️ Gel — attention au givre sur les éléments')
        # `storm` : l'orage ISOLÉ du reste, en booléen. La pastille de foudre de
        # la barre de statut (logx_statusbar.js) en a besoin seule — `warn`
        # agrège orage + rafales + gel dans une phrase FRANÇAISE, et un client
        # qui y chercherait le mot « ORAGE » se casserait au premier
        # reformulage ou dans une interface traduite.
        data = {'ok': True, 'temp': round(temp) if temp is not None else None, 'wind': round(wind),
                'gust': round(gust), 'precip': precip, 'desc': desc,
                'icon': icon, 'warn': ' · '.join(warns),
                'storm': code in (95, 96, 99)}
        _cache.update(ts=time.time(), data=data, key=key)
        return data
    except Exception as e:
        return _cache['data'] or {'ok': False, 'error': f'Météo illisible ({e})'}


# ─── Accès NON BLOQUANT au cache (pour les handlers HTTP) ────────────────────
# get_weather() ci-dessus fait un appel réseau synchrone (jusqu'à ~18 s, cf.
# fetch_url) dès que le cache de 10 min expire — appelée en direct depuis un
# handler HTTP, elle gèlerait la connexion du client (ex. l'écran mural,
# pollé en continu) jusqu'à ~18 s toutes les 10 min si open-meteo.com est lent
# ou injoignable. Même remède que get_solar_cached()/get_muf_cached()
# (logx_clusters.py) : ne lire QUE le cache existant ici, rafraîchissement
# réseau déclenché dans un thread de fond détaché.
_weather_refresh_lock = threading.Lock()


def _refresh_weather_async(lat, lon):
    if not _weather_refresh_lock.acquire(blocking=False):
        return  # un rafraîchissement est déjà en vol
    def _run():
        try:
            get_weather(lat, lon)
        finally:
            _weather_refresh_lock.release()
    threading.Thread(target=_run, daemon=True).start()


def get_weather_cached(lat, lon):
    """Jamais bloquant — à utiliser depuis les handlers HTTP à la place de
    get_weather() (réservée aux appels de fond/tests). Ne renvoie le dernier
    cache que s'il correspond au MÊME point (lat/lon) : servir la météo d'un
    ancien QTH sous prétexte qu'elle est "en cache" serait trompeur pour la
    sécurité antenne après un changement de locator."""
    if lat is None or lon is None:
        return {'ok': False, 'error': 'Locator station non défini'}
    key = f'{lat:.2f},{lon:.2f}'
    same_point = bool(_cache['data']) and _cache['key'] == key
    stale = not same_point or time.time() - _cache['ts'] >= CACHE_S
    if stale:
        _refresh_weather_async(lat, lon)
    if not same_point:
        return {'ok': False, 'error': 'Météo en cours de récupération…', 'stale': True}
    data = dict(_cache['data'])
    data['stale'] = stale
    return data
