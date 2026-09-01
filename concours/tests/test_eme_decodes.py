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
    # STA0=Q65, STA1=FT8, STA2=JT65, STA3=FT4, STA4=q65 (minuscule). On
    # assert sur les CALL retournés, pas sur l'ensemble des modes uppercasés :
    # STA4 en 'q65' minuscule est ainsi DISCRIMINANT — retirer le .upper() de
    # eme_decodes exclurait STA4 et ferait rougir ce test (l'insensibilité à
    # la casse est réellement contrainte, pas seulement l'exclusion FT8/FT4).
    _peupler(monkeypatch, ['Q65', 'FT8', 'JT65', 'FT4', 'q65'])
    calls = {d['call'] for d in w.eme_decodes()}
    assert calls == {'STA0', 'STA2', 'STA4'}, calls


def test_liste_vide_si_aucun_mode_EME(monkeypatch):
    _peupler(monkeypatch, ['FT8', 'FT4'])
    assert w.eme_decodes() == []
