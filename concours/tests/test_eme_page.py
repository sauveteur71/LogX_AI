# -*- coding: utf-8 -*-
"""Fonctions JS pures du cockpit EME (hors DOM)."""
import os
import re
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(CONCOURS, 'logx_eme.html')


def _extraire_script(html, marqueur):
    # Le premier <script> contenant le marqueur (fonctions pures).
    for m in re.finditer(r'<script>(.*?)</script>', html, re.S):
        if marqueur in m.group(1):
            return m.group(1)
    raise AssertionError('script pur introuvable')


@pytest.fixture(scope='module')
def ctx():
    from py_mini_racer import py_mini_racer
    with open(PAGE, encoding='utf-8') as f:
        html = f.read()
    js = _extraire_script(html, 'function dopplerLabel')
    c = py_mini_racer.MiniRacer()
    c.eval('var window = {};')
    c.eval(js)
    return c


def test_dopplerLabel_signe_et_arrondi(ctx):
    assert ctx.eval('dopplerLabel(-412.4)') == '-412 Hz'
    assert ctx.eval('dopplerLabel(37.8)') == '+38 Hz'
    assert ctx.eval('dopplerLabel(null)') == '—'


def test_formatDecode_ligne_compacte(ctx):
    ligne = ctx.eval("formatDecode({call:'DL7APV', snr:-24, mode:'Q65', freq_mhz:432.071})")
    assert 'DL7APV' in ligne and '-24 dB' in ligne and 'Q65' in ligne


def test_la_page_charge_le_theme_et_le_garde(ctx):
    with open(PAGE, encoding='utf-8') as f:
        html = f.read()
    assert 'logx_theme.css' in html
    assert 'logx_theme_guard.js' in html
    # Vocabulaire : pas d'"activation"/"activateur" en texte visible.
    assert 'activateur' not in html.lower()
