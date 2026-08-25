# -*- coding: utf-8 -*-
"""Bande 60m (5 MHz) — bande interne UNIQUE '5' (décision F4GLD 25/08 : une bande,
pas des canaux, couvrant toute la portion attribuée). Manquait de toutes les
tables -> un QSO/ADIF 60m réel n'était pas reconnu. Plage ADIF déjà sourcée
(logx_adif_enums.ADIF_BANDS '60m': 5.06-5.45)."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_export as export     # noqa: E402
import logx_import as imp         # noqa: E402
import logx_scoring as scoring    # noqa: E402
import logx_wsjtx as wsjtx        # noqa: E402


def test_freq_5mhz_donne_bande_interne_5():
    assert scoring._band_from_freq('5.357') == '5'      # MHz
    assert scoring._band_from_freq('5357') == '5'       # kHz
    assert scoring._band_from_freq('7.1') == '7'        # non-régression


def test_mhz_to_band_wsjtx_jumeau():
    assert wsjtx._mhz_to_band(5.357) == '5'


def test_export_bande_5_donne_60m():
    q = {'call': 'F4ABC', 'band': '5', 'mode': 'SSB', 'date': '20260101',
         'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59'}
    adif = export.build_adif([q], {}).upper()
    assert '<BAND:3>60M' in adif, adif


def test_import_60m_donne_bande_5():
    adif = ("<CALL:5>F4ABC<BAND:3>60m<MODE:3>SSB<QSO_DATE:8>20260101"
            "<TIME_ON:4>1200<EOR>")
    qsos, err = imp.parse_adif_to_qsos(adif)
    assert not err and qsos and qsos[0]['band'] == '5', (err, qsos)


def test_aller_retour_60m():
    q = {'call': 'F4ABC', 'band': '5', 'mode': 'CW', 'date': '20260101',
         'time': '1200', 'rst_sent': '599', 'rst_rcvd': '599'}
    adif = export.build_adif([q], {})
    qsos, _ = imp.parse_adif_to_qsos(adif)
    assert qsos[0]['band'] == '5'


def test_toggle_ui_60m_present():
    # BAND_TOGGLE_KEY (logx_contest_rules.js) doit exposer la bande 5 (sinon
    # 60m ne serait pas sélectionnable/filtrable dans l'UI).
    js = open(os.path.join(BASE, 'logx_contest_rules.js'), encoding='utf-8').read()
    i = js.index('BAND_TOGGLE_KEY')
    bloc = js[i:js.index('}', i)]
    assert "'5'" in bloc, bloc
