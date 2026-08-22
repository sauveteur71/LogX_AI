# -*- coding: utf-8 -*-
"""Page d'accueil par activité (concours/logx_accueil.js), chantier « axe =
activité, pas mode déclaré » (CLAUDE.md, 22/08/2026) : résumé en un geste
(localStorage.logx_activity) et choix de la page suivante (CONFIG si aucun
concours actif, LOGBOOK sinon) -- « ne pas rallonger le chemin quotidien ».

Exécute le VRAI logx_accueil.js dans un moteur JS réel (V8 via py_mini_racer)."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_accueil.js')

_DOM_PREAMBLE = r"""
var __store = {};
var __redirected = null;
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:''};
  return new Proxy({}, {
    get:function(target, prop){ return s[prop]; },
    set:function(target, prop, val){ s[prop] = val; return true; }
  });
}
var document = {
  getElementById: function(id){ if(!__store[id]) __store[id] = ElProxy(); return __store[id]; },
};
var location = { href:'', search:'' };
Object.defineProperty(location, 'href', {
  get: function(){ return this._href || ''; },
  set: function(v){ this._href = v; __redirected = v; }
});
var window = { location: location };
var localStorage = {
  _d:{}, getItem:function(k){ return (k in this._d)? this._d[k] : null; },
  setItem:function(k,v){ this._d[k]=String(v); }, removeItem:function(k){ delete this._d[k]; }
};
function URLSearchParams(qs){
  var params = {};
  String(qs||'').replace(/^\?/, '').split('&').forEach(function(pair){
    if(!pair) return;
    var kv = pair.split('=');
    params[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1]||'');
  });
  return { get: function(k){ return (k in params) ? params[k] : null; } };
}
"""


def _make_ctx(search=''):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval("location.search = %r;" % search)
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_premiere_visite_affiche_la_grille_pas_de_redirection():
    ctx = _make_ctx()
    assert ctx.eval('__redirected') is None
    assert ctx.eval("document.getElementById('intro').innerHTML").find('activity-grid') >= 0


def test_choisir_vuhf_pose_la_cle_et_redirige_vers_config_sans_concours():
    ctx = _make_ctx()
    ctx.eval("choisirActivite('vuhf');")
    assert ctx.eval("localStorage.getItem('logx_activity')") == 'vuhf'
    assert ctx.eval('__redirected') == 'logx_configuration.html'


def test_choisir_vuhf_redirige_vers_logbook_si_concours_deja_actif():
    ctx = _make_ctx()
    ctx.eval("localStorage.setItem('logx_config', JSON.stringify({contest:'REF_CCD_JAN1'}));")
    ctx.eval("choisirActivite('vuhf');")
    assert ctx.eval('__redirected') == 'logx_logbook.html'


def test_deuxieme_visite_redirige_directement_sans_montrer_la_grille():
    """Résumé en un geste : l'activité déjà choisie ne doit plus jamais
    ralentir l'habitué avec la grille de tuiles."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval("localStorage.setItem('logx_activity', 'vuhf');")
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    assert ctx.eval('__redirected') == 'logx_configuration.html'


def test_parametre_changer_force_le_reaffichage_de_la_grille():
    """Échappatoire explicite (lien « ↺ ACTIVITÉ » ajouté dans CONFIG) --
    masquer ≠ bloquer l'accès, même une fois l'activité mémorisée."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval("localStorage.setItem('logx_activity', 'vuhf');")
    ctx.eval("location.search = '?changer=1';")
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    assert ctx.eval('__redirected') is None
    assert ctx.eval("document.getElementById('intro').innerHTML").find('activity-grid') >= 0
