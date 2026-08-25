# -*- coding: utf-8 -*-
"""Panadapter : lecture de la fréquence SOUS LE CURSEUR (survol), complément du
click-to-tune. fmtFreqHz extrait et exécuté en V8 ; câblage structurel."""
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
    src = _lire()
    m = re.search(r'  function fmtFreqHz\(.*?\n  \}', src, re.S)
    assert m, 'fmtFreqHz introuvable'
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(m.group(0))
    return ctx


def test_fmt_mhz_et_hz():
    ctx = _ctx()
    assert ctx.eval("fmtFreqHz(14074000)") == '14.0740 MHz'
    assert ctx.eval("fmtFreqHz(1500)") == '1500 Hz'          # < 1 MHz -> Hz (audio)
    assert ctx.eval("fmtFreqHz(7100500)") == '7.1005 MHz'


def test_readout_present():
    assert 'id="paHoverFreq"' in _lire()


def test_hover_cable_sur_les_deux_canvas():
    src = _lire()
    m = re.search(r'function majHover\(.*?\n  \}', src, re.S)
    assert m, 'majHover introuvable'
    corps = m.group(0)
    assert 'plageHzActuelle()' in corps and 'freqAuClic(' in corps
    assert re.search(r'if\(!plage\)', corps)                  # audio brut -> pas de fréquence
    assert "majHover(e, _specCv)" in src and "majHover(e, _waterCv)" in src
    # le click-tune n'est pas cassé
    assert "clicCanvas(e, _specCv)" in src and "clicCanvas(e, _waterCv)" in src
