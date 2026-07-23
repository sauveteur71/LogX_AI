# -*- coding: utf-8 -*-
"""Waterfall du bandmap (commit 3ab2986) — drawWaterfallRow() ne vidait le
canvas QUE si `rng` est falsy (bande absente de la table _BM_RANGE), ce qui
n'arrive quasiment jamais : la quasi-totalité des bandes couvertes ont un rng
défini. Résultat concret : changer de bande alors que le waterfall est
affiché empilait les nouveaux spots PAR-DESSUS l'historique de l'ancienne
bande au lieu de repartir à zéro — impossible de voir QUAND la nouvelle bande
s'est ouverte, tout l'intérêt du waterfall.

Ce module exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via
py_mini_racer, même technique que tests/test_logbook_render_window_reset.py
et tests/test_qtc_panel_js.py), avec un DOM minimal incluant un faux contexte
canvas 2D qui trace les appels clearRect/drawImage/fillRect, pour reproduire
le scénario concrètement plutôt que de grepper une chaîne dans le fichier."""
import os
import subprocess

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')

# ─── DOM minimal (voir tests/test_logbook_render_window_reset.py pour la
# version commentée) + faux canvas 2D : getContext('2d') renvoie un objet qui
# compte ses appels sur l'ÉLÉMENT lui-même (s.__fullClearCalls etc.), pour
# distinguer un clearRect(0,0,w,h) — nettoyage COMPLET du canvas — d'un
# clearRect(0,0,w,1) — qui ne peint que la nouvelle ligne du haut à chaque
# tick normal du waterfall, sans toucher à l'historique. ─────────────────────
_DOM_PREAMBLE = r"""
var __store = {};
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:'', style:{}, checked:false, disabled:false, files:[], children:[],
           width:200, height:80, __fullClearCalls:0, __clearCalls:0, __drawImageCalls:0, __fillRectCalls:0};
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
      if(prop === 'getContext') return function(){
        if(!s.__ctx){
          s.__ctx = { fillStyle:'',
            clearRect:function(x,y,w,h){
              s.__clearCalls++;
              if(x===0 && y===0 && w===s.width && h===s.height) s.__fullClearCalls++;
            },
            drawImage:function(){ s.__drawImageCalls++; },
            fillRect:function(){ s.__fillRectCalls++; }
          };
        }
        return s.__ctx;
      };
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
function getComputedStyle(){ return { getPropertyValue: function(){ return ''; } }; }
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


def _real_source(rev=None):
    """Source réelle de logx_logbook.js : HEAD par défaut, ou `rev` (ex. le
    commit 3ab2986) pour rejouer le scénario tel qu'il était AVANT ce fix."""
    if rev is None:
        with open(JS_PATH, encoding='utf-8') as f:
            return f.read()
    out = subprocess.run(
        ['git', 'show', f'{rev}:concours/logx_logbook.js'],
        cwd=BASE, capture_output=True, text=True, encoding='utf-8', check=True)
    return out.stdout


def _make_ctx(rev=None):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_real_source(rev))
    return ctx


# Un même petit scénario, joué sur l'ancien commit puis sur le code actuel :
# waterfall affiché sur 14 MHz (3 lignes dessinées, aucune ne doit clear tout
# le canvas au-delà de la toute première), PUIS bascule sur 432 MHz (1 ligne).
# La question testée : la bascule de bande a-t-elle déclenché un nettoyage
# COMPLET du canvas (clearRect(0,0,w,h)) ? C'est la seule façon de purger
# l'historique de l'ancienne bande avant d'empiler celui de la nouvelle.
_SCENARIO = r"""
toggleWaterfall();   // _wfShown = true
currentBand = '14';
drawWaterfallRow([{call:'F4AAA',freq:14.195,priority:3,new_mult:false,already_done:false}], _BM_RANGE['14']);
drawWaterfallRow([{call:'F4BBB',freq:14.205,priority:2,new_mult:false,already_done:false}], _BM_RANGE['14']);
drawWaterfallRow([{call:'F4CCC',freq:14.210,priority:1,new_mult:true, already_done:false}], _BM_RANGE['14']);
var __before = document.getElementById('bandWaterfall').__fullClearCalls;
currentBand = '432';
drawWaterfallRow([{call:'F4DXX',freq:432.100,priority:3,new_mult:false,already_done:false}], _BM_RANGE['432']);
var __after = document.getElementById('bandWaterfall').__fullClearCalls;
"""


