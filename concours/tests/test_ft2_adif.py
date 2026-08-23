# -*- coding: utf-8 -*-
"""Terrain FT2 — Phase 1 (ADIF uniquement, aucune émission).

FT2 = sous-mode EXPÉRIMENTAL de MFSK. Règle : export MODE=MFSK + SUBMODE=FT2,
JAMAIS MODE=FT2 ; import MODE=MFSK+SUBMODE=FT2 -> mode interne 'FT2'. Les autres
sous-modes (JS8CALL…) restent préservés dans extra_fields.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_export
import logx_import


def _mode_of(adif):
    # le serveur n'ajoute pas d'espace après la valeur : borner par < ou espace
    m = re.search(r'<mode:\d+>([^<\s]+)', adif, re.I)
    return m.group(1) if m else None


def _submode_of(adif):
    m = re.search(r'<submode:\d+>([^<\s]+)', adif, re.I)
    return m.group(1) if m else None


def test_export_serveur_ft2_devient_mfsk_submode():
    q = {'call': 'F5ABC', 'band': '14', 'mode': 'FT2', 'date': '20260801',
         'time': '1200', 'rst_sent': '599', 'rst_rcvd': '599'}
    adif = logx_export.build_adif([q])
    assert _mode_of(adif) == 'MFSK'
    assert _submode_of(adif) == 'FT2'
    assert re.search(r'<mode:\d+>FT2', adif, re.I) is None   # jamais MODE=FT2


def test_export_serveur_autre_mode_inchange():
    q = {'call': 'F5ABC', 'band': '14', 'mode': 'FT8', 'date': '20260801', 'time': '1200'}
    adif = logx_export.build_adif([q])
    assert _mode_of(adif) == 'FT8' and _submode_of(adif) is None


def test_import_mfsk_submode_ft2_devient_ft2():
    adif = ("<adif_ver:5>3.1.7<EOH>\n"
            "<CALL:5>F5ABC<BAND:3>20m<MODE:4>MFSK<SUBMODE:3>FT2"
            "<QSO_DATE:8>20260801<TIME_ON:4>1200<EOR>\n")
    qsos, _ = logx_import.parse_adif_to_qsos(adif)
    assert len(qsos) == 1 and qsos[0]['mode'] == 'FT2'
    # SUBMODE consommé -> pas laissé dans extra_fields
    assert 'SUBMODE' not in qsos[0].get('extra_fields', {})


def test_import_autre_sousmode_reste_dans_extra():
    adif = ("<adif_ver:5>3.1.7<EOH>\n"
            "<CALL:5>F5ABC<BAND:3>20m<MODE:4>MFSK<SUBMODE:7>JS8CALL"
            "<QSO_DATE:8>20260801<TIME_ON:4>1200<EOR>\n")
    qsos, _ = logx_import.parse_adif_to_qsos(adif)
    assert qsos[0]['mode'] == 'MFSK'                              # pas FT2
    assert qsos[0]['extra_fields'].get('SUBMODE') == 'JS8CALL'    # préservé


def test_aller_retour_ft2_pas_de_double_submode():
    adif_in = ("<adif_ver:5>3.1.7<EOH>\n"
               "<CALL:5>F5ABC<BAND:3>20m<MODE:4>MFSK<SUBMODE:3>FT2"
               "<QSO_DATE:8>20260801<TIME_ON:4>1200<EOR>\n")
    qsos, _ = logx_import.parse_adif_to_qsos(adif_in)
    adif_out = logx_export.build_adif(qsos)
    assert adif_out.upper().count('<SUBMODE:') == 1               # pas de double
    assert _mode_of(adif_out) == 'MFSK' and _submode_of(adif_out) == 'FT2'


def test_client_export_a_la_branche_ft2():
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'logx_export_adif.js'), encoding='utf-8').read()
    # structure : la branche FT2 écrit MODE=MFSK + SUBMODE=FT2
    assert re.search(r"===\s*'FT2'", src)
    assert "adifField('MODE', 'MFSK')" in src and "adifField('SUBMODE', 'FT2')" in src
