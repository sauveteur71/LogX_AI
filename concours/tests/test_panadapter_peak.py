# -*- coding: utf-8 -*-
"""Panadapter : peak hold (maintien de crête). majPeak extrait du fichier LIVRÉ
et exécuté en V8 : monte instantanément à tout nouveau maximum, décroît sinon."""
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
    m = re.search(r'  function majPeak\(.*?\n  \}', _lire(), re.S)
    assert m, 'majPeak introuvable'
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(m.group(0))
    return ctx


def test_monte_instantanement_puis_decroit():
    ctx = _ctx()
    # bin0 : data 50 > peak 10 -> 50 (montée). bin1 : data 5 < peak 20 ->
    # max(5, 20-1.5=18.5)=18.5 (décroissance douce).
    r = ctx.eval("JSON.stringify(majPeak([10,20],[50,5],1.5))")
    import json
    assert json.loads(r) == [50, 18.5]


def test_decroissance_bornee_par_le_signal():
    ctx = _ctx()
    # peak 30, data 25, decay énorme -> ne descend pas SOUS le signal courant (25)
    import json
    assert json.loads(ctx.eval("JSON.stringify(majPeak([30],[25],100))")) == [25]


def test_cable_dans_le_rendu_et_bouton():
    src = _lire()
    m = re.search(r'function dessinerSpectre\(.*?\n  \}', src, re.S)
    assert m and 'peakHoldOn' in m.group(0) and 'majPeak(peakArr' in m.group(0)
    assert 'id="paPeak"' in src
    assert "setItem('rc_pa_peak'" in src        # persistance de la bascule
