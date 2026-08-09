# -*- coding: utf-8 -*-
"""notify() (logx_logbook.js) et les fonctions similaires qui injectent du
texte dynamique visible par l'utilisateur (copyMacro, qslAction, self-spot…)
affichaient TOUJOURS le français source tel quel, sans jamais passer par
window.rcT()/rcTf() (logx_i18n.js) — même quand la clé traduite existe dans le
dictionnaire, un texte déjà interpolé (`${...}`) ne correspond plus à AUCUNE
clé et ne peut donc jamais être traduit. Corrigé en :

  - faisant systématiquement passer notify(msg) par trT(msg) avant affichage
    (repli local si logx_i18n.js n'est pas chargé, cf. trT()/trF() ci-dessus
    de notify() dans logx_logbook.js) ;
  - convertissant tous les appels qui injectaient une valeur dynamique
    (`${...}`/concaténation) pour construire un MODÈLE avec placeholders
    {clé} via trF('modèle {clé}', {clé: valeur}) plutôt que par interpolation
    directe — seul un modèle FIXE peut être une clé du dictionnaire i18n.

Ce module exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via
py_mini_racer), même modèle de DOM minimal (Proxy) que
tests/test_partner_view_closed_panel.py."""
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
# EV-7 33e incrément : appel TOP-LEVEL setInterval(refreshBandMap,...) dans
# logx_logbook.js -- ReferenceError au parse sans ce fichier chargé avant.
FILTRE_SPOTS_JS_PATH = os.path.join(BASE, 'logx_filtre_spots.js')

# ─── DOM minimal (Proxy) — même modèle que test_partner_view_closed_panel.py ─
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
      if(prop === 'getBoundingClientRect') return function(){ var h = s._mockHeight || 0; return {top:0,left:0,width:0,height:h,bottom:h,right:0}; };
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
  querySelector: function(sel){ var k='qs:'+sel; if(!__store[k]) __store[k] = ElProxy(); return __store[k]; },
  addEventListener: function(){}, removeEventListener: function(){},
  createElement: function(){ return ElProxy(); },
  querySelectorAll: function(){ return []; },
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


def _real_source():
    with open(ESM_CALLBOT_JS_PATH, encoding='utf-8') as f:
        src = f.read()
    with open(VOICE_KEYER_JS_PATH, encoding='utf-8') as f:
        src += '\n' + f.read()
    with open(FILTRE_SPOTS_JS_PATH, encoding='utf-8') as f:
        src += '\n' + f.read()
    with open(JS_PATH, encoding='utf-8') as f:
        return src + '\n' + f.read()


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_real_source())
    return ctx


# ─── trT()/trF() : repli sûr quand logx_i18n.js n'est pas chargé ────────────
# (page qui ne l'inclut pas, ou — comme ici — tests JS sans DOM complet).
# Comportement attendu : identique à rcT()/rcTf() en français (texte source
# tel quel, placeholders quand même substitués).

def test_trT_repli_francais_si_rcT_absent():
    ctx = _make_ctx()
    assert ctx.eval("typeof window.rcT") == 'undefined'
    assert ctx.eval("trT('Indicatif manquant !')") == 'Indicatif manquant !'


def test_trF_repli_substitue_les_placeholders_si_rcTf_absent():
    ctx = _make_ctx()
    assert ctx.eval("typeof window.rcTf") == 'undefined'
    assert ctx.eval("trF('QSO avec {call} sur {band} MHz', {call:'F4GLD', band:'14'})") == \
        'QSO avec F4GLD sur 14 MHz'


# ─── notify() route désormais son message par trT() avant affichage ─────────

def test_notify_traduit_via_rcT_si_disponible():
    """Simule logx_i18n.js chargé + langue ≠ français (window.rcT défini) :
    notify() doit afficher le texte TRADUIT, pas le français source."""
    ctx = _make_ctx()
    ctx.eval("""
    window.rcT = function(fr){ return fr === 'Indicatif manquant !' ? 'Callsign missing!' : fr; };
    notify('Indicatif manquant !');
    """)
    assert ctx.eval("document.getElementById('macroToast').textContent") == 'Callsign missing!'


def test_notify_classification_erreur_sur_le_francais_source_pas_la_traduction():
    """La classe toast-err est déterminée par des mots-clés FRANÇAIS
    ('manquant', 'erreur'…) : elle doit être posée sur le message ORIGINAL,
    AVANT traduction — une traduction anglaise ('Callsign missing!') ne
    contient plus aucun de ces mots-clés et ne serait jamais classifiée si
    l'ordre était inversé."""
    ctx = _make_ctx()
    ctx.eval("""
    window.rcT = function(fr){ return fr === 'Indicatif manquant !' ? 'Callsign missing!' : fr; };
    notify('Indicatif manquant !');
    """)
    assert ctx.eval("document.getElementById('macroToast').classList.contains('toast-err')") is True


def test_notify_sans_rcT_affiche_le_francais_inchange():
    """Page/contexte sans logx_i18n.js (window.rcT absent) : notify() doit
    quand même fonctionner, en repli sur le français source (pas d'erreur,
    pas de "undefined" affiché)."""
    ctx = _make_ctx()
    assert ctx.eval("typeof window.rcT") == 'undefined'
    ctx.eval("notify('Doublon ignoré — QSO non enregistré.');")
    assert ctx.eval("document.getElementById('macroToast').textContent") == \
        'Doublon ignoré — QSO non enregistré.'


# ─── Un appel notify() avec valeur dynamique doit passer par trF() ──────────
# (garde-fou anti-régression : si un futur commit revient à l'interpolation
# directe `${...}`, ce test échoue car window.rcTf ne serait jamais appelé
# avec le MODÈLE — il serait appelé, au mieux, avec le texte déjà interpolé,
# donc introuvable dans le dictionnaire réel de logx_i18n.js).

def test_qtc_refuse_utilise_trF_avec_le_modele_pas_le_texte_interpole():
    ctx = _make_ctx()
    ctx.eval("""
    var __seenTemplates = [];
    window.rcTf = function(fr, params){
      __seenTemplates.push(fr);
      var s = fr;
      if(params) for(var k in params) s = s.split('{'+k+'}').join(params[k]);
      return s;
    };
    notify(trF('QTC refusé : {err}', {err: 'connexion perdue'}));
    """)
    assert ctx.eval("__seenTemplates[0]") == 'QTC refusé : {err}'
    assert ctx.eval("document.getElementById('macroToast').textContent") == \
        'QTC refusé : connexion perdue'
