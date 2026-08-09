# -*- coding: utf-8 -*-
"""Panneau QTC (WAE) côté client (commit 5a98e7a) — showQTCPanel()/
saveQTCSeries() ne réinitialisaient jamais #qtcPartner ni #qtcDirection
entre deux séries : un opérateur qui enregistre une série ÉMISE à DL0XM,
puis rouvre le panneau pour une série REÇUE d'une autre station, retrouvait
encore l'indicatif ET le sens de la série précédente pré-remplis — au risque
de logguer la série suivante sous le mauvais indicatif/sens par inattention.

Ce module exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via
py_mini_racer, même technique que tests/test_logbook_render_window_reset.py)
avec un DOM minimal, pour reproduire le scénario concrètement plutôt que de
grepper une chaîne dans le fichier source."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
# EV-7 : showQTCPanel()/closeQTCPanel()/saveQTCSeries() ont été extraites
# vers ce fichier -- doit être chargé AVANT logx_logbook.js, même convention
# que tests/test_cw_panel_consolidation.py.
QTC_JS_PATH = os.path.join(BASE, 'logx_qtc.js')
# EV-7 19e incrément : appel TOP-LEVEL renderVoiceDynPanel() dans
# logx_logbook.js -- ReferenceError au parse sans ce fichier chargé avant.
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')
# EV-7 20e incrément : appel TOP-LEVEL voiceRefreshSlots() dans
# logx_logbook.js -- même piège que renderVoiceDynPanel() (19e incrément).
VOICE_KEYER_JS_PATH = os.path.join(BASE, 'logx_voice_keyer.js')
# EV-7 33e incrément : appel TOP-LEVEL setInterval(refreshBandMap,...) dans
# logx_logbook.js -- ReferenceError au parse sans ce fichier chargé avant.
FILTRE_SPOTS_JS_PATH = os.path.join(BASE, 'logx_filtre_spots.js')

# ─── DOM minimal (voir tests/test_logbook_render_window_reset.py pour la
# version commentée/complète de ce Proxy — copie volontairement réduite ici
# aux besoins du panneau QTC pour garder ce module indépendant) ──────────────
_DOM_PREAMBLE = r"""
var __store = {};
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:'', style:{}, checked:false, disabled:false, files:[], children:[]};
  var cls = {_s:new Set(), add:function(){for(var i=0;i<arguments.length;i++) this._s.add(arguments[i]);},
             remove:function(){for(var i=0;i<arguments.length;i++) this._s.delete(arguments[i]);},
             contains:function(c){return this._s.has(c);},
             toggle:function(c){ if(this._s.has(c)) this._s.delete(c); else this._s.add(c); return this._s.has(c);}};
  var handler = {
    get:function(target, prop){
      if(prop === 'classList') return cls;
      if(prop === 'style') return s.style;
      if(prop === 'dataset') return (s.dataset = s.dataset || {});
      if(prop === 'addEventListener') return function(){};
      if(prop === 'removeEventListener') return function(){};
      if(prop === 'appendChild') return function(c){ s.children.push(c); return c; };
      if(prop === 'insertBefore') return function(c){ s.children.unshift(c); return c; };
      if(prop === 'removeChild') return function(c){ var i=s.children.indexOf(c); if(i>=0) s.children.splice(i,1); };
      if(prop === 'querySelector') return function(){ return ElProxy(); };
      if(prop === 'querySelectorAll') return function(){ return []; };
      if(prop === 'focus') return function(){};
      if(prop === 'click') return function(){};
      if(prop === 'getContext') return function(){ return null; };
      if(prop === 'getBoundingClientRect') return function(){ return {top:0,left:0,width:0,height:0,bottom:0,right:0}; };
      if(prop === 'setAttribute') return function(){};
      if(prop === 'getAttribute') return function(){ return null; };
      if(prop === 'remove') return function(){};
      if(prop === 'scrollIntoView') return function(){};
      return s[prop];
    },
    set:function(target, prop, val){ s[prop] = val; return true; }
  };
  return new Proxy({}, handler);
}
var document = {
  getElementById: function(id){ if(!__store[id]) __store[id] = ElProxy(); return __store[id]; },
  addEventListener: function(){}, removeEventListener: function(){},
  createElement: function(){ return ElProxy(); },
  querySelectorAll: function(){ return []; },
  querySelector: function(){ return ElProxy(); },
  body: ElProxy(), documentElement: ElProxy(),
};
var window = this;
window.addEventListener = function(){};
window.removeEventListener = function(){};
function setInterval(){ return 0; }
function setTimeout(){ return 0; }
function clearInterval(){}
function clearTimeout(){}
var localStorage = {
  _d:{}, getItem:function(k){ return (k in this._d)? this._d[k] : null; },
  setItem:function(k,v){ this._d[k]=String(v); }, removeItem:function(k){ delete this._d[k]; }
};
function fetch(){ return Promise.resolve({ ok:false, json: function(){ return Promise.resolve({}); } }); }
function alert(){}
function confirm(){ return false; }
function prompt(){ return null; }
var navigator = { userAgent:'test', mediaDevices: { enumerateDevices: function(){ return Promise.resolve([]); } }, clipboard:{} };
var location = { protocol:'http:', hostname:'127.0.0.1', href:'http://127.0.0.1/', search:'', reload:function(){} };
window.location = location;
function Notification(){}
Notification.permission = 'denied';
Notification.requestPermission = function(){ return Promise.resolve('denied'); };
function WebSocket(){ this.close = function(){}; }
function Blob(parts, opts){ this.parts = parts; }
window.URL = { createObjectURL:function(){ return 'blob:x'; }, revokeObjectURL:function(){} };
function Image(){ this.src = ''; }
function AudioContext(){}
function MediaRecorder(){}
var L = new Proxy({}, { get:function(){ return function(){ return new Proxy({}, {get:function(){ return function(){ return new Proxy({},{get:function(){ return function(){}; }}); }; }}); }; } });
"""


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    with open(QTC_JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(ESM_CALLBOT_JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(VOICE_KEYER_JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(FILTRE_SPOTS_JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_showQTCPanel_reinitialise_partenaire_et_sens():
    """Reproduction : ouvrir le panneau pour une 1e série (reçue, DL0XM) PUIS
    le rouvrir pour une 2e série doit repartir de zéro (sens 'sent',
    partenaire vide) — sans le fix, les deux champs restent sur DL0XM/'recv'."""
    ctx = _make_ctx()
    ctx.eval("""
    document.getElementById('qtcDirection').value = 'recv';
    document.getElementById('qtcPartner').value = 'DL0XM';
    """)
    # Rouvre le panneau (nouvelle série) : doit repartir à zéro.
    ctx.eval("showQTCPanel();")
    assert ctx.eval("document.getElementById('qtcPartner').value") == ''
    assert ctx.eval("document.getElementById('qtcDirection').value") == 'sent'


def test_closeQTCPanel_reinitialise_partenaire_et_sens():
    ctx = _make_ctx()
    ctx.eval("""
    document.getElementById('qtcDirection').value = 'recv';
    document.getElementById('qtcPartner').value = 'DL0XM';
    closeQTCPanel();
    """)
    assert ctx.eval("document.getElementById('qtcPartner').value") == ''
    assert ctx.eval("document.getElementById('qtcDirection').value") == 'sent'


def test_saveQTCSeries_reinitialise_partenaire_et_sens_apres_enregistrement():
    """Après un enregistrement RÉUSSI, la série SUIVANTE ne doit pas hériter
    de l'indicatif/sens de la précédente."""
    ctx = _make_ctx()
    ctx.eval("""
    fetch = function(){ return Promise.resolve({ ok:true, json:function(){
      return Promise.resolve({ok:true, total:1, id:1}); } }); };
    document.getElementById('qtcDirection').value = 'recv';
    document.getElementById('qtcPartner').value = 'DL0XM';
    document.getElementById('qtcRows').innerHTML = '';
    qtcRows = [{time:'0030', call:'YU1ZZ', nr:'62'}];
    """)
    ctx.eval("saveQTCSeries();")
    # saveQTCSeries() est async (attend le fetch) : laisser le microtask queue se vider.
    ctx.eval("undefined")
    assert ctx.eval("document.getElementById('qtcPartner').value") == ''
    assert ctx.eval("document.getElementById('qtcDirection').value") == 'sent'


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    with open(JS_PATH, encoding='utf-8') as f:
        assert 'QSO Director' not in f.read()
