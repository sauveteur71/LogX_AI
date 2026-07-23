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
    assert wsjtx._mhz_to_band(10.136) == '10.1'  # 30 m → bande WARC propre (plus rabattue sur 40 m)
    assert wsjtx._mhz_to_band(18.100) == '18'    # 17 m
    assert wsjtx._mhz_to_band(24.915) == '24'    # 12 m
    assert wsjtx._mhz_to_band(50.313) == '50'
    assert wsjtx._mhz_to_band(144.174) == '144'


def test_magic_invalide_ignore():
    assert wsjtx.parse_message(b'\x00\x00\x00\x00' + b'x' * 20) is None
    assert wsjtx.parse_message(b'court') is None


def test_settings_desactive_par_defaut():
    assert wsjtx.wsjtx_settings({})['enabled'] is False
    s = wsjtx.wsjtx_settings({'wsjtx_enabled': True, 'wsjtx_port': '2237'})
    assert s == {'enabled': True, 'port': 2237}


# ─── DECODE (type 2) : alerte « DXCC/département manquant » façon GridTracker ─

def _decode_datagram(mode='FT8', message='CQ F4ABC JN18', snr=-10,
                     delta_time=0.2, delta_hz=1500, new=1):
    return (_header(2) + struct.pack('>B', new) + struct.pack('>I', 0) +
            struct.pack('>i', snr) + struct.pack('>d', delta_time) +
            struct.pack('>I', delta_hz) + _utf8(mode) + _utf8(message) +
            struct.pack('>B', 0) + struct.pack('>B', 0))


def test_parse_decode():
    data = _decode_datagram(message='CQ F4ABC JN18', delta_hz=1500)
    m = wsjtx.parse_message(data)
    assert m['type'] == 'decode' and m['mode'] == 'FT8'
    assert m['message'] == 'CQ F4ABC JN18' and m['delta_hz'] == 1500


def test_extract_calls_cq():
    assert wsjtx.extract_calls('CQ F4ABC JN18') == ['F4ABC']


def test_extract_calls_cq_avec_qualificatif():
    # "CQ DX"/"CQ POTA"/"CQ TEST"... : le qualificatif ne doit pas être pris
    # pour un indicatif, ni la grille Maidenhead qui suit.
    assert wsjtx.extract_calls('CQ POTA F4ABC/P JN18') == ['F4ABC/P']
    assert wsjtx.extract_calls('CQ DX F4ABC JN18') == ['F4ABC']


def test_extract_calls_echange_exclut_mon_indicatif():
    # Échange standard "appelant appelé rapport" : mon propre indicatif (celui
    # auquel je réponds) ne doit JAMAIS remonter comme "station entendue".
    assert wsjtx.extract_calls('F4ABC F5XYZ +05', my_call='F5XYZ') == ['F4ABC']
    assert wsjtx.extract_calls('F4ABC F5XYZ RR73', my_call='F5XYZ') == ['F4ABC']


def test_extract_calls_grille_6_caracteres_pas_confondue():
    # JN18AA (grille 6 caractères) a la même forme lettre+digit+lettre que
    # certains indicatifs — ne doit jamais être pris pour un indicatif.
    assert wsjtx.extract_calls('CQ F4ABC JN18AA') == ['F4ABC']


def test_extract_calls_rien_a_signaler():
    assert wsjtx.extract_calls('TU 73') == []
    assert wsjtx.extract_calls('') == []


def test_my_call_utilise_indicatif_concours_puis_repli():
    assert wsjtx._my_call({'callsign_contest': 'F4GLD/P', 'callsign': 'F4GLD'}) == 'F4GLD/P'
    assert wsjtx._my_call({'callsign': 'F4GLD'}) == 'F4GLD'
    assert wsjtx._my_call({}) == ''


def test_record_decode_alimente_recent_decodes():
    wsjtx._decodes.clear()
    wsjtx.status['dial_mhz'] = 14.074
    msg = {'mode': 'FT8', 'message': 'CQ F4ABC JN18', 'delta_hz': 1500}
    calls = wsjtx.record_decode(msg, my_call='F5XYZ')
    assert calls == ['F4ABC']
    decodes = wsjtx.recent_decodes()
    assert len(decodes) == 1
    d = decodes[0]
    assert d['call'] == 'F4ABC' and d['mode'] == 'FT8' and d['band'] == '14'
    assert d['freq_mhz'] == 14.0755   # dial + 1500 Hz de décalage audio


def test_record_decode_purge_les_entrees_expirees():
    wsjtx._decodes.clear()
    wsjtx.status['dial_mhz'] = 14.074
    wsjtx._decodes['OLD1CALL'] = {'band': '14', 'freq_mhz': 14.07, 'mode': 'FT8',
                                  'last_seen': 0.0}   # très ancien (epoch)
    wsjtx.record_decode({'mode': 'FT8', 'message': 'CQ F4ABC JN18', 'delta_hz': 0})
    calls = {d['call'] for d in wsjtx.recent_decodes()}
    assert 'F4ABC' in calls
    assert 'OLD1CALL' not in calls


