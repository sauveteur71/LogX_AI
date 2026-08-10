# -*- coding: utf-8 -*-
"""Champs obligatoires de la saisie QSO (demande F4GLD, 10/08/2026) :

- Indicatif ET fréquence sont les deux seuls champs réellement indispensables
  à TOUT QSO -- submitQSO() bloquait déjà sur l'indicatif manquant, pas sur
  la fréquence (silencieusement enregistrée vide). La bande, elle, est déjà
  déduite automatiquement de la fréquence saisie (onFreqInput() ->
  bandFromFreq(), inchangé ici) -- rien à ajouter de ce côté.
- Le locator du correspondant reste optionnel par défaut (simple
  avertissement, QSO loggué à 0 pt) SAUF pour les concours dont le barème
  calcule les points à la distance (per_km) : sans locator, calcPoints()
  renvoie 0 pt à coup sûr, ce n'est plus une perte de confort mais un QSO
  qu'on sait déjà nul -- contestRequiresLocator() bloque alors la saisie.
  Dérivée du même barème serveur (contestScoringDefs) que calcPoints(), pas
  d'une liste d'identifiants de concours écrite à la main (cf.
  piege-liste-identifiants-ecrite-a-la-main.md).
- Le lookup automatique du locator par indicatif (proposition auto pendant
  la frappe) existe déjà de longue date -- onCallInput() -> lookupCall()/
  lookupCluster()/applyCallData(), avec repli distant HamQTH via
  remoteCallLookup() -- vérifié ici par lecture de code, aucun nouveau test
  requis pour ce point.

Ce module exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via
py_mini_racer), DOM minimal et fetch stub -- même patron que
tests/test_macro_cw_serie_bande.py (repris tel quel pour rester
indépendant)."""
import json
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
HARDWARE_JS_PATH = os.path.join(BASE, 'logx_hardware_cat.js')
# calcPoints() -> evalPointsFromDef() -> _brickCtx() appelle lookupDXCC() dès
# qu'un barème serveur (contestScoringDefs[contestId]) est défini -- ce que
# les tests locator-obligatoire ci-dessous font explicitement, contrairement
# à test_macro_cw_serie_bande.py qui n'en a jamais eu besoin.
DXCC_JS_PATH = os.path.join(BASE, 'logx_dxcc_lookup.js')
CALLBOOK_JS_PATH = os.path.join(BASE, 'logx_callbook.js')
LOOKUP_JS_PATH = os.path.join(BASE, 'logx_lookup.js')
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')
VOICE_KEYER_JS_PATH = os.path.join(BASE, 'logx_voice_keyer.js')
LOCATOR_REVERSE_JS_PATH = os.path.join(BASE, 'logx_locator_reverse.js')
MACROS_JS_PATH = os.path.join(BASE, 'logx_macros.js')
FILTRE_SPOTS_JS_PATH = os.path.join(BASE, 'logx_filtre_spots.js')
OUTILS_DIVERS_JS_PATH = os.path.join(BASE, 'logx_outils_divers.js')

# ─── DOM minimal (copie de tests/test_macro_cw_serie_bande.py) ──────────────
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

_NET_STUB = r"""
var __logged = [];
function __ok(payload){
  return Promise.resolve({ok:true, status:200, json:function(){ return Promise.resolve(payload); }});
}
function fetch(url, opts){
  url = String(url);
  var body = {};
  try{ body = (opts && opts.body) ? JSON.parse(opts.body) : {}; }catch(e){}
  if(url.indexOf('/log/next_serial') === 0) return __ok({serial:'001'});
  if(url.indexOf('/log/add') === 0){ __logged.push(body); return __ok({ok:true}); }
  return __ok({});
}
"""

_INIT = r"""
function __init(){
  myCall = 'F4TEST'; myLocator = 'JN03QQ'; myOp = 'OP1';
  usageMode = 'contest';
  currentContest = null;
  contestScoringDefs = {};
  qsoLog = [];
  serialByBand = {};
  __logged = [];
  expeditionMode = false;
  applyExpeditionMode(false);
  pickBand('144');
  document.getElementById('inputCall').value = 'F6KQJ';
}
"""


def _real_source():
    parts = []
    for path in (HARDWARE_JS_PATH, DXCC_JS_PATH, CALLBOOK_JS_PATH, LOOKUP_JS_PATH, ESM_CALLBOT_JS_PATH,
                 VOICE_KEYER_JS_PATH, LOCATOR_REVERSE_JS_PATH, MACROS_JS_PATH,
                 FILTRE_SPOTS_JS_PATH, OUTILS_DIVERS_JS_PATH, JS_PATH):
        with open(path, encoding='utf-8') as f:
            parts.append(f.read())
    return '\n'.join(parts)


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_real_source())
    ctx.eval(_NET_STUB)   # après la source : remplace le fetch du préambule
    ctx.eval(_INIT)
    ctx.eval('__init();')
    return ctx


def _toast(ctx):
    return ctx.eval("document.getElementById('macroToast').textContent")


# ─── Fréquence obligatoire ───────────────────────────────────────────────────

def test_submitQSO_bloque_sans_frequence():
    ctx = _make_ctx()
    ctx.eval("""
    document.getElementById('inputLocator').value = 'JN15XC';
    document.getElementById('inputFreq').value = '';
    """)
    ctx.eval('submitQSO();')
    assert ctx.eval('__logged.length') == 0, 'aucun QSO ne doit être posté sans fréquence'
    assert 'requence manquante' in _toast(ctx) or 'Fréquence manquante' in _toast(ctx)


