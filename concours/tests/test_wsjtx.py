# -*- coding: utf-8 -*-
"""Tests du pont WSJT-X : parsing des datagrammes UDP (protocole Qt QDataStream)."""
import os
import struct
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_wsjtx as wsjtx


def _utf8(s):
    if s is None:
        return struct.pack('>I', 0xFFFFFFFF)
    b = s.encode('utf-8')
    return struct.pack('>I', len(b)) + b


def _qdatetime(dt):
    """datetime UTC → sérialisation Qt (JDN i64 + ms u32 + timespec=1)."""
    a = (14 - dt.month) // 12
    y = dt.year + 4800 - a
    m = dt.month + 12 * a - 3
    jdn = (dt.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045)
    ms = (dt.hour * 3600 + dt.minute * 60 + dt.second) * 1000
    return struct.pack('>q', jdn) + struct.pack('>I', ms) + struct.pack('>B', 1)


def _header(mtype, wsjt_id='WSJT-X'):
    return (struct.pack('>I', wsjtx.MAGIC) + struct.pack('>I', 2) +
            struct.pack('>I', mtype) + _utf8(wsjt_id))


def test_parse_status():
    data = (_header(1) + struct.pack('>Q', 14074000) + _utf8('FT8') +
            _utf8('') + _utf8('') + _utf8('FT8'))
    m = wsjtx.parse_message(data)
    assert m['type'] == 'status' and m['dial_mhz'] == 14.074 and m['mode'] == 'FT8'


def test_parse_qso_logged():
    dt = datetime.datetime(2026, 8, 1, 13, 45, 30)
    data = (_header(5) + _qdatetime(dt) + _utf8('DL1ABC') + _utf8('JO31') +
            struct.pack('>Q', 14074000) + _utf8('FT8') + _utf8('-08') +
            _utf8('-12') + _utf8('30') + _utf8('') + _utf8('Hans') + _qdatetime(dt))
    m = wsjtx.parse_message(data)
    assert m['type'] == 'qso_logged'
    assert m['call'] == 'DL1ABC' and m['grid'] == 'JO31'
    assert m['dial_mhz'] == 14.074 and m['mode'] == 'FT8'
    assert m['rpt_sent'] == '-08' and m['rpt_recv'] == '-12'
    assert m['time_on'] == dt


def test_qso_from_logged_produit_un_qso_loggeable():
    dt = datetime.datetime(2026, 8, 1, 13, 45, 0)
    msg = {'type': 'qso_logged', 'call': 'w1aw', 'grid': 'FN31',
           'dial_mhz': 7.074, 'mode': 'FT4', 'rpt_sent': '+02',
           'rpt_recv': '-05', 'time_on': dt}
    q = wsjtx.qso_from_logged(msg, {'locator': 'JN15XC', 'contest': 'X', 'op_call': 'F4GLD'})
    assert q['call'] == 'W1AW' and q['band'] == '7' and q['mode'] == 'FT4'
    assert q['date'] == '20260801' and q['time'] == '13:45'
    assert q['locator'] == 'FN31' and q['source'] == 'wsjtx'
    assert q['dist'] > 4000        # distance transatlantique calculée


def test_bande_depuis_frequence():
    assert wsjtx._mhz_to_band(14.074) == '14'
    assert wsjtx._mhz_to_band(7.074) == '7'
    assert wsjtx._mhz_to_band(10.136) == '7'     # 30 m → segment 40 m interne
    assert wsjtx._mhz_to_band(50.313) == '50'
    assert wsjtx._mhz_to_band(144.174) == '144'


def test_magic_invalide_ignore():
    assert wsjtx.parse_message(b'\x00\x00\x00\x00' + b'x' * 20) is None
    assert wsjtx.parse_message(b'court') is None


def test_settings_desactive_par_defaut():
    assert wsjtx.wsjtx_settings({})['enabled'] is False
    s = wsjtx.wsjtx_settings({'wsjtx_enabled': True, 'wsjtx_port': '2237'})
    assert s == {'enabled': True, 'port': 2237}
