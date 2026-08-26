# -*- coding: utf-8 -*-
"""Lot 3 — award_summary source-aware : une confirmation eQSL ne doit PAS
créditer les diplômes ARRL (DXCC…), qui n'acceptent qu'LoTW + papier. Elle
reste comptée dans le « confirmé (tous services) » général.

Garde-fou capital du chantier (décision F4GLD) : eQSL n'inflate jamais le DXCC.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_awards as awards

_QSO = [{'call': 'F4ABC', 'band': '20', 'mode': 'SSB', 'date': '20260101', 'time': '10:00'}]
_KEY = 'F4ABC|20|SSB'


def _prep(monkeypatch, conf):
    monkeypatch.setattr(awards, '_read_archives', lambda: [])
    monkeypatch.setattr(awards, '_read_qso_archive', lambda: [])
    monkeypatch.setattr(awards, '_load_confirmations', lambda: conf)
    awards.invalidate()


def test_eqsl_ne_credite_pas_le_dxcc(monkeypatch):
    _prep(monkeypatch, {_KEY: {'eqsl': True}})
    s = awards.award_summary(_QSO)
    assert s['dxcc']['worked'] >= 1, "France doit être travaillée (enrichissement)"
    assert s['dxcc']['confirmed'] == 0, "eQSL ne doit PAS créditer le DXCC (ARRL)"
    # ...mais reste comptée comme confirmation générale (tous services).
    assert s['confirmed_total'] >= 1


def test_lotw_credite_le_dxcc(monkeypatch):
    _prep(monkeypatch, {_KEY: {'lotw': True}})
    s = awards.award_summary(_QSO)
    assert s['dxcc']['confirmed'] == 1, "LoTW doit créditer le DXCC (non-régression)"
