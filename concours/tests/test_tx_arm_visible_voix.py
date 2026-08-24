# -*- coding: utf-8 -*-
"""Interrupteur maître TX atteignable quand la VOIX est possible (24/08/2026).

Le garde-fou serveur exige désormais `armed` pour la voix. Un opérateur voix
SANS CW (DVK par VOX, pas de CAT ni WinKeyer) doit donc quand même pouvoir ARMER
— sinon sa voix est bloquée à jamais (régression). Le panneau qui porte le bouton
d'armement (#cwStopPanel) doit s'afficher dès que le keyer vocal est activé, pas
seulement quand un pilote CW est disponible. Le bouton STOP CW, lui, reste
spécifique au CW (masqué en voix-seule).

Exécuté en V8 (py_mini_racer) avec un stub localStorage."""
import os

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer', reason='py_mini_racer absent')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_hardware_cat.js')

_PREAMBLE = r"""
var __panels = {};
function ElProxy(id){
  var s = {style:{display:''}, textContent:''};
  var cls = { toggle:function(){}, add:function(){}, remove:function(){}, contains:function(){return false;} };
  __panels[id] = s;
  return new Proxy({}, { get:function(t,p){
                            if(p==='style') return s.style;
                            if(p==='classList') return cls;
                            if(p==='setAttribute' || p==='getAttribute') return function(){};
                            return s[p];
                          },
                          set:function(t,p,v){ s[p]=v; return true; } });
}
var document = { readyState: 'loading', addEventListener: function(){},
                 getElementById: function(id){ return __panels[id] || (__panels[id]=ElProxy(id)); } };
var __store = {};
var localStorage = { getItem:function(k){ return (k in __store) ? __store[k] : null; },
                     setItem:function(k,v){ __store[k]=String(v); } };
"""


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_PREAMBLE)
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_panneau_visible_si_keyer_vocal_actif_sans_cw():
    ctx = _ctx()
    # pas de CAT ni WinKeyer, mais keyer vocal activé en config
    ctx.eval("localStorage.setItem('logx_config', JSON.stringify({voicekeyer_enabled: 1}));")
    ctx.eval("updateCwStopBtn();")
    assert ctx.eval("cwPiloteDisponible()") is False
    assert ctx.eval("document.getElementById('cwStopPanel').style.display") == 'block'


def test_panneau_cache_si_ni_cw_ni_voix():
    ctx = _ctx()
    ctx.eval("updateCwStopBtn();")
    assert ctx.eval("document.getElementById('cwStopPanel').style.display") == 'none'


def test_stop_cw_masque_en_voix_seule():
    # STOP CW est spécifique au CW : masqué quand seul le keyer vocal est actif.
    ctx = _ctx()
    ctx.eval("localStorage.setItem('logx_config', JSON.stringify({voicekeyer_enabled: 1}));")
    ctx.eval("updateCwStopBtn();")
    assert ctx.eval("document.getElementById('cwStopBtn').style.display") == 'none'


def test_stop_cw_visible_avec_pilote_cw():
    ctx = _ctx()
    ctx.eval("winkeyerState.enabled = true;")
    ctx.eval("updateCwStopBtn();")
    assert ctx.eval("document.getElementById('cwStopBtn').style.display") != 'none'
