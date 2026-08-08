# -*- coding: utf-8 -*-
"""editQSO() : le mode/la bande RÉELS du QSO doivent apparaître dans la
popup de correction, même s'ils ne font pas partie de la liste du concours
ACTUELLEMENT actif.

Bug réel signalé par F4GLD (05/08/2026, capture d'écran) : en éditant un
vieux QSO FT8 (13cm) pendant que REF_RPH est le concours actif —
CONTEST_MODES.REF_RPH = ['SSB','CW','FM'], pas de FT8 — la popup affichait
« SSB » au lieu de « FT8 ». Le rapport « -01 » (dB, format FT8) restait lui
correct ; ce n'était pas un bug de validation de rapport comme supposé au
premier abord, mais le SELECT MODE qui montrait la mauvaise valeur.

Cause : `editModeSel.innerHTML = contestModes.map(...)` ne crée une
<option> que pour les modes du concours actif — FT8 n'en fait pas partie
ici, donc aucune <option> n'a `selected`, et le navigateur retombe sur la
PREMIÈRE de la liste (SSB). Le filet `if(!editModeSel.value) ... = q.mode`
censé rattraper ce cas ne se déclenche JAMAIS : un <select> peuplé a
TOUJOURS une valeur (celle que le navigateur a choisie par défaut), donc
cette condition est du code mort. Même bug, même correctif, côté bande.

Ce module exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via
py_mini_racer) avec un DOM minimal — même approche que
test_macro_cw_serie_bande.py."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
# EV-7 19e incrément : appel TOP-LEVEL renderVoiceDynPanel() dans
# logx_logbook.js -- ReferenceError au parse sans ce fichier chargé avant.
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')
# EV-7 20e incrément : appel TOP-LEVEL voiceRefreshSlots() dans
# logx_logbook.js -- même piège que renderVoiceDynPanel() (19e incrément).
VOICE_KEYER_JS_PATH = os.path.join(BASE, 'logx_voice_keyer.js')

# DOM minimal — copié de test_macro_cw_serie_bande.py (même besoin : un
# Proxy générique pour n'importe quel élément DOM lu/écrit par le script).
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
      // Simule le comportement RÉEL d'un <select> : lire .innerHTML ne fait
      // rien de spécial, mais on veut que .value se comporte comme un vrai
      // navigateur (retombe sur la première <option> si aucune n'a
      // "selected") — voir le setter innerHTML plus bas.
      return s[prop];
    },
    set:function(target, prop, val){
      if(prop === 'innerHTML' && typeof val === 'string' && val.indexOf('<option') >= 0){
        s.innerHTML = val;
        var opts = val.match(/<option value="([^"]*)"( selected)?>/g) || [];
        var selected = null, first = null;
        opts.forEach(function(o){
          var m = o.match(/<option value="([^"]*)"( selected)?>/);
          if(!m) return;
          if(first === null) first = m[1];
          if(m[2]) selected = m[1];
        });
        s.value = (selected !== null) ? selected : (first !== null ? first : '');
        return true;
      }
      s[prop] = val; return true;
    }
  };
  return new Proxy({}, handler);
}
var document = {
  getElementById: function(id){ if(!__store[id]) __store[id] = ElProxy(); return __store[id]; },
  addEventListener: function(){}, removeEventListener: function(){},
  createElement: function(){ return ElProxy(); },
  querySelectorAll: function(){ return []; },
  querySelector: function(){ return ElProxy(); },
  dispatchEvent: function(){ return true; },
  body: ElProxy(), documentElement: ElProxy(),
};
// EV-7 phase 2 : editQSO() emet un CustomEvent('logx:qso-editing-opened')
// (voir logx_scan_qsl.js) -- ce stub minimal evite un ReferenceError, meme
// convention que tests/test_pastille_orage_cache_froid.py.
function CustomEvent(n, o){ this.type = n; this.detail = (o||{}).detail; }
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


@pytest.fixture(scope='module')
def moteur():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    with open(ESM_CALLBOT_JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(VOICE_KEYER_JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_mode_hors_concours_actif_reste_correct_a_l_edition(moteur):
    moteur.eval("""
    currentContest = 'REF_RPH';
    qsoLog = [{id: 42, call: 'F5ABC', date: '20260101', time: '1200',
               rst_sent: '-01', rst_rcvd: '+21', num_sent: '', num_rcvd: '',
               band: '2320', mode: 'FT8', locator: 'JN18AA'}];
    editQSO(42);
    """)
    mode = moteur.eval("document.getElementById('editMode').value")
    band = moteur.eval("document.getElementById('editBand').value")
    assert mode == 'FT8', f"attendu FT8, obtenu {mode!r} — REF_RPH ne liste pourtant pas FT8 dans CONTEST_MODES"
    assert band == '2320', f"attendu 2320 (13cm), obtenu {band!r}"


def test_mode_dans_le_concours_actif_reste_selectionne_normalement(moteur):
    """Non-régression : un QSO dont le mode/la bande SONT dans la liste du
    concours actif ne doit rien changer au comportement existant."""
    moteur.eval("""
    currentContest = 'REF_RPH';
    qsoLog = [{id: 43, call: 'F5DEF', date: '20260101', time: '1201',
               rst_sent: '59', rst_rcvd: '59', num_sent: '', num_rcvd: '',
               band: '432', mode: 'CW', locator: 'JN18AA'}];
    editQSO(43);
    """)
    mode = moteur.eval("document.getElementById('editMode').value")
    band = moteur.eval("document.getElementById('editBand').value")
    assert mode == 'CW'
    assert band == '432'


def test_liste_des_modes_contient_bien_toujours_ceux_du_concours(moteur):
    """La correction ne doit pas ÉCARTER les modes légitimes du concours —
    seulement ajouter celui du QSO s'il manque."""
    moteur.eval("""
    currentContest = 'REF_RPH';
    qsoLog = [{id: 44, call: 'F5GHI', date: '20260101', time: '1202',
               rst_sent: '-05', rst_rcvd: '+10', num_sent: '', num_rcvd: '',
               band: '1296', mode: 'FT8', locator: 'JN18AA'}];
    editQSO(44);
    """)
    html = moteur.eval("document.getElementById('editMode').innerHTML")
    for attendu in ('SSB', 'CW', 'FM', 'FT8'):
        assert attendu in html, f"{attendu} manquant dans la liste : {html}"
