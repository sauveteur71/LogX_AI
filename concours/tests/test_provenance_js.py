# -*- coding: utf-8 -*-
"""Relevé de provenance côté client (logx_provenance.js) — testé en V8."""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_provenance.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      var window = {};
      var __p = { hidden: false, innerHTML: '' };
      var document = { getElementById: function(id){ return id === 'provenancePanel' ? __p : null; } };
    """)
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_rendre_affiche_champ_valeur_source():
    ctx = _ctx()
    ctx.eval("""window.LogxProvenance._rendre([
      {champ:'Pays', valeur:'Japon', source:'cty.dat'},
      {champ:'Distance', valeur:'9100 km', source:'calculé (cty.dat)'}]);""")
    html = ctx.eval("__p.innerHTML")
    assert 'Pays' in html and 'Japon' in html and 'cty.dat' in html
    assert 'Distance' in html and 'calculé' in html
    assert ctx.eval("__p.hidden") is False


def test_rendre_vide_cache():
    ctx = _ctx()
    ctx.eval("window.LogxProvenance._rendre([]);")
    assert ctx.eval("__p.hidden") is True
    assert ctx.eval("__p.innerHTML") == ''


def test_rendre_echappe_xss():
    ctx = _ctx()
    ctx.eval("window.LogxProvenance._rendre([{champ:'X', valeur:'<img src=x onerror=1>', source:'s'}]);")
    html = ctx.eval("__p.innerHTML")
    assert '<img' not in html and '&lt;img' in html


def test_cablage_logbook():
    with open(os.path.join(CONCOURS, 'logx_logbook.html'), encoding='utf-8') as f:
        h = f.read()
    assert 'src="logx_provenance.js"' in h
    assert 'id="provenancePanel"' in h
