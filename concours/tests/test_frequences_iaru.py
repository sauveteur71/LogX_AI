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