def test_record_decode_sans_indicatif_ne_change_rien():
    wsjtx._decodes.clear()
    assert wsjtx.record_decode({'mode': 'FT8', 'message': 'TU 73'}) == []
    assert wsjtx.recent_decodes() == []


# ─── Revue adversariale du commit 75034bd : PRÉFIXE/INDICATIF, échange tiers,
#     purge de recent_decodes() ────────────────────────────────────────────

def test_extract_calls_prefixe_dxcc_slash_indicatif():
    # Format DXpedition le plus courant : PRÉFIXE/INDICATIF (ex. PJ4/K1ABC
    # depuis Bonaire, 9A/OK1ABC depuis la Croatie). AVANT le fix, _CALL_RE ne
    # reconnaissait que le format inverse INDICATIF/SUFFIXE (/P, /QRP...) et
    # ratait 100% de ces indicatifs : extract_calls('CQ PJ4/K1ABC FK52')
    # renvoyait [].
    assert wsjtx.extract_calls('CQ PJ4/K1ABC FK52') == ['PJ4/K1ABC']
    assert wsjtx.extract_calls('CQ 9A/OK1ABC JN95') == ['9A/OK1ABC']


def test_extract_calls_prefixe_dxcc_distingue_du_suffixe_portable():
    # Le format INDICATIF/SUFFIXE déjà géré (/P, /QRP, /M, changement de zone
    # /4...) ne doit pas être cassé par le support du nouveau format inverse.
    assert wsjtx.extract_calls('CQ F4ABC/P JN18') == ['F4ABC/P']
    assert wsjtx.extract_calls('CQ F4ABC/QRP JN18') == ['F4ABC/QRP']
    assert wsjtx.extract_calls('CQ F4ABC/4 JN18') == ['F4ABC/4']


def test_extract_calls_prefixe_dxcc_exclut_mon_indicatif_compose():
    # Mon propre indicatif composé (que je sois DXpéditionnaire ou que
    # my_call ne porte que la partie "cœur") ne doit jamais remonter comme
    # "station entendue".
    assert wsjtx.extract_calls('CQ PJ4/K1ABC FK52', my_call='PJ4/K1ABC') == []
    assert wsjtx.extract_calls('CQ PJ4/K1ABC FK52', my_call='K1ABC') == []


def test_extract_calls_echange_tiers_ne_garde_que_lemetteur():
    # Grammaire FT8 standard : "<destinataire> <émetteur> <rapport>". Quand
    # aucun des deux indicatifs n'est le mien (échange entre deux tiers
    # observé passivement), seul le SECOND a réellement émis CE décodage —
    # AVANT le fix, les DEUX étaient marqués "entendus".
    assert wsjtx.extract_calls('F4ABC F5XYZ +05', my_call='F9ZZZ') == ['F5XYZ']
    assert wsjtx.extract_calls('F4ABC F5XYZ RR73') == ['F5XYZ']
    # Compound call côté émetteur ou destinataire : même règle.
    assert wsjtx.extract_calls('PJ4/K1ABC F5XYZ +05', my_call='F9ZZZ') == ['F5XYZ']


def test_record_decode_echange_tiers_ne_marque_que_lemetteur():
    wsjtx._decodes.clear()
    wsjtx.status['dial_mhz'] = 14.074
    msg = {'mode': 'FT8', 'message': 'F4ABC F5XYZ +05', 'delta_hz': 0}
    calls = wsjtx.record_decode(msg, my_call='F9ZZZ')
    assert calls == ['F5XYZ']
    decoded_calls = {d['call'] for d in wsjtx.recent_decodes()}
    assert decoded_calls == {'F5XYZ'}
    assert 'F4ABC' not in decoded_calls


def test_recent_decodes_purge_les_entrees_expirees_sans_nouveau_decode():
    # AVANT le fix, seule record_decode() purgeait _decodes : sans nouveau
    # décodage pour la déclencher, une entrée expirée restait dans le cache
    # (invisible côté vue retournée, mais jamais libérée) indéfiniment.
    import time
    wsjtx._decodes.clear()
    wsjtx._decodes['OLD1CALL'] = {'band': '14', 'freq_mhz': 14.07, 'mode': 'FT8',
                                  'last_seen': 0.0}   # très ancien (epoch)
    wsjtx._decodes['NEW1CALL'] = {'band': '14', 'freq_mhz': 14.07, 'mode': 'FT8',
                                  'last_seen': time.time()}
    result = wsjtx.recent_decodes()
    assert {d['call'] for d in result} == {'NEW1CALL'}
    # Le cache lui-même doit avoir été purgé, pas seulement la vue retournée.
    assert 'OLD1CALL' not in wsjtx._decodes
    assert 'NEW1CALL' in wsjtx._decodes
