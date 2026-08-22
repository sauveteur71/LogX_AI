# -*- coding: utf-8 -*-
"""Correctif du sélecteur de bandes du LOGBOOK pour les VRAIS concours V/UHF
(chantier « page d'accueil par activité », 22/08/2026).

Avant ce correctif, renderBandButtons() (logx_logbook.js) indexait une table
locale CONTEST_BANDS qui ne connaissait que des clés GÉNÉRIQUES (REF_CCD,
REF_IARU_VHF...) -- aucune des vraies clés d'édition qu'utilise le reste de
l'app (REF_CCD_JAN1, REF_MARCONI, REF_DDFM_50, REF_IARU_50...). Le lookup
échouait donc pour la quasi-totalité des concours V/UHF réels et retombait
sur ALL_BANDS -- bandes HF comprises. Une activité « LOG V/UHF » qui ne
filtre pas vraiment les bandes serait creuse.

Ce module exécute le VRAI logx_logbook.js (avec logx_contest_rules.js, d'où
vient désormais _resolveContestFilters()) dans un moteur JS réel (V8 via
py_mini_racer), même harnais DOM que tests/test_dup_confirm_banner.py."""
import json
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

# ─── DOM minimal (copie de tests/test_dup_confirm_banner.py) ────────────────
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
    # RULES_JS_PATH AVANT JS_PATH : renderBandButtons() appelle
    # _resolveContestFilters(), défini dans logx_contest_rules.js.
    for path in (RULES_JS_PATH, QTC_JS_PATH, ESM_CALLBOT_JS_PATH, VOICE_KEYER_JS_PATH, FILTRE_SPOTS_JS_PATH, JS_PATH):
        with open(path, encoding='utf-8') as f:
            ctx.eval(f.read())
    return ctx


def _rendered_bands(ctx):
    return ctx.eval("JSON.stringify(_currentVisibleBands)")


def test_renderbandbuttons_marconi_ne_propose_que_144mhz():
    """REF_MARCONI (144 MHz, CW uniquement) -- id historique absent de la
    table générique CONTEST_BANDS d'avant correctif."""
    ctx = _make_ctx()
    ctx.eval("renderBandButtons('REF_MARCONI');")
    assert _rendered_bands(ctx) == '["144"]'


def test_renderbandbuttons_ccd_jan1_propose_les_trois_bandes_thf_sans_hf():
    """REF_CCD_JAN1 (432/1296/2320 MHz) -- avant correctif, seule la clé
    générique REF_CCD (jamais utilisée en pratique) était connue."""
    ctx = _make_ctx()
    ctx.eval("renderBandButtons('REF_CCD_JAN1');")
    bands = json.loads(ctx.eval("JSON.stringify(_currentVisibleBands)"))
    assert set(bands) == {'432', '1296', '2320'}
    assert '1.8' not in bands and '14' not in bands  # aucune bande HF


def test_renderbandbuttons_ddfm_50_ne_propose_que_50mhz():
    ctx = _make_ctx()
    ctx.eval("renderBandButtons('REF_DDFM_50');")
    assert _rendered_bands(ctx) == '["50"]'


def test_renderbandbuttons_concours_libre_retombe_sur_toutes_les_bandes():
    """CUSTOM (axe libre, ni serveur ni LEGACY_CONTEST_FILTERS) doit garder
    le repli ALL_BANDS -- comportement de sécurité inchangé."""
    ctx = _make_ctx()
    ctx.eval("renderBandButtons('CUSTOM');")
    bands = json.loads(ctx.eval("JSON.stringify(_currentVisibleBands)"))
    assert '1.8' in bands and '144' in bands and '432' in bands  # HF et V/UHF toutes présentes


def test_renderbandbuttons_concours_libre_active_vuhf_propose_144_432_1296():
    """QSO occasionnel hors concours (CUSTOM = axe libre) en activité
    LOG V/UHF : « 2m, 70cm, 23cm et ça suffit » (F4GLD, 22/08/2026), pas
    ALL_BANDS -- sans quoi choisir l'activité ne changerait rien au sélecteur
    de bandes pour l'usage le plus courant (pas de concours actif)."""
    ctx = _make_ctx()
    ctx.eval("localStorage.setItem('logx_activity', 'vuhf');")
    ctx.eval("renderBandButtons('CUSTOM');")
    bands = json.loads(ctx.eval("JSON.stringify(_currentVisibleBands)"))
    assert set(bands) == {'144', '432', '1296'}


def test_renderbandbuttons_concours_reel_prime_sur_le_defaut_vuhf():
    """L'activité V/UHF ne doit influencer QUE le repli « axe libre » --
    un vrai concours (même HF, si l'opérateur en choisit un explicitement)
    garde son propre règlement, jamais écrasé par le défaut d'activité."""
    ctx = _make_ctx()
    ctx.eval("localStorage.setItem('logx_activity', 'vuhf');")
    ctx.eval("renderBandButtons('REF_MARCONI');")
    assert _rendered_bands(ctx) == '["144"]'


def test_lien_propag_contextuel_utilise_la_bande_en_cours():
    """Retour F4GLD 22/08/2026 (« lien profond propag ») : le lien PROPAG de
    la nav doit ouvrir logx_propagation.html sur la bande RÉELLEMENT en
    cours de saisie, pas un onglet générique ou le dernier consulté."""
    ctx = _make_ctx()
    ctx.eval("renderBandButtons('REF_CCD_JAN1');")   # currentBand -> '432'
    ctx.eval("_navPropagContextuel();")
    href = ctx.eval("location.href")
    assert href == 'logx_propagation.html?band=432#propPane-focus'


def test_lien_propag_contextuel_empeche_la_navigation_par_defaut():
    ctx = _make_ctx()
    appele = ctx.eval("""
    (function(){
      var appele = false;
      var faux_event = { preventDefault: function(){ appele = true; } };
      _navPropagContextuel(faux_event);
      return appele;
    })();
    """)
    assert appele is True


def test_nav_propag_utilise_bien_le_garde_typeof():
    """La nav (.app-nav) est identique sur 10 pages -- seule logx_logbook.js
    connaît _navPropagContextuel(). Sans garde typeof, les autres pages
    lèveraient une ReferenceError au clic sur PROPAG."""
    html = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()
    assert "typeof _navPropagContextuel==='function'" in html
