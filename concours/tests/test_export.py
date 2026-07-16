# -*- coding: utf-8 -*-
"""Tests des exports Cabrillo et ADIF (radiocontest_export)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radiocontest_export import build_cabrillo, build_adif

QSOS = [
    {'call': 'dl1abc', 'band': '14', 'mode': 'CW', 'date': '20260801',
     'time': '12:03', 'rst_sent': '599', 'num_sent': '001',
     'rst_rcvd': '599', 'num_rcvd': '042', 'points': 1,
     'operator': 'OP1', 'contest': 'EU_HF_CHAMP'},
    {'call': 'F1XYZ', 'band': '144', 'mode': 'SSB', 'date': '20260801',
     'time': '12:10', 'rst_sent': '59', 'num_sent': '002',
     'rst_rcvd': '59', 'num_rcvd': '007', 'locator': 'JN18DU',
     'points': 435, 'operator': 'OP2', 'contest': 'EU_HF_CHAMP'},
]
CFG = {'callsign': 'F6KQJ', 'locator': 'JN15XC', 'power_class': 'LP',
       'contest': 'EU_HF_CHAMP', 'op_name': 'Test OP', 'email': 't@e.fr'}


def test_cabrillo_structure():
    cab = build_cabrillo(QSOS, {'cabrillo_name': 'EU-HF'}, CFG)
    assert cab.startswith('START-OF-LOG: 3.0')
    assert cab.rstrip().endswith('END-OF-LOG:')
    assert 'CONTEST: EU-HF' in cab
    assert 'CALLSIGN: F6KQJ' in cab
    assert 'CLAIMED-SCORE: 436' in cab               # 1 + 435
    assert 'CATEGORY-OPERATOR: MULTI-OP' in cab      # OP1 + OP2


def test_cabrillo_lignes_qso():
    cab = build_cabrillo(QSOS, {}, CFG)
    qso_lines = [l for l in cab.split('\n') if l.startswith('QSO:')]
    assert len(qso_lines) == 2
    # HF : fréquence nominale en kHz ; mode CW ; indicatif en majuscules
    assert '14000' in qso_lines[0] and ' CW ' in qso_lines[0] and 'DL1ABC' in qso_lines[0]
    # VHF : désignateur de bande '144' ; SSB → PH ; locator reçu inclus
    assert ' 144 ' in qso_lines[1] and ' PH ' in qso_lines[1] and 'JN18DU' in qso_lines[1]
    assert '2026-08-01' in qso_lines[0] and '1203' in qso_lines[0]


def test_adif_structure():
    adi = build_adif(QSOS, CFG)
    assert '<EOH>' in adi
    assert adi.count('<EOR>') == 2
    # Longueurs de champs ADIF exactes
    assert '<call:6>DL1ABC' in adi
    assert '<band:3>20m' in adi and '<band:2>2m' in adi
    assert '<qso_date:8>20260801' in adi
    assert '<time_on:4>1203' in adi
    assert '<gridsquare:6>JN18DU' in adi
    assert '<contest_id:11>EU_HF_CHAMP' in adi


def test_export_vide():
    assert build_cabrillo([], {}, CFG).rstrip().endswith('END-OF-LOG:')
    assert build_adif([], CFG).count('<EOR>') == 0
