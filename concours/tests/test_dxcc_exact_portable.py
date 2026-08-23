# -*- coding: utf-8 -*-
"""Surcharge exacte =CALL ignorée sur indicatif portable/composé (logx_dxcc.py) — Strate 2.

cty.dat contient des surcharges EXACTES (lignes =CALL) pour les indicatifs dont
le DXCC/la zone ne suivent pas leur préfixe. _lookup_compute() testait bien
_EXACT pour l'indicatif COMPLET, mais dès qu'il y avait une barre (/P, /QRP,
/MM…), la branche « barres » ne faisait QUE du plus-long-préfixe sur les parties,
sans reconsulter _EXACT : la surcharge exacte du call de base était perdue, et le
QSO se voyait attribuer le mauvais pays / la mauvaise zone CQ.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_dxcc as dxcc   # noqa: E402


_PREFIX = ('PaysPrefixe', 'AF', 99, 99, 'ZZ', 0.0, 0.0)
_EXACT_T = ('PaysExact', 'EU', 40, 14, 'ZZ', 0.0, 0.0)


def _isole(monkeypatch, exact):
    # Tables ENTIÈREMENT remplacées : le test ne dépend pas du vrai cty.dat
    # qu'un autre test aurait pu charger dans les dicts module.
    monkeypatch.setattr(dxcc, '_loaded', True)
    monkeypatch.setattr(dxcc, '_EXACT', dict(exact))
    monkeypatch.setattr(dxcc, '_PREFIXES', {'ZZ': _PREFIX})
    dxcc._lookup_cache.clear()


def test_surcharge_exacte_honoree_sur_call_portable(monkeypatch):
    _isole(monkeypatch, {'ZZ9TEST': _EXACT_T})
    try:
        r = dxcc.lookup('ZZ9TEST/P')
        assert r and r['country'] == 'PaysExact' and r['cq_zone'] == 40, (
            "la surcharge exacte =CALL doit primer sur le préfixe pour un /P : %r" % r
        )
    finally:
        dxcc._lookup_cache.clear()


def test_prefixe_normal_toujours_ok(monkeypatch):
    _isole(monkeypatch, {})   # pas de surcharge exacte -> préfixe
    try:
        r = dxcc.lookup('ZZ9OTHER/P')
        assert r and r['country'] == 'PaysPrefixe', r
    finally:
        dxcc._lookup_cache.clear()
