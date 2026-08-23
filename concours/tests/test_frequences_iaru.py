# -*- coding: utf-8 -*-
"""Base de fréquences IARU R1 + accès dial_freq (logx_frequences) — chantier auto-QSY."""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_frequences as fr   # noqa: E402


def test_db_bien_formee():
    with open(os.path.join(BASE, 'logx_rigs', 'frequences_iaru_r1.json'), encoding='utf-8') as f:
        d = json.load(f)
    entries = d['frequences']
    assert entries and d['count'] == len(entries)
    for e in entries:
        for champ in ('region', 'band', 'mode', 'dial_mhz', 'radio_mode',
                      'frequency_kind', 'status', 'verified_on'):
            assert champ in e, (champ, e)
        assert isinstance(e['dial_mhz'], (int, float)) and e['dial_mhz'] > 0


def test_dial_freq_ft8_valeurs_sourcees():
    assert fr.dial_freq('20m', 'FT8') == 14.074
    assert fr.dial_freq('40m', 'FT8') == 7.074
    assert fr.dial_freq('6m', 'FT8') == 50.313                       # continental (principal)
    assert fr.dial_freq('6m', 'FT8', variant='DX_intercontinental') == 50.323
    assert fr.dial_freq('30m', 'FT4') == 10.140


def test_dial_freq_absent_rend_none():
    assert fr.dial_freq('2m', 'FT4') is None        # 'local' -> non renseigné
    assert fr.dial_freq('20m', 'MODE_BIDON') is None


def test_modes_de_bande():
    m = fr.modes_de_bande('20m')
    assert 'FT8' in m and 'FT4' in m and 'WSPR' in m


def test_bandplan_bien_forme():
    bp = json.load(open(os.path.join(BASE, 'logx_rigs', 'bandplan_iaru_r1.json'), encoding='utf-8'))
    assert bp['inventaire'] and bp['hf_segments'] and bp['vhf_uhf_categories']
    for e in bp['inventaire']:
        assert e['start_mhz'] < e['end_mhz'], e
    for s in bp['hf_segments']:
        assert s['start_khz'] < s['end_khz'], s


def test_band_range():
    assert fr.band_range('20m') == (14.0, 14.35)
    assert fr.band_range('2m') == (144.0, 146.0)
    assert fr.band_range('bidon') is None


def test_digital_table():
    t = fr.digital_table()
    assert '20m' in t['bands'] and 'FT8' in t['modes']
    assert t['table']['20m']['FT8']['dial_mhz'] == 14.074
    assert t['table']['20m']['FT8']['radio_mode'] == 'USB-DATA'
    # 2m FT4 = 'local' -> absent de la table
    assert 'FT4' not in t['table'].get('2m', {})


def test_segment_for_freq():
    # 14074 kHz (FT8) tombe dans le segment numérique étroit 14070-14089
    s = fr.segment_for(14074, '20m')
    assert s and s['start_khz'] == 14070 and s['max_width_hz'] == 500
    # 14200 kHz -> segment SSB 14112-14350
    assert fr.segment_for(14200, '20m')['start_khz'] == 14112
    # hors de tout segment HF référencé
    assert fr.segment_for(99999) is None
