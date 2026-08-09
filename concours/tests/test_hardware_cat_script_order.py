# -*- coding: utf-8 -*-
"""Non-régression : adaptivePoll() (logx_hardware_cat.js) doit démarrer une
fois TOUS les <script> de la page chargés, quel que soit le temps de
récupération réseau des fichiers restants.

Régression réelle trouvée le 09/08/2026 (vérification navigateur, campagne
EV-7) : ReferenceError: adaptivePoll is not defined, reproduit à 100% au
chargement de logx_logbook.html. Un correctif identique (DOMContentLoaded
au lieu de setTimeout(fn,0)) avait déjà été développé et validé le 08/08
(commit dc194d6) mais sur une branche jamais fusionnée — perdu quand
logx_hardware_cat.js a été régénéré par une extraction EV-7 ultérieure
repartant de l'ancien code.

`logx_hardware_cat.js` est chargé AVANT `logx_logbook.js` (convention EV-7,
même portée globale partagée) — `adaptivePoll()` n'est définie que dans ce
2e fichier. Ce test rejoue l'ordre RÉEL des <script> via DEUX ctx.eval()
py_mini_racer séparés (jamais concaténés en un seul appel : sinon toutes
les déclarations `function` seraient hoistées ensemble et le bug d'ordre
deviendrait invisible — même piège déjà documenté dans
chantier-ev7-radio-cat-2026-08-08.md), avec document.readyState='loading'
au moment du 1er eval (le pire cas : le document N'A PAS fini de charger,
donc le repli synchrone ne doit PAS se déclencher, et adaptivePoll() ne
doit être appelée qu'à l'événement DOMContentLoaded)."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARDWARE_CAT_JS_PATH = os.path.join(BASE, 'logx_hardware_cat.js')
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
# EV-7 19e/20e incréments : logx_logbook.js contient encore 2 appels
# TOP-LEVEL (renderVoiceDynPanel(); voiceRefreshSlots();) qui dépendent de
# ces 2 fichiers -- sans rapport avec CE test, mais ReferenceError au PARSE
# même de logx_logbook.js sans eux, avant que le test puisse commencer.
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')
VOICE_KEYER_JS_PATH = os.path.join(BASE, 'logx_voice_keyer.js')
# EV-7 33e incrément : appel TOP-LEVEL setInterval(refreshBandMap,...) dans
# logx_logbook.js -- même piège, ReferenceError au parse sans ce fichier.
FILTRE_SPOTS_JS_PATH = os.path.join(BASE, 'logx_filtre_spots.js')

# DOM minimal — dérivé de test_edit_qso_mode_hors_concours.py (même besoin :
# évaluer le VRAI logx_logbook.js en entier sans lever). Différences ici :
# document.readyState démarre à 'loading' (pire cas réaliste : le document
# n'a pas fini de se charger quand logx_hardware_cat.js s'exécute) et
# document.addEventListener capture les callbacks 'DOMContentLoaded' au lieu
# de les avaler silencieusement, pour pouvoir simuler l'événement ensuite.
# fetch() est une sonde qui compte ses appels (pas juste une réponse muette)
# pour prouver que refreshHardware() -- appelée par adaptivePoll() -- a
# RÉELLEMENT été invoquée, pas juste que rien n'a levé d'exception.
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
var __domReadyListeners = [];
var document = {
  readyState: 'loading',
  getElementById: function(id){ if(!__store[id]) __store[id] = ElProxy(); return __store[id]; },
  addEventListener: function(name, fn){ if(name === 'DOMContentLoaded') __domReadyListeners.push(fn); },
  removeEventListener: function(){},
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
var __fetchCalls = [];
function fetch(url){
  __fetchCalls.push(url);
  return Promise.resolve({ ok:false, status:0, json: function(){ return Promise.resolve({}); } });
}
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


@pytest.fixture
def moteur():
    """Reproduit l'ordre RÉEL des <script> : logx_hardware_cat.js d'abord
    (document.readyState='loading', le pire cas), puis logx_logbook.js —
    deux eval() distincts, jamais concaténés."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    with open(HARDWARE_CAT_JS_PATH, encoding='utf-8') as f:
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


def test_le_chargement_des_deux_scripts_ne_leve_aucune_erreur(moteur):
    """Le simple fait d'évaluer les deux fichiers dans le VRAI ordre, avec
    readyState='loading', ne doit lever aucune exception -- l'ancien code
    (setTimeout(fn,0)) ne levait pas non plus d'exception ici (le
    setTimeout stubbé à no-op masquait le bug), donc ce test seul ne
    suffit pas à prouver la régression corrigée : voir le test suivant."""
    assert moteur is not None


def test_adaptivePoll_demarre_reellement_apres_DOMContentLoaded(moteur):
    """Le cœur de la régression : logx_hardware_cat.js doit avoir enregistré
    UN écouteur DOMContentLoaded (pas appelé adaptivePoll() directement,
    puisque readyState='loading' au moment de son exécution). Simuler cet
    événement doit ensuite déclencher un VRAI appel réseau via
    refreshHardware() -- pas juste l'absence d'exception."""
    n_listeners = moteur.eval('__domReadyListeners.length')
    assert n_listeners >= 1, (
        "logx_hardware_cat.js n'a enregistré aucun écouteur DOMContentLoaded "
        "alors que document.readyState valait 'loading' à son exécution -- "
        "a-t-il régressé vers un setTimeout(fn,0) ou un appel direct ?")

    # Vérifie /hardware/state spécifiquement (pas juste "fetch a été appelé
    # au moins une fois") : d'autres <script> chargés dans le même contexte
    # (logx_logbook.js, logx_esm_callbot.js...) font leurs propres appels
    # fetch() top-level SANS RAPPORT avec adaptivePoll -- déjà observé ici,
    # pas un défaut de ce correctif.
    def _hardware_state_deja_appele():
        return moteur.eval("__fetchCalls.indexOf('/hardware/state') !== -1")

    assert not _hardware_state_deja_appele(), (
        "fetch('/hardware/state') a été appelé AVANT l'événement "
        "DOMContentLoaded -- adaptivePoll() a-t-elle démarré trop tôt ?")

    # Simule le navigateur qui a fini de parser TOUT le document (tous les
    # <script> classiques exécutés) : ne déclenche QUE le 1er écouteur
    # capturé (celui de logx_hardware_cat.js, enregistré avant tout écouteur
    # propre à logx_logbook.js s'il en existe un).
    moteur.eval('__domReadyListeners[0]()')

    assert _hardware_state_deja_appele(), (
        "adaptivePoll(refreshHardware, ...) n'a déclenché aucun appel "
        "fetch('/hardware/state') après l'événement DOMContentLoaded -- "
        "adaptivePoll() est-elle restée introuvable (ReferenceError avalée) ?")

# Note : pas de test dédié au repli synchrone (readyState !== 'loading' au
# moment de l'exécution de logx_hardware_cat.js) -- dans CETTE page, ce
# fichier est TOUJOURS un <script src> statique chargé AVANT logx_logbook.js
# (qui définit adaptivePoll), donc readyState vaut TOUJOURS 'loading' à son
# exécution réelle : simuler le contraire nécessiterait qu'adaptivePoll()
# soit déjà définie sans avoir chargé logx_logbook.js, un scénario qui ne se
# produit jamais avec l'ordre de <script> réel de cette page.
