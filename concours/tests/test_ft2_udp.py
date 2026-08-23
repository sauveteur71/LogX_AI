# -*- coding: utf-8 -*-
"""Terrain FT2 — Phase 2 : décodages/QSO reçus par UDP (Decodium, API WSJT-X).

Decodium émet ses décodages en UDP « type WSJT-X » (port 2237). Le handler
logx_wsjtx de LogX est AGNOSTIQUE AU MODE (il lit `mode` et le conserve tel
quel, sans allowlist) : les décodages et QSO FT2 passent donc DÉJÀ. Ce test le
prouve et le VERROUILLE (garde contre l'ajout futur d'un filtre de mode qui
casserait FT2). Aucune émission — réception seule.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_wsjtx as wsjtx
from test_wsjtx import _decode_datagram, _header, _qdatetime, _utf8


def test_decode_ft2_conserve_le_mode():
    data = _decode_datagram(mode='FT2', message='CQ F4ABC JN18', delta_hz=1500)
    m = wsjtx.parse_message(data)
    assert m['type'] == 'decode' and m['mode'] == 'FT2'


def test_variante_decodium_passe_aussi():
    # une variante (mode="FT2_DECODIUM") traverse le handler agnostique
    data = _decode_datagram(mode='FT2_DECODIUM', message='CQ F4ABC JN18')
    assert wsjtx.parse_message(data)['mode'] == 'FT2_DECODIUM'


def test_record_decode_ft2_alimente_le_cache():
    wsjtx._decodes.clear()
    wsjtx.status['dial_mhz'] = 14.08
    msg = wsjtx.parse_message(_decode_datagram(mode='FT2', message='CQ F4ABC JN18',
                                               delta_hz=1500))
    calls = wsjtx.record_decode(msg, my_call='F5XYZ')
    assert 'F4ABC' in calls
    e = next(d for d in wsjtx.recent_decodes() if d['call'] == 'F4ABC')
    assert e['mode'] == 'FT2'                       # mode FT2 conservé dans le cache


def test_qso_logged_ft2_conserve_le_mode():
    import datetime
    dt = datetime.datetime(2026, 8, 1, 12, 0, 0)
    data = (_header(5) + _qdatetime(dt) + _utf8('DL1ABC') + _utf8('JO31')
            + struct.pack('>Q', 14080000) + _utf8('FT2') + _utf8('-08')
            + _utf8('-12') + _utf8('30') + _utf8('') + _utf8('Hans') + _qdatetime(dt))
    m = wsjtx.parse_message(data)
    assert m['type'] == 'qso_logged' and m['mode'] == 'FT2'


def test_aucun_allowlist_de_mode_dans_le_handler():
    # garde structurel : le parse du Decode ne doit PAS filtrer par un ensemble
    # de modes connus (sinon FT2 serait rejeté). Le mode est lu et rendu tel quel.
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'logx_wsjtx.py'), encoding='utf-8').read()
    bloc = src[src.index("mtype == 2"):src.index("mtype == 5")]
    assert "'mode': mode" in bloc and 'in (' not in bloc.split('return')[0].split('mode = r.utf8()')[1]
