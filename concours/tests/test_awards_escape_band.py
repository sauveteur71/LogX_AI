# -*- coding: utf-8 -*-
"""Le champ `band` (issu du QSO, alimentable par import ADIF, non assaini côté
serveur) était échappé dans la Worked Matrix (escHtml) mais injecté BRUT dans le
récap per_band (awards.js:133) et la liste VUCC par bande (:155), tous deux posés
via innerHTML : asymétrie d'échappement -> injection HTML par ce chemin.

Correctif : rendu extrait dans _awardsPerBandHtml()/_awardsVuccBandesHtml() qui
échappent `band` via escHtml (le VRAI escHtml de logx_logbook.js est injecté,
pas un stub — sinon le test ne contraindrait qu'un mannequin).
"""
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer', reason='py_mini_racer absent')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _extract_function(src, name):
    m = re.search(r'^(?:async\s+)?function %s\(' % re.escape(name), src, re.M)
    assert m, name
    depth = 0
    i = src.index('{', m.start())
    while True:
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return src[m.start():i + 1]
        i += 1


with open(os.path.join(BASE, 'logx_awards.js'), encoding='utf-8') as f:
    _AWARDS = f.read()
with open(os.path.join(BASE, 'logx_logbook.js'), encoding='utf-8') as f:
    _ESCHTML = _extract_function(f.read(), 'escHtml')

_PERBAND = _extract_function(_AWARDS, '_awardsPerBandHtml')
_VUCC = _extract_function(_AWARDS, '_awardsVuccBandesHtml')


def _ctx():
    c = py_mini_racer.MiniRacer()
    c.eval(_ESCHTML + '\n' + _PERBAND + '\n' + _VUCC)
    return c


def test_per_band_echappe_le_champ_band():
    c = _ctx()
    html = c.eval("_awardsPerBandHtml({'<img src=x onerror=alert(1)>': {qso:5, dxcc:2}})")
    assert '<img' not in html and '&lt;img' in html, html


def test_vucc_echappe_le_champ_band():
    c = _ctx()
    html = c.eval("_awardsVuccBandesHtml({'<b>x</b>': 3})")
    assert '<b>x</b>' not in html and '&lt;b&gt;' in html, html
