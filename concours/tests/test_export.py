# -*- coding: utf-8 -*-
"""Tests des exports Cabrillo et ADIF (logx_export)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logx_export import build_cabrillo, build_adif

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


# ─── QTC (WAE) : lignes "QTC:" du Cabrillo, format vérifié contre les règles
# publiques DARC/WAEDC (QRG MODE DATE TIME CALL-RX QTC-GRP CALL-TX TIME-QSO
# CALL-QSO NR-QSO — une ligne par QTC individuel, pas par série) ────────────

QTC_SENT = {'call': 'DL0XM', 'direction': 'sent', 'band': '14', 'mode': 'CW',
            'date': '20260810', 'time': '01:55', 'series_number': 1,
            'entries': [{'time': '00:30', 'call': 'YU1ZZ', 'nr': '62'}]}
QTC_RECV = {'call': 'CT3KU', 'direction': 'recv', 'band': '14', 'mode': 'CW',
            'date': '20260810', 'time': '01:55', 'series_number': 7,
            'entries': [{'time': '13:07', 'call': 'DA1AA', 'nr': '431'}]}
QTC_SANS_DETAIL = {'call': 'F5ABC', 'count': 3, 'contest': 'WAEDC_SSB'}   # ancien format


def test_cabrillo_qtc_serie_envoyee_moi_emetteur():
    cab = build_cabrillo(QSOS, {}, CFG, [QTC_SENT])
    lines = [l for l in cab.split('\n') if l.startswith('QTC:')]
    assert len(lines) == 1
    line = lines[0]
    assert '14000' in line and 'CW' in line and '2026-08-10' in line and '0155' in line
    assert '1/1' in line and '0030' in line and 'YU1ZZ' in line and '62' in line
    # Envoyée : CALL-RX (partenaire DL0XM) précède CALL-TX (nous, F6KQJ)
    assert line.index('DL0XM') < line.index('F6KQJ')


def test_cabrillo_qtc_serie_recue_moi_recepteur():
    cab = build_cabrillo(QSOS, {}, CFG, [QTC_RECV])
    line = [l for l in cab.split('\n') if l.startswith('QTC:')][0]
    assert '7/1' in line and '1307' in line and 'DA1AA' in line and '431' in line
    # Reçue : CALL-RX (nous, F6KQJ) précède CALL-TX (partenaire CT3KU)
    assert line.index('F6KQJ') < line.index('CT3KU')


def test_cabrillo_qtc_serie_sans_detail_ignoree_a_l_export():
    """Une série enregistrée avant cette fonctionnalité (comptage seul, sans
    'entries') ne peut pas être reconstituée en ligne WAE-QTC valide — elle
    ne doit pas produire de ligne QTC: fantaisiste, ni faire planter l'export."""
    cab = build_cabrillo(QSOS, {}, CFG, [QTC_SANS_DETAIL])
    assert not [l for l in cab.split('\n') if l.startswith('QTC:')]
    assert cab.rstrip().endswith('END-OF-LOG:')


def test_cabrillo_qtc_absent_reste_retrocompatible():
    # Signature à 3 arguments (avant l'ajout du paramètre qtc_series) : ne
    # doit toujours rien changer pour les appelants existants.
    cab = build_cabrillo(QSOS, {}, CFG)
    assert 'QTC:' not in cab
