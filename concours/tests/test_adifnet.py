# -*- coding: utf-8 -*-
"""Tests du réseau ADIF générique (logx_adifnet) : interopérabilité
UDP <contactinfo> avec N1MM Logger+ / DXLog.net (format de facto entre
loggers de concours tiers)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_adifnet as adifnet

N1MM_SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<contactinfo>
\t<app>N1MM</app>
\t<contestname>CWOPS</contestname>
\t<contestnr>73</contestnr>
\t<timestamp>2020-01-17 16:43:38</timestamp>
\t<mycall>W2XYZ</mycall>
\t<band>14</band>
\t<rxfreq>352519</rxfreq>
\t<txfreq>352519</txfreq>
\t<operator></operator>
\t<mode>CW</mode>
\t<call>W1AW</call>
\t<countryprefix>K</countryprefix>
\t<gridsquare>FN31</gridsquare>
\t<snt>599</snt>
\t<sntnr>5</sntnr>
\t<rcv>599</rcv>
\t<rcvnr>0</rcvnr>
\t<comment></comment>
</contactinfo>"""


# ─── réglages ─────────────────────────────────────────────────────────────
def test_settings_desactive_par_defaut():
    s = adifnet.adifnet_settings({})
    assert s['mode'] == 'off' and not s['listen'] and not s['send']
    assert s['port'] == 12060 and s['target'] == '255.255.255.255'


def test_settings_mode_invalide_retombe_sur_off():
    s = adifnet.adifnet_settings({'adifnet_mode': 'n_importe_quoi'})
    assert s['mode'] == 'off'


def test_settings_mode_both():
    s = adifnet.adifnet_settings({'adifnet_mode': 'both', 'adifnet_port': '12061',
                                   'adifnet_target': '192.168.1.50', 'adifnet_app_name': 'RCTest'})
    assert s['listen'] and s['send']
    assert s['port'] == 12061 and s['target'] == '192.168.1.50' and s['app_name'] == 'RCTest'


def test_settings_mode_listen_seul():
    s = adifnet.adifnet_settings({'adifnet_mode': 'listen'})
    assert s['listen'] and not s['send']


def test_settings_mode_send_seul():
    s = adifnet.adifnet_settings({'adifnet_mode': 'send'})
    assert not s['listen'] and s['send']


# ─── parsing (réception) ────────────────────────────────────────────────────
def test_parse_contactinfo_n1mm_reel():
    fields = adifnet.parse_contactinfo(N1MM_SAMPLE)
    assert fields['app'] == 'N1MM' and fields['call'] == 'W1AW'
    assert fields['band'] == '14' and fields['mode'] == 'CW'
    assert fields['gridsquare'] == 'FN31'
    assert fields['snt'] == '599' and fields['rcv'] == '599'


def test_parse_contactinfo_xml_invalide():
    assert adifnet.parse_contactinfo('pas du xml <<<') is None


def test_parse_contactinfo_racine_inattendue():
    assert adifnet.parse_contactinfo('<radioinfo><band>14</band></radioinfo>') is None


def test_qso_from_contactinfo():
    fields = adifnet.parse_contactinfo(N1MM_SAMPLE)
    q = adifnet.qso_from_contactinfo(fields, {'locator': 'JN15XC', 'contest': 'cq_ww_cw'})
    assert q['call'] == 'W1AW' and q['band'] == '14' and q['mode'] == 'CW'
    assert q['date'] == '20200117' and q['time'] == '16:43'
    assert q['rst_sent'] == '599' and q['rst_rcvd'] == '599'
    assert q['locator'] == 'FN31'
    assert q['dist'] > 4000        # distance transatlantique calculée
    # Le concours reste celui de CETTE instance, pas le contestname étranger
    assert q['contest'] == 'cq_ww_cw'
    assert q['source'] == 'adifnet:N1MM'


def test_qso_from_contactinfo_horodatage_absent_ne_plante_pas():
    q = adifnet.qso_from_contactinfo({'call': 'DL1AA', 'band': '7', 'mode': 'SSB'}, {})
    assert q['call'] == 'DL1AA' and q['date'] and q['time']


