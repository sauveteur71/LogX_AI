# -*- coding: utf-8 -*-
"""Prévision troposphérique (ducting) — indice de réfractivité.

La propagation tropo VHF/UHF/SHF dépend du GRADIENT VERTICAL de l'indice de
réfraction radio N. Une inversion de température + humidité près du sol crée un
conduit (« ducting ») qui piège les ondes sur des centaines de km — le régal
des concours THF.

On interroge Open-Meteo aux niveaux de pression (1000/950/925/900 hPa),
on calcule N à chaque niveau puis le gradient dN/dh (N-unités/km) :

    N = 77.6·P/T + 3.73e5·e/T²   (P,e en hPa, T en K)

Seuils classiques (N-unités/km) :
    > 0        : sous-réfraction (dégradé)
    0 … -79    : réfraction normale
    -79 … -157 : SUPER-réfraction (tropo renforcé)
    < -157     : DUCTING (conduit, ouverture tropo)

Déterministe hormis l'appel météo ; cache 20 min ; dégrade sans réseau.
"""
import math
import time

_cache = {'ts': 0, 'data': None, 'key': ''}
CACHE_S = 1200

# Niveau de pression (hPa) → altitude approx (m), atmosphère standard.
LEVELS = [(1000, 110), (950, 540), (925, 760), (900, 990)]


def _sat_vapor_hpa(t_c):
    """Pression de vapeur saturante (hPa) — formule de Magnus."""
    return 6.112 * math.exp(17.62 * t_c / (243.12 + t_c))


def _refractivity(p_hpa, t_c, rh_pct):
    t_k = t_c + 273.15
    e = (max(0.0, min(100.0, rh_pct)) / 100.0) * _sat_vapor_hpa(t_c)
    return 77.6 * p_hpa / t_k + 3.73e5 * e / (t_k * t_k)


def _classify(gradient):
    if gradient is None:
        return 'inconnu', 0
    if gradient < -157:
        return 'ducting', 4          # conduit : ouverture tropo
    if gradient < -79:
        return 'super', 3            # super-réfraction
    if gradient <= 0:
        return 'normal', 1
    return 'sous', 0                 # sous-réfraction


LEVEL_TXT = {
    'ducting': ('🟢 DUCTING — conduit tropo, ouverture longue distance possible',
                'les bandes hautes (1296+ et micro-ondes) peuvent porter très loin'),
    'super':   ('🟡 Super-réfraction — tropo renforcé',
                'gains notables sur 144/432 et au-delà, tente les distances'),
    'normal':  ('Réfraction normale', 'propagation tropo standard'),
    'sous':    ('🔵 Sous-réfraction — tropo dégradé', 'portées réduites, reste local'),
    'inconnu': ('Prévision tropo indisponible', ''),
}


def tropo_forecast(lat, lon):
    """Indice de ducting au point (lat, lon) + tendance sur quelques heures.
    {'ok', 'level', 'score', 'gradient', 'inversion', 'title', 'advice',
     'trend'} ou {'ok': False, 'error'}."""
    if lat is None or lon is None:
        return {'ok': False, 'error': 'Locator station non défini'}
    key = f'{lat:.2f},{lon:.2f}'
    if _cache['data'] and _cache['key'] == key and time.time() - _cache['ts'] < CACHE_S:
        return _cache['data']

    from logx_utils import fetch_url
    import json
    fields = []
    for p, _ in LEVELS:
        fields.append(f'temperature_{p}hPa')
        fields.append(f'relative_humidity_{p}hPa')
    url = (f'https://api.open-meteo.com/v1/forecast?latitude={lat:.4f}'
           f'&longitude={lon:.4f}&hourly={",".join(fields)}&forecast_days=1')
    raw = fetch_url(url, timeout=15)
    if not raw:
        return _cache['data'] or {'ok': False, 'error': 'Météo injoignable'}
    try:
        hourly = json.loads(raw).get('hourly', {})
        n_hours = len(hourly.get('time', []))
        if not n_hours:
            return {'ok': False, 'error': 'Données tropo absentes'}

        import datetime
        idx = min(datetime.datetime.utcnow().hour, n_hours - 1)

        def grad_at(i):
            pts = []
            for p, h in LEVELS:
                t = hourly.get(f'temperature_{p}hPa', [])
                rh = hourly.get(f'relative_humidity_{p}hPa', [])
                if i < len(t) and i < len(rh) and t[i] is not None and rh[i] is not None:
                    pts.append((h, _refractivity(p, t[i], rh[i]), t[i]))
            if len(pts) < 2:
                return None, False
            (h0, n0, t0), (h1, n1, t1) = pts[0], pts[-1]
            gradient = (n1 - n0) / ((h1 - h0) / 1000.0)   # N-unités / km
            inversion = t1 > t0 + 0.3                      # T monte avec l'altitude
            return gradient, inversion

        gradient, inversion = grad_at(idx)
        level, score = _classify(gradient)

        # Tendance : meilleur niveau dans les 12 h à venir
        best = score
        best_h = 0
        for dh in range(1, 13):
            j = idx + dh
            g, _ = grad_at(j)
            _, s = _classify(g)
            if s > best:
                best, best_h = s, dh
        trend = ''
        if best > score and best_h:
            names = {4: 'ducting', 3: 'super-réfraction'}
            trend = f"amélioration vers {names.get(best,'tropo renforcé')} dans ~{best_h} h"

        title, advice = LEVEL_TXT.get(level, LEVEL_TXT['inconnu'])
        data = {
            'ok': True, 'level': level, 'score': score,
            'gradient': round(gradient) if gradient is not None else None,
            'inversion': inversion, 'title': title, 'advice': advice,
            'trend': trend,
        }
        _cache.update(ts=time.time(), data=data, key=key)
        return data
    except Exception as e:
        return _cache['data'] or {'ok': False, 'error': f'Tropo illisible ({e})'}
