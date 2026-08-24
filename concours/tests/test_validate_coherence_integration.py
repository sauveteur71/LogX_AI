# -*- coding: utf-8 -*-
"""IA-1 lot 3 — les contrôles de cohérence (logx_controles) sont branchés dans
validate_log et s'appliquent à TOUT QSO, y compris hors concours / mode simple,
sans casser les findings concours existants."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_validator as v   # noqa: E402


def test_coherence_active_meme_en_mode_simple():
    # mode simple, aucun concours : les contrôles concours sont muets, mais la
    # cohérence freq/bande doit sortir quand même.
    log = [{'call': 'F4ABC', 'band': '14', 'freq': '7.150', 'mode': 'SSB',
            'date': '20200101', 'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59'}]
    res = v.validate_log(log, contest_id='', cfg={'usage_mode': 'simple'})
    codes = {f['code'] for f in res['findings']}
    assert 'freq_bande_incoherente' in codes


def test_findings_concours_inchanges_sur_log_ref():
    # doublon REF (même call+band) toujours détecté : la greffe cohérence ne
    # casse pas l'existant.
    log = [{'call': 'F4ABC', 'band': '14', 'mode': 'SSB', 'date': '20260101',
            'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59'},
           {'call': 'F4ABC', 'band': '14', 'mode': 'SSB', 'date': '20260101',
            'time': '1205', 'rst_sent': '59', 'rst_rcvd': '59'}]
    res = v.validate_log(log, contest_id='REF_CDF_HF_SSB', cfg={})
    assert any(f['code'] == 'doublon' for f in res['findings'])
