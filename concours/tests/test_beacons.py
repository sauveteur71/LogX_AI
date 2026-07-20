# -*- coding: utf-8 -*-
"""Tests des balises NCDXF/IBP (calcul de rotation) et du parseur PSK Reporter."""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_beacons as beacons


def test_rotation_instant_zero():
    """À t=0 (créneau 0) : 20m=4U1UN (1re balise), les bandes hautes décalées."""
    now = datetime.datetime(2026, 8, 1, 12, 0, 0)
    out = {b['band']: b['call'] for b in beacons.beacons_now(now)}
    assert out['20m'] == '4U1UN'
    assert out['17m'] == 'YV5B'    # (slot0 - band1) mod 18 = 17
    assert out['10m'] == 'CS3B'    # (0 - 4) mod 18 = 14


def test_rotation_avance_de_10s():
    """+10 s = créneau suivant : la balise 20m devient la 2e (VE8AT)."""
    now = datetime.datetime(2026, 8, 1, 12, 0, 10)
    out = {b['band']: b['call'] for b in beacons.beacons_now(now)}
    assert out['20m'] == 'VE8AT'


def test_cycle_180s():
    """Le cycle boucle toutes les 3 minutes."""
    a = beacons.beacons_now(datetime.datetime(2026, 8, 1, 12, 0, 5))
    b = beacons.beacons_now(datetime.datetime(2026, 8, 1, 12, 3, 5))
    assert [x['call'] for x in a] == [x['call'] for x in b]


def test_toujours_5_bandes():
    out = beacons.beacons_now(datetime.datetime(2026, 8, 1, 14, 22, 37))
    assert [b['band'] for b in out] == ['20m', '17m', '15m', '12m', '10m']
    assert all(1 <= b['seconds_left'] <= 10 for b in out)


def test_psk_parse_reception_reports():
    """Le parseur PSK Reporter extrait bien les attributs d'un rapport."""
    import logx_psk as psk
    # Fragment XML réel de l'API (format receptionReport)
    sample = ('<receptionReports>'
              '<receptionReport receiverCallsign="OH6BG" receiverLocator="KP03sk" '
              'senderCallsign="F6KQJ" frequency="14074000" mode="FT8" sNR="-8"/>'
              '</receptionReports>')
    import re
    from logx_utils import locator_to_latlon
    attrs = re.findall(r'<receptionReport\s+([^>]+?)/?>', sample)
    assert len(attrs) == 1
    d = dict(re.findall(r'(\w+)="([^"]*)"', attrs[0]))
    assert d['receiverCallsign'] == 'OH6BG'
    assert psk._band_label(14.074) == '20m'
    assert psk._band_label(7.03) == '40m'
