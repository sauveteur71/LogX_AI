# -*- coding: utf-8 -*-
"""RST : le rapport doit s'adapter au mode sélectionné.

Bug réel signalé par F4GLD (14/08/2026) : le champ RST restait figé sur
« 59 » (2 chiffres, phonie) quel que soit le mode choisi — en CW, le rapport
officiel est à 3 chiffres (R + S + TONALITÉ, ex. « 599 »). inputRSTsent/
inputRSTrcvd avaient bien maxlength=3 (l'opérateur pouvait taper le 3e
chiffre à la main), mais rien dans le logiciel ne proposait/appliquait
automatiquement ce format par défaut.

Ce module exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via
py_mini_racer) avec un DOM minimal — même approche que
test_edit_qso_mode_hors_concours.py."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')
VOICE_KEYER_JS_PATH = os.path.join(BASE, 'logx_voice_keyer.js')
EDIT_QSO_JS_PATH = os.path.join(BASE, 'logx_edit_qso.js')
FILTRE_SPOTS_JS_PATH = os.path.join(BASE, 'logx_filtre_spots.js')

# DOM minimal — copié de test_edit_qso_mode_hors_concours.py (même besoin :
# un Proxy générique pour n'importe quel élément DOM lu/écrit par le script).
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
    with open(EDIT_QSO_JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(FILTRE_SPOTS_JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def _set_rst(ctx, sent, rcvd):
    ctx.eval("document.getElementById('inputRSTsent').value = %r;" % sent)
    ctx.eval("document.getElementById('inputRSTrcvd').value = %r;" % rcvd)


def test_rst_par_defaut_cw_est_a_3_chiffres(moteur):
    assert moteur.eval("_rstParDefaut('CW')") == '599'


def test_rst_par_defaut_ssb_reste_a_2_chiffres(moteur):
    assert moteur.eval("_rstParDefaut('SSB')") == '59'


@pytest.mark.parametrize('mode', ['CW', 'RTTY', 'FT8', 'FT4', 'PSK'])
def test_modes_non_phoniques_veulent_3_chiffres(moteur, mode):
    assert moteur.eval("_rstParDefaut(%r)" % mode) == '599'


@pytest.mark.parametrize('mode', ['SSB', 'FM', 'AM'])
def test_modes_phoniques_restent_a_2_chiffres(moteur, mode):
    assert moteur.eval("_rstParDefaut(%r)" % mode) == '59'


def test_pickMode_cw_adapte_le_rst_encore_par_defaut(moteur):
    """Passage SSB -> CW via le sélecteur de mode : le champ, encore sur sa
    valeur par défaut « 59 », doit passer à « 599 »."""
    _set_rst(moteur, '59', '59')
    moteur.eval("pickMode('CW')")
    assert moteur.eval("document.getElementById('inputRSTsent').value") == '599'
    assert moteur.eval("document.getElementById('inputRSTrcvd').value") == '599'


def test_pickMode_ne_touche_jamais_un_rapport_deja_saisi(moteur):
    """Un rapport que l'opérateur a déjà personnalisé (ex. « 57 » — signal
    plus faible) ne doit JAMAIS être écrasé par un changement de mode."""
    _set_rst(moteur, '57', '43')
    moteur.eval("pickMode('CW')")
    assert moteur.eval("document.getElementById('inputRSTsent').value") == '57'
    assert moteur.eval("document.getElementById('inputRSTrcvd').value") == '43'


def test_pickMode_ssb_apres_cw_revient_a_2_chiffres(moteur):
    _set_rst(moteur, '599', '599')
    moteur.eval("pickMode('SSB')")
    assert moteur.eval("document.getElementById('inputRSTsent').value") == '59'
    assert moteur.eval("document.getElementById('inputRSTrcvd').value") == '59'