def test_submitQSO_passe_avec_frequence_deja_prefillie():
    """setFreqForBand() (appelé par pickBand() dans __init()) préremplit déjà
    le champ -- le cas normal ne doit RIEN changer."""
    ctx = _make_ctx()
    ctx.eval("document.getElementById('inputLocator').value = 'JN15XC';")
    freq_avant = ctx.eval("document.getElementById('inputFreq').value")
    assert freq_avant, 'le champ fréquence doit déjà être prérempli par pickBand()'
    ctx.eval('submitQSO();')
    assert ctx.eval('__logged.length') == 1


# ─── Bande déduite automatiquement de la fréquence (déjà existant) ──────────

def test_bandFromFreq_deja_cablee_sur_la_saisie_frequence():
    """Non-régression : onFreqInput() doit toujours faire suivre currentBand
    à la fréquence tapée -- pas une nouveauté de ce correctif, juste vérifié
    ici pour documenter que la demande était déjà satisfaite de ce côté."""
    ctx = _make_ctx()
    ctx.eval("""
    _currentVisibleBands = ['144', '432', '1296'];   // normalement rempli par renderBandButtons()
    document.getElementById('inputFreq').value = '432.100';
    onFreqInput();
    """)
    assert ctx.eval('currentBand') == '432'


# ─── Locator : obligatoire seulement si le barème du concours le distance ────

def test_contestRequiresLocator_faux_sans_concours():
    ctx = _make_ctx()
    assert ctx.eval('contestRequiresLocator()') is False


def test_contestRequiresLocator_faux_pour_bareme_a_points_fixes():
    ctx = _make_ctx()
    ctx.eval("""
    currentContest = 'CQ_WW_CW';
    contestScoringDefs['CQ_WW_CW'] = {type:'zone_country_per_band'};
    """)
    assert ctx.eval('contestRequiresLocator()') is False


def test_contestRequiresLocator_vrai_pour_bareme_km_x_locators():
    ctx = _make_ctx()
    ctx.eval("""
    currentContest = 'REF_RPH';
    contestScoringDefs['REF_RPH'] = {type:'km_x_locators'};
    """)
    assert ctx.eval('contestRequiresLocator()') is True


def test_contestRequiresLocator_vrai_pour_bareme_km_x_large_locator_squares():
    ctx = _make_ctx()
    ctx.eval("""
    currentContest = 'REF_IARU_VHF';
    contestScoringDefs['REF_IARU_VHF'] = {type:'km_x_large_locator_squares'};
    """)
    assert ctx.eval('contestRequiresLocator()') is True


def test_contestRequiresLocator_vrai_pour_bricks_custom_avec_per_km():
    """Barème serveur généré (IA ou custom_contests.json), pas un des 3 types
    connus -- doit quand même être détecté via ses briques `points`."""
    ctx = _make_ctx()
    ctx.eval("""
    currentContest = 'MON_CONCOURS';
    contestScoringDefs['MON_CONCOURS'] = {bricks:{points:[{points:'per_km'}]}};
    """)
    assert ctx.eval('contestRequiresLocator()') is True


def test_submitQSO_bloque_sans_locator_quand_concours_note_a_la_distance():
    ctx = _make_ctx()
    ctx.eval("""
    currentContest = 'REF_RPH';
    contestScoringDefs['REF_RPH'] = {type:'km_x_locators'};
    document.getElementById('inputLocator').value = '';
    """)
    ctx.eval('submitQSO();')
    assert ctx.eval('__logged.length') == 0
    assert 'obligatoire' in _toast(ctx).lower()


def test_submitQSO_passe_sans_locator_quand_concours_a_points_fixes():
    """Non-régression du comportement existant : locator vide reste un simple
    avertissement (QSO loggué à 0 pt) pour un concours qui n'en a pas besoin."""
    ctx = _make_ctx()
    ctx.eval("""
    currentContest = 'CQ_WW_CW';
    contestScoringDefs['CQ_WW_CW'] = {type:'zone_country_per_band'};
    document.getElementById('inputLocator').value = '';
    """)
    ctx.eval('submitQSO();')
    assert ctx.eval('__logged.length') == 1
    assert 'sans locator' in _toast(ctx).lower()


def test_submitQSO_locator_obligatoire_nempeche_pas_si_rempli():
    ctx = _make_ctx()
    ctx.eval("""
    currentContest = 'REF_RPH';
    contestScoringDefs['REF_RPH'] = {type:'km_x_locators'};
    document.getElementById('inputLocator').value = 'JN15XC';
    """)
    ctx.eval('submitQSO();')
    assert ctx.eval('__logged.length') == 1


def test_submitQSO_locator_obligatoire_neffet_pas_en_mode_expedition():
    """Le champ locator est masqué en mode expédition (applyExpeditionMode) --
    aucun blocage ne doit apparaître même si le concours actif est à distance."""
    ctx = _make_ctx()
    ctx.eval("""
    currentContest = 'REF_RPH';
    contestScoringDefs['REF_RPH'] = {type:'km_x_locators'};
    expeditionMode = true;
    document.getElementById('inputLocator').value = '';
    """)
    ctx.eval('submitQSO();')
    assert ctx.eval('__logged.length') == 1


def test_pas_de_liste_de_concours_ecrite_a_la_main():
    """contestRequiresLocator() doit dériver du barème serveur
    (contestScoringDefs), jamais d'une liste d'identifiants codée en dur --
    piège documenté (piege-liste-identifiants-ecrite-a-la-main.md)."""
    with open(JS_PATH, encoding='utf-8') as f:
        src = f.read()
    deb = src.index('function contestRequiresLocator(')
    fin = src.index('\n}', deb) + 2
    corps = src[deb:fin]
    assert 'REF_' not in corps and 'IARU' not in corps and 'CQ_WW' not in corps
