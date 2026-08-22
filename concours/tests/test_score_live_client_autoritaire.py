# -*- coding: utf-8 -*-
"""A10 (docs/FEUILLE_DE_ROUTE.md) : le score affiché en direct côté client
(logx_logbook.js:updateStats(), zone #sbTotal du statusbar) sommait juste
les points par QSO -- jamais multiplié par le compte de multiplicateurs,
exactement le même défaut que les chemins serveur (voir
tests/test_calc_total_score.py). Corrigé en préférant le score AUTORITAIRE
reçu au dernier /log/list (_lastServerScore) dès qu'il est connu.

Exécute le VRAI logx_logbook.js (V8 réel, py_mini_racer), même patron que
tests/test_qso_champs_obligatoires.py (repris pour rester indépendant)."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
RULES_JS_PATH = os.path.join(BASE, 'logx_contest_rules.js')
HARDWARE_JS_PATH = os.path.join(BASE, 'logx_hardware_cat.js')
DXCC_JS_PATH = os.path.join(BASE, 'logx_dxcc_lookup.js')
CALLBOOK_JS_PATH = os.path.join(BASE, 'logx_callbook.js')
LOOKUP_JS_PATH = os.path.join(BASE, 'logx_lookup.js')
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')
VOICE_KEYER_JS_PATH = os.path.join(BASE, 'logx_voice_keyer.js')
LOCATOR_REVERSE_JS_PATH = os.path.join(BASE, 'logx_locator_reverse.js')
MACROS_JS_PATH = os.path.join(BASE, 'logx_macros.js')
FILTRE_SPOTS_JS_PATH = os.path.join(BASE, 'logx_filtre_spots.js')
OUTILS_DIVERS_JS_PATH = os.path.join(BASE, 'logx_outils_divers.js')

_DOM_PREAMBLE = r"""
var __store = {};
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:'', title:'', style:{}, checked:false, disabled:false, files:[], children:[]};
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
      if(prop === 'closest') return function(){ return ElProxy(); };
      if(prop === 'contains') return function(){ return false; };
      if(prop === 'focus') return function(){};
      if(prop === 'select') return function(){};
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
var console = {log:function(){}, warn:function(){}, error:function(){}, info:function(){}, debug:function(){}};
function setInterval(){ return 0; }
function setTimeout(){ return 0; }
function clearInterval(){}
function clearTimeout(){}
var localStorage = {
  _d:{}, getItem:function(k){ return (k in this._d)? this._d[k] : null; },
  setItem:function(k,v){ this._d[k]=String(v); }, removeItem:function(k){ delete this._d[k]; }
};
function fetch(){ return Promise.resolve({ ok:false, status:0, json: function(){ return Promise.resolve({}); } }); }
function alert(){}
function confirm(){ return false; }
function prompt(){ return null; }
var navigator = { userAgent:'test', mediaDevices: { enumerateDevices: function(){ return Promise.resolve([]); } },
                  clipboard:{ writeText:function(){ return Promise.resolve(); } } };
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


def _real_source():
    parts = []
    for path in (RULES_JS_PATH, HARDWARE_JS_PATH, DXCC_JS_PATH, CALLBOOK_JS_PATH, LOOKUP_JS_PATH, ESM_CALLBOT_JS_PATH,
                 VOICE_KEYER_JS_PATH, LOCATOR_REVERSE_JS_PATH, MACROS_JS_PATH,
                 FILTRE_SPOTS_JS_PATH, OUTILS_DIVERS_JS_PATH, JS_PATH):
        with open(path, encoding='utf-8') as f:
            parts.append(f.read())
    return '\n'.join(parts)


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_real_source())
    ctx.eval("myCall = 'F4TEST'; myLocator = 'JN18CX'; usageMode = 'contest'; currentContest = 'CQ_WW_SSB';")
    return ctx


def test_updateStats_prefere_le_score_serveur_autoritaire():
    """Le coeur du défaut : 2 QSO à 3 pts chacun (somme locale = 6) mais le
    serveur (seul à connaître le VRAI compte de multiplicateurs) a annoncé
    24 -- c'est 24 qui doit s'afficher, pas 6."""
    ctx = _make_ctx()
    ctx.eval("""
    qsoLog = [
      {call:'K1ABC', band:'14', mode:'SSB', points:3, locator:'', date:'20260101', time:'1200'},
      {call:'DL1ABC', band:'21', mode:'SSB', points:3, locator:'', date:'20260101', time:'1201'}
    ];
    _lastServerScore = 24;
    updateStats();
    """)
    assert ctx.eval("document.getElementById('sbTotal').textContent") == '24 pts'


def test_updateStats_replie_sur_le_calcul_local_si_jamais_de_reponse_serveur():
    """Avant le tout premier /log/list (page tout juste ouverte, ou
    hors-ligne) : _lastServerScore est encore null -- repli sur le calcul
    local, mieux qu'un score vide ou à zéro."""
    ctx = _make_ctx()
    ctx.eval("""
    qsoLog = [{call:'K1ABC', band:'14', mode:'SSB', points:3, locator:'', date:'20260101', time:'1200'}];
    _lastServerScore = null;
    updateStats();
    """)
    assert ctx.eval("document.getElementById('sbTotal').textContent") == '3 pts'
