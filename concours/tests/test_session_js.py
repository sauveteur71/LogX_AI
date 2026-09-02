# -*- coding: utf-8 -*-
"""Planificateur de session côté client (logx_session.js) — testé en V8.

La génération du plan est côté serveur (logx_session + /session/plan, testé
ailleurs). Ici : _payload() lit le formulaire, _rendre() affiche le plan (texte,
jamais d'HTML injecté) ou une erreur discrète."""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_session.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      var window = {};
      var __vals = {sessDuree:'30', sessObjectif:'3 DXCC', sessMode:'FT8', sessBandes:'20m, 15m', sessPuissance:'100'};
      var __plan = { textContent:'', _cls:{}, classList:{ add:function(c){__plan._cls[c]=true;}, remove:function(c){__plan._cls[c]=false;} } };
      var __ctx = { checked: true };
      var document = { getElementById:function(id){
          if(id==='sessPlan') return __plan;
          if(id==='sessContexte') return __ctx;
          return (id in __vals) ? { value: __vals[id] } : null; } };
    """)
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_payload_lit_le_formulaire():
    ctx = _ctx()
    ctx.eval("window.__p = window.LogxSession._payload();")
    assert ctx.eval("window.__p.duree_min") == 30
    assert ctx.eval("window.__p.objectif") == '3 DXCC'
    assert ctx.eval("window.__p.mode") == 'FT8'
    assert ctx.eval("window.__p.bandes") == '20m, 15m'
    assert ctx.eval("window.__p.puissance_w") == 100
    assert ctx.eval("window.__p.avec_contexte") is True     # case cochée par défaut


def test_payload_contexte_decoche():
    ctx = _ctx()
    ctx.eval("__ctx.checked = false;")
    ctx.eval("window.__p = window.LogxSession._payload();")
    assert ctx.eval("window.__p.avec_contexte") is False


def test_payload_ignore_les_champs_vides():
    ctx = _ctx()
    ctx.eval("__vals.sessObjectif=''; __vals.sessDuree='';")
    ctx.eval("window.__p = window.LogxSession._payload();")
    assert ctx.eval("'objectif' in window.__p") is False
    assert ctx.eval("'duree_min' in window.__p") is False


def test_rendre_affiche_le_plan():
    ctx = _ctx()
    ctx.eval("window.LogxSession._rendre({plan:'0-10 min : 20m FT8'});")
    assert ctx.eval("__plan.textContent") == '0-10 min : 20m FT8'
    assert ctx.eval("__plan._cls['sess-err']") in (False, None)


def test_rendre_affiche_erreur():
    ctx = _ctx()
    ctx.eval("window.LogxSession._rendre({error:'Clé API non configurée'});")
    assert 'Clé API' in ctx.eval("__plan.textContent")
    assert ctx.eval("__plan._cls['sess-err']") is True


def test_sauver_puis_restaurer_les_contraintes():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      var window = {};
      var __store = {};
      window.localStorage = { getItem:function(k){ return (k in __store)?__store[k]:null; },
                              setItem:function(k,v){ __store[k]=v; } };
      var __els = { sessDuree:{value:'45'}, sessObjectif:{value:'WAS'}, sessMode:{value:'CW'},
                    sessBandes:{value:'40m'}, sessPuissance:{value:'5'}, sessContexte:{checked:false} };
      var document = { getElementById:function(id){ return __els[id]||null; },
                       readyState:'complete', addEventListener:function(){} };
    """)
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    ctx.eval("window.LogxSession._sauver();")
    # l'opérateur change tout, puis on restaure -> les valeurs SAUVÉES reviennent
    ctx.eval("__els.sessDuree.value='999'; __els.sessObjectif.value='X'; __els.sessContexte.checked=true;")
    ctx.eval("window.LogxSession._restaurer();")
    assert ctx.eval("__els.sessDuree.value") == '45'
    assert ctx.eval("__els.sessObjectif.value") == 'WAS'
    assert ctx.eval("__els.sessMode.value") == 'CW'
    assert ctx.eval("__els.sessContexte.checked") is False


def test_cablage_page():
    with open(os.path.join(CONCOURS, 'logx_session.html'), encoding='utf-8') as f:
        h = f.read()
    assert 'src="logx_session.js"' in h
    assert 'id="sessPlan"' in h
    assert 'LogxSession.generer' in h
    assert 'logx_theme.css' in h and 'logx_statusbar.js' in h
