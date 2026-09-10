# -*- coding: utf-8 -*-
"""renderWcaRows / renderDxRows (fusion D2, incr. 4c) : complète les panneaux
POTA/SOTA/WWFF (incr. 4b) avec WCA/COTA et DXpéditions dans l'activité
« activation portable » — lecture seule, même patron additif. Champs sourcés
sur logx_wca.py (reference/title/description) et logx_dxpeditions.py
(callsign/entity/dates/qsl/status/worked_status/freq_khz/spot_band/spot_mode).
Exécuté en V8.
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


# ─── renderWcaRows ──────────────────────────────────────────────────────────

def test_expose_render_wca_rows():
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxChassePanneaux.renderWcaRows") == 'function'


def test_wca_rend_reference_et_titre():
    ctx = _ctx()
    html = ctx.eval("""window.LogxChassePanneaux.renderWcaRows([
        {reference:'DL-03166', title:'DL/AB1CD activation château', description:'Info WCA'}
    ])""")
    assert 'DL-03166' in html and 'château' in html and 'sr-wca' in html


def test_wca_tronque_la_description_a_160():
    # `title=` porte la description ENTIÈRE (info au survol, comme
    # logx_chasse.html) ; seul le TEXTE VISIBLE (entre balises) est tronqué à
    # 160 car. -> on borne la recherche à un nœud texte (précédé de `>`).
    ctx = _ctx()
    html = ctx.eval("""(function(){
        var d = ''; for(var i=0;i<300;i++) d += 'x';
        return window.LogxChassePanneaux.renderWcaRows([{reference:'F-001', title:'t', description:d}]);
    })()""")
    assert ('>' + 'x' * 160 + '<') in html
    assert ('>' + 'x' * 161) not in html


def test_wca_echappe_les_champs_tiers():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderWcaRows([{reference:'<x>', title:'<b>t</b>'}])")
    assert '<x>' not in html and '&lt;x&gt;' in html
    assert '<b>t</b>' not in html and '&lt;b&gt;' in html


def test_wca_liste_vide():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderWcaRows([])")
    assert 'ck-need-empty' in html


def test_wca_respecte_le_max():
    ctx = _ctx()
    n = ctx.eval("""(function(){
        var s=[]; for(var i=0;i<40;i++) s.push({reference:'R'+i});
        return (window.LogxChassePanneaux.renderWcaRows(s,{max:7}).match(/sr-wca/g)||[]).length;
    })()""")
    assert n == 7


# ─── renderDxRows ───────────────────────────────────────────────────────────

def test_expose_render_dx_rows():
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxChassePanneaux.renderDxRows") == 'function'


def test_dx_rend_call_entity_dates():
    ctx = _ctx()
    html = ctx.eval("""window.LogxChassePanneaux.renderDxRows([
        {callsign:'3D2AG', entity:'Rotuma', dates:'01-15/09', status:'active', freq_khz:14195, spot_mode:'SSB'}
    ])""")
    assert '3D2AG' in html and 'Rotuma' in html and '01-15/09' in html
    assert '14.195 MHz' in html and 'SSB' in html and 'ACTIVE' in html


def test_dx_badge_a_venir_si_pas_actif():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderDxRows([{callsign:'XX1XX', status:'upcoming'}])")
    assert 'ACTIVE' not in html


def test_dx_badge_nouveau_pays():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderDxRows([{callsign:'XX1XX', worked_status:'new'}])")
    assert 'nouveau pays' in html


def test_dx_qsl_affichee_si_presente():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderDxRows([{callsign:'XX1XX', qsl:'via LOTW'}])")
    assert 'via LOTW' in html


def test_dx_echappe_les_champs_tiers():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderDxRows([{callsign:'<x>', entity:'<b>e</b>'}])")
    assert '<x>' not in html and '&lt;x&gt;' in html
    assert '<b>e</b>' not in html and '&lt;b&gt;' in html


def test_dx_liste_vide():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderDxRows([])")
    assert 'ck-need-empty' in html


def test_dx_respecte_le_max():
    ctx = _ctx()
    n = ctx.eval("""(function(){
        var s=[]; for(var i=0;i<60;i++) s.push({callsign:'C'+i});
        return (window.LogxChassePanneaux.renderDxRows(s,{max:9}).match(/sr-act/g)||[]).length;
    })()""")
    assert n == 9
