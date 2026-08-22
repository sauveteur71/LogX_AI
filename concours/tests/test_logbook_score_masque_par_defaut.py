# -*- coding: utf-8 -*-
"""Score masqué par défaut hors concours, affiché sur demande (retour F4GLD
22/08/2026 : « afin d'épurer au maximum les pages tout ce qui est scoring
doit apparaître uniquement sur demande » -- chantier « page d'accueil par
activité »).

Précédent réutilisé, pas réinventé : bandeauxRythmeMasques() (logx_logbook.js)
cachait déjà .score-banner en entier pour les modes 'simple'/'expedition'.
Ce module vérifie l'extension : hors concours actif (contestActif() faux),
le bandeau reste masqué par défaut, sur demande sinon via
#scoreVisibleToggle/toggleScoreVisible()/logx_score_visible — sans jamais
toucher le comportement existant en concours actif ou en mode simple/expedition.

Exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via py_mini_racer),
même harnais DOM que tests/test_dup_confirm_banner.py."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
RULES_JS_PATH = os.path.join(BASE, 'logx_contest_rules.js')
QTC_JS_PATH = os.path.join(BASE, 'logx_qtc.js')
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')
VOICE_KEYER_JS_PATH = os.path.join(BASE, 'logx_voice_keyer.js')
FILTRE_SPOTS_JS_PATH = os.path.join(BASE, 'logx_filtre_spots.js')

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
    for path in (RULES_JS_PATH, QTC_JS_PATH, ESM_CALLBOT_JS_PATH, VOICE_KEYER_JS_PATH, FILTRE_SPOTS_JS_PATH, JS_PATH):
        with open(path, encoding='utf-8') as f:
            ctx.eval(f.read())
    return ctx


def test_masque_par_defaut_sans_concours_actif():
    ctx = _make_ctx()
    assert ctx.eval('bandeauxRythmeMasques()') is True


def test_affiche_sur_demande_sans_concours_actif():
    ctx = _make_ctx()
    ctx.eval("toggleScoreVisible();")
    assert ctx.eval('_scoreDemandee()') is True
    assert ctx.eval('bandeauxRythmeMasques()') is False


def test_toggle_est_reversible():
    ctx = _make_ctx()
    ctx.eval("toggleScoreVisible(); toggleScoreVisible();")
    assert ctx.eval('_scoreDemandee()') is False
    assert ctx.eval('bandeauxRythmeMasques()') is True


def test_concours_actif_affiche_le_score_meme_sans_demande_explicite():
    """Un concours réellement en cours ne doit JAMAIS voir son score caché
    par défaut -- le nouveau masquage ne s'applique qu'en l'ABSENCE de
    concours, jamais pendant un concours actif (contexte où le score est le
    coeur de l'usage)."""
    ctx = _make_ctx()
    ctx.eval("localStorage.setItem('logx_config', JSON.stringify({contest:'REF_CCD_JAN1'}));")
    assert ctx.eval('contestActif()') is True
    assert ctx.eval('bandeauxRythmeMasques()') is False


def test_mode_simple_reste_masque_meme_score_demande():
    """Non-régression du mécanisme existant : le mode simple/expedition
    masque le bandeau indépendamment de logx_score_visible -- une demande
    explicite de score n'a pas de sens dans ce mode (log personnel continu)."""
    ctx = _make_ctx()
    ctx.eval("toggleScoreVisible();")   # demande explicite
    ctx.eval("applyUsageModeToLogbook('simple');")
    assert ctx.eval('bandeauxRythmeMasques()') is True


def test_bouton_masque_pendant_un_concours_actif():
    """Rien à révéler pendant un concours actif : le bouton lui-même
    disparaît plutôt que de proposer une action sans effet."""
    ctx = _make_ctx()
    ctx.eval("localStorage.setItem('logx_config', JSON.stringify({contest:'REF_CCD_JAN1'}));")
    ctx.eval("applyContestActifToLogbook();")
    assert ctx.eval("document.getElementById('scoreVisibleToggle').style.display") == 'none'


def test_bouton_visible_et_reflete_letat_hors_concours():
    ctx = _make_ctx()
    ctx.eval("applyContestActifToLogbook();")
    assert ctx.eval("document.getElementById('scoreVisibleToggle').style.display") == ''
    assert '○' in ctx.eval("document.getElementById('scoreVisibleToggle').textContent")
    ctx.eval("toggleScoreVisible();")
    assert '●' in ctx.eval("document.getElementById('scoreVisibleToggle').textContent")
