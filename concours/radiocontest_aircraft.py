# -*- coding: utf-8 -*-
"""Diffusion par avion (aircraft scatter) — aide THF/VHF.

Un avion à ~10 km d'altitude réfléchit les signaux VHF/UHF/SHF : deux stations
qui pointent leurs antennes vers le MÊME avion peuvent établir un contact bien
au-delà de l'horizon, surtout en hyperfréquences (1296 MHz → 47 GHz) où c'est
une technique de concours reconnue (CDF THF, Bol d'Or).

Ce module fait la GÉOMÉTRIE (déterministe, testable) :
  - à partir de ma position, d'une direction DX (cap ou locator du DX) et des
    avions ADS-B environnants, il trouve ceux bien placés (dans l'axe DX, à
    portée de réflexion) et calcule le CAP D'ANTENNE vers l'avion + une note.

La récupération ADS-B (réseau) est faite par le serveur/endpoint ; ici on ne
manipule que des listes de dicts {lat, lon, alt_m, callsign, track}.
"""
import math
import time

from radiocontest_utils import haversine, bearing, cardinal, locator_to_latlon

# Portée utile d'un avion réflecteur (km) : au-delà l'avion est trop bas sur
# l'horizon pour être vu. ~10 km d'altitude → horizon radio ~400 km.
MAX_RANGE_KM = 420
MIN_ALT_M = 3000        # sous 3 km, réflexion peu utile
# Tolérance d'azimut (°) entre le cap vers l'avion et le cap vers le DX.
AZIMUTH_TOL = 30


def _ang_diff(a, b):
    d = abs((a - b) % 360)
    return min(d, 360 - d)


def scatter_candidates(my_lat, my_lon, planes, dx_bearing=None,
                       dx_locator='', max_range_km=MAX_RANGE_KM, limit=8):
    """Avions bien placés pour une réflexion vers le DX.

    my_lat/my_lon : ma position. planes : [{lat, lon, alt_m, callsign?, track?}].
    dx_bearing : cap vers le DX (°) OU dx_locator : locator du DX (on en dérive
    le cap). Si aucun n'est fourni, on renvoie simplement les avions à portée,
    triés par proximité (utile en veille).

    Retourne [{callsign, distance_km, bearing, cardinal, alt_m, off_axis,
    score, reason}] trié par score décroissant."""
    if my_lat is None or my_lon is None:
        return []
    if dx_bearing is None and dx_locator:
        dlat, dlon = locator_to_latlon((dx_locator.upper() + 'MM')[:6])
        if dlat is not None:
            dx_bearing = bearing(my_lat, my_lon, dlat, dlon)

    out = []
    for p in planes or []:
        lat, lon = p.get('lat'), p.get('lon')
        if lat is None or lon is None:
            continue
        alt = p.get('alt_m') or 0
        if alt and alt < MIN_ALT_M:
            continue
        dist = haversine(my_lat, my_lon, lat, lon)
        if dist > max_range_km or dist < 20:
            continue
        az = bearing(my_lat, my_lon, lat, lon)
        off = _ang_diff(az, dx_bearing) if dx_bearing is not None else 0

        # Score : dans l'axe DX (off faible) + altitude élevée + distance moyenne
        # (un avion trop proche a un angle d'élévation trop fort).
        if dx_bearing is not None and off > AZIMUTH_TOL:
            continue
        axis_score = max(0, 1 - off / AZIMUTH_TOL) if dx_bearing is not None else 0.5
        alt_score = min(1.0, alt / 11000.0) if alt else 0.4
        dist_score = 1 - abs(dist - 220) / 260.0     # optimum ~200-250 km
        dist_score = max(0, min(1, dist_score))
        score = round(100 * (0.5 * axis_score + 0.25 * alt_score + 0.25 * dist_score))

        reason = f"cap {az}° {cardinal(az)}, {dist} km"
        if alt:
            reason += f", {round(alt/1000,1)} km alt"
        if dx_bearing is not None:
            reason += f", {round(off)}° hors axe DX" if off > 3 else ", DANS l'axe DX"

        out.append({
            'callsign': (p.get('callsign') or p.get('hex') or '?').strip(),
            'distance_km': dist, 'bearing': az, 'cardinal': cardinal(az),
            'alt_m': int(alt), 'off_axis': round(off), 'score': score,
            'reason': reason,
        })
    out.sort(key=lambda x: -x['score'])
    return out[:limit]


_planes_cache = {'ts': 0, 'data': None, 'key': ''}
_PLANES_TTL = 20      # les avions bougent vite : cache court


def fetch_planes(my_lat, my_lon, radius_km=250):
    """Avions ADS-B autour de la station (source gratuite adsb.lol, sans clé).
    Retourne [{lat, lon, alt_m, callsign, track}] ou [] si indisponible."""
    if my_lat is None or my_lon is None:
        return []
    key = f'{my_lat:.2f},{my_lon:.2f}'
    if (_planes_cache['data'] is not None and _planes_cache['key'] == key
            and time.time() - _planes_cache['ts'] < _PLANES_TTL):
        return _planes_cache['data']
    nm = int(min(250, radius_km / 1.852))
    url = f'https://api.adsb.lol/v2/lat/{my_lat:.4f}/lon/{my_lon:.4f}/dist/{nm}'
    try:
        from radiocontest_utils import fetch_url
        import json
        raw = fetch_url(url, timeout=12)
        ac = (json.loads(raw).get('ac', []) if raw else []) or []
    except Exception:
        return _planes_cache['data'] or []
    planes = []
    for a in ac:
        lat, lon = a.get('lat'), a.get('lon')
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        alt = a.get('alt_baro')
        alt_m = int(alt * 0.3048) if isinstance(alt, (int, float)) else 0
        planes.append({
            'lat': lat, 'lon': lon, 'alt_m': alt_m,
            'callsign': (a.get('flight') or a.get('hex') or '?').strip(),
            'track': a.get('track'),
        })
    _planes_cache.update(ts=time.time(), data=planes, key=key)
    return planes


def summarize(candidates, dx_bearing=None):
    """Résumé pour le coach / le panneau : meilleur avion + conseil."""
    if not candidates:
        return {'available': False,
                'text': "Aucun avion bien placé pour une diffusion vers le DX."}
    best = candidates[0]
    txt = (f"✈ {best['callsign']} à {best['distance_km']} km — pointe l'antenne au "
           f"cap {best['bearing']}° ({best['cardinal']})")
    if best['score'] >= 60:
        txt += " : réflexion possible MAINTENANT."
    else:
        txt += " (position moyenne)."
    return {'available': True, 'best': best, 'count': len(candidates), 'text': txt}
