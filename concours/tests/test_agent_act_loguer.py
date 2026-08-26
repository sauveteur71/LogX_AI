# -*- coding: utf-8 -*-
"""Copilote NL — action loguer_station (F4GLD 26/08, feu vert). « logue TX9A » ->
l'agent propose un pending {type:'log', call, band, mode, ...} que l'opérateur
CONFIRME avant écriture (ajout only via /log/add, jamais modif/suppression).
RST par défaut selon le mode (599 hors phonie, 59 en phonie). Validation stricte :
sans indicatif/bande/mode -> None (jamais un QSO fantôme)."""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as h   # noqa: E402


def _p(inp):
    return h.pending_action_from_tool({'tool': 'loguer_station', 'input': inp})


def test_log_numerique_rst_599():
    a = _p({'indicatif': 'tx9a', 'band': '20', 'mode': 'FT8'})
    assert a == {'type': 'log', 'call': 'TX9A', 'band': '20', 'mode': 'FT8', 'rst': '599'}


def test_log_phonie_rst_59():
    a = _p({'indicatif': 'EA8AA', 'band': '40', 'mode': 'SSB'})
    assert a['type'] == 'log' and a['rst'] == '59' and a['call'] == 'EA8AA'


def test_log_avec_frequence():
    a = _p({'indicatif': 'DL1ABC', 'band': '20', 'mode': 'CW', 'freq_khz': 14025.5})
    assert a['freq_khz'] == 14025.5 and a['rst'] == '599'


def test_log_freq_absurde_ignoree_mais_qso_garde():
    a = _p({'indicatif': 'DL1ABC', 'band': '20', 'mode': 'CW', 'freq_khz': -3})
    assert 'freq_khz' not in a and a['call'] == 'DL1ABC'   # QSO valide, fréquence écartée


def test_log_champs_manquants_refuses():
    assert _p({'indicatif': 'TX9A', 'mode': 'FT8'}) is None          # pas de bande
    assert _p({'band': '20', 'mode': 'FT8'}) is None                 # pas d'indicatif
    assert _p({'indicatif': 'TX9A', 'band': '20'}) is None           # pas de mode
