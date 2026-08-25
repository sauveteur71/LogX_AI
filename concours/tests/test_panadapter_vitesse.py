# -*- coding: utf-8 -*-
"""Panadapter : vitesse du waterfall (défilement ralentissable). traceWfCetteTrame
extrait du fichier LIVRÉ et exécuté en V8 : ne trace une nouvelle ligne qu'une
trame sur N (le SPECTRE, lui, reste vif à chaque trame — seul le waterfall
ralentit pour montrer plus d'historique temporel)."""
import json
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANADAPTER = os.path.join(CONCOURS, 'logx_panadapter.html')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _lire():
    with open(PANADAPTER, encoding='utf-8') as f:
        return f.read()


def _ctx():
    m = re.search(r'  function traceWfCetteTrame\(.*?\n  \}', _lire(), re.S)
    assert m, 'traceWfCetteTrame introuvable'
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(m.group(0))
    return ctx


def _suite(ctx, everyN, frames):
    return [json.loads(ctx.eval("JSON.stringify(traceWfCetteTrame(%d,%d))" % (f, everyN))) for f in frames]


def test_rapide_trace_chaque_trame():
    ctx = _ctx()
    assert _suite(ctx, 1, [0, 1, 2, 3]) == [True, True, True, True]


def test_lent_trace_une_trame_sur_n():
    ctx = _ctx()
    # everyN=3 -> ligne aux trames 0,3,6 ; sautée à 1,2,4,5
    assert _suite(ctx, 3, [0, 1, 2, 3, 4, 5, 6]) == [True, False, False, True, False, False, True]


def test_zero_ou_negatif_se_comporte_comme_rapide():
    ctx = _ctx()
    assert _suite(ctx, 0, [0, 1, 2]) == [True, True, True]


def test_cable_dans_le_waterfall_et_selecteur():
    src = _lire()
    wf = re.search(r'function dessinerWaterfall\(.*?\n  \}', src, re.S).group(0)
    assert 'traceWfCetteTrame(' in wf and 'waterfallEveryN' in wf and 'wfFrame' in wf
    # le SPECTRE ne doit PAS être ralenti (reste vif) : la cadence ne touche
    # que dessinerWaterfall.
    sp = re.search(r'function dessinerSpectre\(.*?\n  \}', src, re.S).group(0)
    assert 'traceWfCetteTrame' not in sp and 'waterfallEveryN' not in sp
    assert 'id="paWfSpeed"' in src
    assert "setItem('rc_pa_wfspeed'" in src
