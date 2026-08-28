# -*- coding: utf-8 -*-
"""Récap « APRÈS LE QSO » (logx_apres_qso.js) — testé en V8.

Le calcul de « ce qu'un QSO apporte » est côté serveur (logx_awards via
/call/history : new_one, lotw_need — testés ailleurs). Ici on teste QUE la
couche présentation propre à cette brique :
  - _evaluer() traduit la réponse /call/history en gains + « à confirmer » ;
  - _rendre() affiche une pastille non-modale, et RESTE SILENCIEUX si le QSO
    n'apporte rien (pas de bruit sur un doublon) ;
  - échappement XSS du libellé.
Aucun démarrage auto (le module ne s'active qu'au hook submitQSO en vrai
navigateur).
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_apres_qso.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      var window = {};
      window.__filPush = [];
      window.LogxFilIA = { pousser: function(s, e){ window.__filPush.push({source: s, n: (e||[]).length}); } };
      var __p = { innerHTML: '', style: { display: '' } };
      var document = { getElementById: function(id){ return id === 'apresQsoPastille' ? __p : null; } };
    """)
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_evaluer_extrait_gains_et_a_confirmer():
    ctx = _ctx()
    ctx.eval("""window.__e = window.LogxApresQso._evaluer({
      new_one: [
        {type:'dxcc', scope:'atlantic', label:'nouveau pays : Japon'},
        {type:'dxcc', scope:'band', label:'nouvelle bande : 20 m'},
        {type:'dept', scope:'atlantic', label:'nouveau département : 56'}
      ],
      lotw_need: {besoin:true, label:'LoTW non confirmé (Japon 20 m FT8)'}
    });""")
    assert ctx.eval("window.__e.gains.length") == 3
    assert ctx.eval("window.__e.aconf.length") == 1
    assert 'Japon' in ctx.eval("window.__e.gains[0].label")
    assert 'LoTW' in ctx.eval("window.__e.aconf[0]")


def test_evaluer_rien_si_doublon():
    ctx = _ctx()
    ctx.eval("window.__e = window.LogxApresQso._evaluer({new_one: [], lotw_need: {besoin:false}});")
    assert ctx.eval("window.__e.gains.length") == 0
    assert ctx.eval("window.__e.aconf.length") == 0


def test_rendre_affiche_gains_et_a_confirmer():
    ctx = _ctx()
    ctx.eval("""window.LogxApresQso._rendre({
      gains: [{emoji:'🌟', label:'nouveau pays : Japon'}],
      aconf: ['LoTW non confirmé']});""")
    html = ctx.eval("__p.innerHTML")
    assert 'enregistr' in html.lower()            # « QSO enregistré »
    assert 'Japon' in html
    assert 'confirmer' in html.lower() and 'LoTW' in html
    assert ctx.eval("__p.style.display") == 'flex'


def test_rendre_silence_si_rien_a_dire():
    ctx = _ctx()
    ctx.eval("window.LogxApresQso._rendre({gains: [], aconf: []});")
    assert ctx.eval("__p.style.display") == 'none'   # pas de bruit sur un doublon
    assert ctx.eval("__p.innerHTML") == ''


def test_rendre_echappe_le_xss():
    ctx = _ctx()
    ctx.eval("""window.LogxApresQso._rendre({
      gains: [{emoji:'🌟', label:'<img src=x onerror=1>'}], aconf: []});""")
    html = ctx.eval("__p.innerHTML")
    assert '<img' not in html and '&lt;img' in html


def test_alimente_le_fil_ia():
    ctx = _ctx()
    ctx.eval("window.LogxApresQso._rendre({gains:[{emoji:'🌟', label:'nouveau pays : Japon'}], aconf:[]});")
    assert ctx.eval("window.__filPush[window.__filPush.length-1].source") == 'apres_qso'
    assert ctx.eval("window.__filPush[window.__filPush.length-1].n") == 1
    ctx.eval("window.LogxApresQso._rendre({gains:[], aconf:[]});")
    assert ctx.eval("window.__filPush[window.__filPush.length-1].n") == 0   # rien -> retiré


def test_cablage_logbook():
    with open(os.path.join(CONCOURS, 'logx_logbook.html'), encoding='utf-8') as f:
        h = f.read()
    assert 'src="logx_apres_qso.js"' in h
    assert 'id="apresQsoPastille"' in h
    with open(os.path.join(CONCOURS, 'logx_logbook.js'), encoding='utf-8') as f:
        js = f.read()
    assert 'LogxApresQso.montrer' in js              # branché sur le flux d'enregistrement
