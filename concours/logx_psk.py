# -*- coding: utf-8 -*-
"""PSK Reporter / capteur d'ouverture de propagation.

pskreporter.info agrège en temps réel les décodages du monde entier (FT8,
FT4, PSK, JT...). En interrogeant l'API par indicatif, on obtient OÙ notre
signal a été entendu — une carte d'ouverture instantanée. Ce sont des
données de PROPAGATION, jamais du log de QSO : elles n'entrent ni dans le
scoring ni dans le log.

NB : PSK Reporter est alimenté par les modes NUMÉRIQUES. Pour voir sa
propagation pendant un concours CW/SSB, faire une brève émission FT8 de test
(ex. sur 14.074) ; la CW automatique se suit plutôt sur le Reverse Beacon
Network. Cache 3 min (l'API limite le débit — 503 sinon).
"""
import re
import time

from logx_utils import locator_to_latlon, haversine, bearing, cardinal

_cache = {}   # call -> {'ts', 'data'}
CACHE_S = 180


def heard_where(callsign, my_locator='', minutes=30):
    """Récepteurs ayant décodé `callsign` dans les N dernières minutes.
    Retourne {'ok', 'call', 'reports':[...], 'by_band':{...}, 'note'}."""
    call = (callsign or '').upper().strip()
    if not call:
        return {'ok': False, 'error': 'Indicatif station non configuré'}
    ck = f'{call}|{minutes}'
    hit = _cache.get(ck)
    if hit and time.time() - hit['ts'] < CACHE_S:
        return hit['data']

    from logx_utils import fetch_url
    url = (f'https://retrieve.pskreporter.info/query?senderCallsign={call}'
           f'&flowStartSeconds=-{int(minutes) * 60}&rronly=1')
    xml = fetch_url(url, timeout=25)
    if xml is None:
        return {'ok': False, 'error': 'PSK Reporter injoignable'}

    my_ll = locator_to_latlon(my_locator) if my_locator else (None, None)
    reports = []
    by_band = {}
    for attrs in re.findall(r'<receptionReport\s+([^>]+?)/?>', xml):
        d = dict(re.findall(r'(\w+)="([^"]*)"', attrs))
        rx_loc = d.get('receiverLocator', '')
        freq = d.get('frequency', '')
        try:
            mhz = int(freq) / 1e6
        except (ValueError, TypeError):
            mhz = 0
        band = _band_label(mhz)
        rx_ll = locator_to_latlon(rx_loc) if rx_loc else (None, None)
        dist = az = None
        if my_ll[0] is not None and rx_ll[0] is not None:
            dist = haversine(my_ll[0], my_ll[1], rx_ll[0], rx_ll[1])
            az = bearing(my_ll[0], my_ll[1], rx_ll[0], rx_ll[1])
        rep = {
            'rx_call': d.get('receiverCallsign', ''),
            'rx_locator': rx_loc,
            'band': band, 'freq_mhz': round(mhz, 3),
            'mode': d.get('mode', ''),
            'snr': d.get('sNR', ''),
            'dist_km': dist, 'bearing': az,
            'cardinal': cardinal(az) if az is not None else '',
            'lat': rx_ll[0], 'lon': rx_ll[1],
        }
        reports.append(rep)
        b = by_band.setdefault(band, {'count': 0, 'max_km': 0})
        b['count'] += 1
        if dist and dist > b['max_km']:
            b['max_km'] = dist
    # Plus lointains d'abord (les DX intéressent le plus)
    reports.sort(key=lambda r: -(r['dist_km'] or 0))
    data = {
        'ok': True, 'call': call, 'reports': reports[:80],
        'by_band': by_band, 'total': len(reports),
        'note': ('Aucun décodage récent — fais une brève émission numérique '
                 '(FT8 sur 14.074) pour tester ta propagation.') if not reports else '',
    }
    _cache[ck] = {'ts': time.time(), 'data': data}
    return data


def _band_label(mhz):
    for lo, hi, b in ((1.7, 2.1, '160m'), (3.4, 4.1, '80m'), (6.9, 7.4, '40m'),
                      (10.0, 10.2, '30m'), (13.9, 14.4, '20m'), (18.0, 18.2, '17m'),
                      (20.9, 21.5, '15m'), (24.8, 25.0, '12m'), (27.9, 29.8, '10m'),
                      (49, 55, '6m'), (69, 71, '4m'), (143, 149, '2m')):
        if lo <= mhz <= hi:
            return b
    return f'{mhz:.1f}MHz' if mhz else '?'