def test_reproduction_bug_sur_3ab2986_pas_de_clear_au_changement_de_bande():
    """Sur le commit d'origine, changer de bande (14 -> 432, toutes deux avec
    un rng défini dans _BM_RANGE) NE déclenche AUCUN nettoyage complet du
    canvas : l'historique de 14 MHz reste visible, mélangé à 432 MHz."""
    ctx = _make_ctx(rev='3ab2986')
    ctx.eval(_SCENARIO)
    before = ctx.eval('__before')
    after = ctx.eval('__after')
    # Le bug : la bascule de bande n'a provoqué aucun clearRect(0,0,w,h) de plus.
    assert after == before


def test_changement_de_bande_vide_le_canvas_waterfall():
    """Sur le code actuel : la bascule de bande DOIT déclencher un nettoyage
    complet du canvas (l'historique de l'ancienne bande ne doit pas persister)."""
    ctx = _make_ctx()
    ctx.eval(_SCENARIO)
    before = ctx.eval('__before')
    after = ctx.eval('__after')
    assert after == before + 1


def test_meme_bande_repetee_ne_vide_pas_le_canvas():
    """Non-régression : rester sur la MÊME bande ne doit PAS déclencher de
    nettoyage complet à chaque tick, sinon le waterfall ne montrerait plus
    jamais d'historique (toute sa raison d'être)."""
    ctx = _make_ctx()
    ctx.eval("""
    toggleWaterfall();
    currentBand = '14';
    drawWaterfallRow([{call:'F4AAA',freq:14.195,priority:3,new_mult:false,already_done:false}], _BM_RANGE['14']);
    var __afterFirst = document.getElementById('bandWaterfall').__fullClearCalls;
    drawWaterfallRow([{call:'F4BBB',freq:14.205,priority:2,new_mult:false,already_done:false}], _BM_RANGE['14']);
    drawWaterfallRow([{call:'F4CCC',freq:14.210,priority:1,new_mult:true, already_done:false}], _BM_RANGE['14']);
    var __afterMore = document.getElementById('bandWaterfall').__fullClearCalls;
    """)
    assert ctx.eval('__afterMore') == ctx.eval('__afterFirst')


def test_changement_de_bande_pendant_que_le_waterfall_est_masque():
    """Le changement de bande doit être pris en compte même si le waterfall
    est masqué (toggle OFF) au moment du changement : sans quoi, en le
    réaffichant ensuite, l'historique de l'ancienne bande resurgirait tel
    quel (le canvas n'est alors jamais retouché tant qu'il reste caché)."""
    ctx = _make_ctx()
    ctx.eval("""
    // Waterfall affiché, on peint sur 14 MHz.
    toggleWaterfall();
    currentBand = '14';
    drawWaterfallRow([{call:'F4AAA',freq:14.195,priority:3,new_mult:false,already_done:false}], _BM_RANGE['14']);
    // On le masque, PUIS on change de bande pendant qu'il est caché.
    toggleWaterfall();   // _wfShown = false
    currentBand = '432';
    drawWaterfallRow([{call:'F4DXX',freq:432.100,priority:3,new_mult:false,already_done:false}], _BM_RANGE['432']);
    var __hiddenClearCalls = document.getElementById('bandWaterfall').__fullClearCalls;
    """)
    assert ctx.eval('__hiddenClearCalls') >= 1


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    with open(JS_PATH, encoding='utf-8') as f:
        assert 'QSO Director' not in f.read()
