# -*- coding: utf-8 -*-
"""logx_ref_info.js : relevé sommet/parc quand on tape une réf (SOTA/POTA…).

On teste _fmt (pur) : mise en forme « Nom · région · alt m · pts », champs absents
omis, entrée vide -> chaîne vide. Le câblage HTML (script inclus) est aussi vérifié.
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_ref_info.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("var window = {};")
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_fmt_complet():
    ctx = _ctx()
    txt = ctx.eval("window.LogxRefInfo._fmt({name:'Scafell Pike', region:'Lake District',"
                   " alt_m:978, points:10})")
    assert txt == 'Scafell Pike · Lake District · 978 m · 10 pts'


def test_fmt_champs_absents_omis():
    ctx = _ctx()
    assert ctx.eval("window.LogxRefInfo._fmt({name:'Le Pouce', alt_m:810})") == 'Le Pouce · 810 m'
    assert ctx.eval("window.LogxRefInfo._fmt({name:'X'})") == 'X'


def test_fmt_vide():
    ctx = _ctx()
    assert ctx.eval("window.LogxRefInfo._fmt(null)") == ''
    assert ctx.eval("window.LogxRefInfo._fmt({})") == ''


def test_cablage_logbook():
    with open(os.path.join(CONCOURS, 'logx_logbook.html'), encoding='utf-8') as f:
        h = f.read()
    assert 'src="logx_ref_info.js"' in h
    assert 'id="theirRefInfo"' in h
