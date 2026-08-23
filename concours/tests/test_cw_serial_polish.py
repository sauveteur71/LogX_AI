# -*- coding: utf-8 -*-
"""Polissages keyer série : plafond anti-runaway + journalisation TX série."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_cw_serial as cw


def test_plafond_refuse_un_texte_trop_long():
    # à 5 mots/min, 40 « PARIS » dépassent largement 120 s -> refus AVANT toute
    # ouverture de port (le garde-fou est vérifié en amont).
    res = cw.envoyer({'cw_serial_enabled': '1', 'cw_serial_port': 'COM9',
                      'cw_serial_wpm': 5}, 'PARIS ' * 40)
    assert res['ok'] is False and 'runaway' in res['error']


def test_un_qso_normal_reste_tres_sous_le_plafond():
    # un échange de contest typique est très en dessous des 120 s -> jamais refusé
    d = cw.duree_totale_ms('CQ TEST F4GLD F4GLD K', 25)
    assert 0 < d < cw._MAX_EMISSION_MS


def test_http_journalise_le_backend_serie():
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'logx_http.py'), encoding='utf-8').read()
    assert "cwj.enregistrer(res.get('text'), 'serial', wpm=res.get('wpm'))" in src
