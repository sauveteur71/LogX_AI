# -*- coding: utf-8 -*-
"""Le relais EME ne garde que les décodages Q65/JT65 (pas FT8/FT4)."""
import os
import sys
import time

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_wsjtx as w   # noqa: E402


def _peupler(monkeypatch, modes):
    now = time.time()
    faux = [{'call': 'STA%d' % i, 'band': '432', 'freq_mhz': 432.07,
             'mode': m, 'message': 'CQ STA%d IO91' % i, 'snr': -22,
             'last_seen': now} for i, m in enumerate(modes)]
    monkeypatch.setattr(w, 'recent_decodes', lambda max_age=w._DECODE_TTL: faux)


def test_garde_Q65_et_JT65_exclut_FT8_FT4(monkeypatch):
    _peupler(monkeypatch, ['Q65', 'FT8', 'JT65', 'FT4', 'q65'])
    modes = {d['mode'].upper() for d in w.eme_decodes()}
    assert modes == {'Q65', 'JT65'}, modes


def test_liste_vide_si_aucun_mode_EME(monkeypatch):
    _peupler(monkeypatch, ['FT8', 'FT4'])
    assert w.eme_decodes() == []
