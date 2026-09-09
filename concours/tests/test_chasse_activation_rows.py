# -*- coding: utf-8 -*-
"""renderActivationRows (fusion D2, incr. 4b) : rendu PUR des lignes d'un panneau
d'activation « en direct » (POTA/SOTA/WWFF/WCA), format sr-act commun, la ligne
« lieu » fournie par opts.place(s) (park_name / summit_name+alt+pts / …). Champs
issus de services tiers publics -> tout passe par esc(). Exécuté en V8.
"""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_chasse_panneaux.js')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("var window = this;")
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_expose_render_activation_rows():
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxChassePanneaux.renderActivationRows") == 'function'


def test_rend_call_band_freq_mode():
    ctx = _ctx()
    html = ctx.eval("""window.LogxChassePanneaux.renderActivationRows([
        {call:'F4ABC', band:'14', freq:14285, mode:'SSB', reference:'FF-0001'}
    ])""")
    assert 'F4ABC' in html and 'sr-act' in html
    assert '14.285 MHz' in html          # freq kHz -> MHz, 3 décimales
    assert 'SSB' in html


def test_place_fn_utilisee():
    ctx = _ctx()
    html = ctx.eval("""window.LogxChassePanneaux.renderActivationRows(
        [{call:'F4ABC', reference:'F/AB-421'}],
        {place:function(s){ return 'SOMMET ' + s.reference; }}
    )""")
    assert 'SOMMET F/AB-421' in html


def test_echappe_les_champs_tiers():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderActivationRows([{call:'<x>', band:'14', comment:'<b>hi</b>'}])")
    assert '<x>' not in html and '&lt;x&gt;' in html
    assert '<b>hi</b>' not in html and '&lt;b&gt;' in html


def test_respecte_le_max():
    ctx = _ctx()
    n = ctx.eval("""(function(){
        var s=[]; for(var i=0;i<40;i++) s.push({call:'C'+i});
        return (window.LogxChassePanneaux.renderActivationRows(s,{max:10}).match(/sr-act/g)||[]).length;
    })()""")
    assert n == 10