# ─── construction (émission) ─────────────────────────────────────────────────
def test_build_contactinfo_xml_round_trip():
    qso = {'call': 'F4GLD', 'band': '21', 'mode': 'SSB', 'date': '20260719',
           'time': '14:30', 'rst_sent': '59', 'rst_rcvd': '57', 'locator': 'JN18',
           'operator': 'Olivier'}
    cfg = {'adifnet_app_name': 'LogXAI', 'contest': 'cq_ww_ssb',
           'callsign_contest': 'F4GLD'}
    xml_text = adifnet.build_contactinfo_xml(qso, cfg)
    assert '<contactinfo>' in xml_text and xml_text.startswith('<?xml')
    fields = adifnet.parse_contactinfo(xml_text)
    assert fields['call'] == 'F4GLD' and fields['band'] == '21' and fields['mode'] == 'SSB'
    assert fields['app'] == 'LogXAI' and fields['mycall'] == 'F4GLD'
    assert fields['snt'] == '59' and fields['rcv'] == '57'
    assert fields['gridsquare'] == 'JN18'
    assert fields['timestamp'] == '2026-07-19 14:30:00'


def test_build_contactinfo_xml_echappe_les_caracteres_speciaux():
    qso = {'call': 'F4GLD', 'band': '14', 'mode': 'SSB', 'comment': 'R&S <test>'}
    xml_text = adifnet.build_contactinfo_xml(qso, {})
    fields = adifnet.parse_contactinfo(xml_text)
    assert fields['comment'] == 'R&S <test>'


def test_build_contactinfo_xml_resout_lid_de_creneau_en_indicatif_reel():
    """L'ID de créneau brut ('OP1') ne doit jamais partir en UDP vers un poste
    N1MM/DXLog voisin — celui-ci l'afficherait tel quel dans SA propre
    interface, exactement le même bug que LOGBOOK/export ADIF (signalement
    F4GLD 08/08/2026)."""
    qso = {'call': 'F4GLD', 'band': '14', 'mode': 'SSB', 'operator': 'OP1'}
    cfg = {'callsign_contest': 'F6KQJ', 'operators': [{'call': 'F1ABC'}]}
    xml_text = adifnet.build_contactinfo_xml(qso, cfg)
    fields = adifnet.parse_contactinfo(xml_text)
    assert fields['operator'] == 'F1ABC'
    assert 'OP1' not in xml_text


# ─── émission (broadcast_qso) ────────────────────────────────────────────────
def test_broadcast_qso_desactive_ne_transmet_rien(monkeypatch):
    monkeypatch.setattr(adifnet.socket, 'socket', lambda *a, **k: (_ for _ in ()).throw(AssertionError('ne doit pas etre appele')))
    r = adifnet.broadcast_qso({'call': 'F4GLD', 'band': '14', 'mode': 'SSB'}, {'adifnet_mode': 'off'})
    assert r is False


def test_broadcast_qso_envoie_au_bon_port_et_cible(monkeypatch):
    sent = {}

    class FakeSocket:
        def setsockopt(self, *a):
            pass

        def sendto(self, data, addr):
            sent['data'] = data
            sent['addr'] = addr

        def close(self):
            pass

    monkeypatch.setattr(adifnet.socket, 'socket', lambda *a, **k: FakeSocket())
    cfg = {'adifnet_mode': 'send', 'adifnet_port': '12060', 'adifnet_target': '192.168.1.255'}
    r = adifnet.broadcast_qso({'call': 'W1AW', 'band': '14', 'mode': 'CW'}, cfg)
    assert r is True
    assert sent['addr'] == ('192.168.1.255', 12060)
    assert b'<call>W1AW</call>' in sent['data']


def test_broadcast_qso_erreur_reseau_ne_leve_pas(monkeypatch):
    def boom(*a, **k):
        raise OSError('reseau indisponible')
    monkeypatch.setattr(adifnet.socket, 'socket', boom)
    r = adifnet.broadcast_qso({'call': 'F4GLD', 'band': '14', 'mode': 'SSB'},
                              {'adifnet_mode': 'send'})
    assert r is False


# ─── bande MHz -> code interne ────────────────────────────────────────────────
def test_band_from_field():
    assert adifnet._band_from_field('14') == '14'
    assert adifnet._band_from_field('3.5') == '3.5'
    assert adifnet._band_from_field('144') == '144'
    assert adifnet._band_from_field('') == ''
