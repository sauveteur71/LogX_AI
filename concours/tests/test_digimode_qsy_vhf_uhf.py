# -*- coding: utf-8 -*-
"""QSY numérique VHF/UHF (F4GLD 23/08) : presets 50.600 / 70.270 / 144.600 /
144.800 ajoutés à la table digimode. Valeurs SOURCÉES (plan VHF IARU R1 + plan
REF 70 MHz + RSGB). Presets = QSY manuel uniquement (le bouton n'émet jamais).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_frequences as f

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_count_meta_egal_au_reel():
    d = json.load(open(os.path.join(BASE, 'logx_rigs', 'frequences_iaru_r1.json'), encoding='utf-8'))
    assert d['count'] == len(d['frequences']) == 105


def test_presets_dans_la_table_digimode():
    t = f.digital_table('IARU_R1')['table']
    assert t['6m']['RTTY'] == {'dial_mhz': 50.6, 'radio_mode': 'RTTY'}
    assert t['4m']['MGM'] == {'dial_mhz': 70.27, 'radio_mode': 'USB-DATA'}
    assert t['2m']['MGM'] == {'dial_mhz': 144.6, 'radio_mode': 'USB-DATA'}
    assert t['2m']['APRS'] == {'dial_mhz': 144.8, 'radio_mode': 'FM'}


def test_dial_freq_des_presets():
    assert f.dial_freq('6m', 'RTTY') == 50.6
    assert f.dial_freq('4m', 'MGM') == 70.27
    assert f.dial_freq('2m', 'MGM') == 144.6
    assert f.dial_freq('2m', 'APRS') == 144.8


def test_144_800_est_bien_en_FM():
    # 144.800 = APRS packet -> FM, pas USB-DATA (piège si copié depuis les FT8)
    assert f.digital_table('IARU_R1')['table']['2m']['APRS']['radio_mode'] == 'FM'
