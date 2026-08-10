# -*- coding: utf-8 -*-
"""Bandeau de confirmation doublon non bloquant (chantier 2, audit
accessibilité 09/08/2026, PR suivant #7/#8) : _confirmDupBanner()/
_resolveDupConfirm()/_cancelPendingDupConfirm() remplacent les dialogues
confirm() natifs de submitQSO() (pré-vérification client + réponse serveur
409) -- un dialogue natif gèle toute la page et déplace le focus hors du
contrôle de l'app, gênant en pleine cadence de saisie.

Ce module exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via
py_mini_racer, même technique que tests/test_qtc_panel_js.py, dont le DOM
minimal est repris tel quel pour rester indépendant)."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
# EV-7 : mêmes dépendances top-level que tests/test_qtc_panel_js.py --
# ReferenceError au parse de logx_logbook.js sans elles.
QTC_JS_PATH = os.path.join(BASE, 'logx_qtc.js')
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')
VOICE_KEYER_JS_PATH = os.path.join(BASE, 'logx_voice_keyer.js')
FILTRE_SPOTS_JS_PATH = os.path.join(BASE, 'logx_filtre_spots.js')

# ─── DOM minimal (copie de tests/test_qtc_panel_js.py, voir
# tests/test_logbook_render_window_reset.py pour la version commentée) ──────
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
    for path in (QTC_JS_PATH, ESM_CALLBOT_JS_PATH, VOICE_KEYER_JS_PATH, FILTRE_SPOTS_JS_PATH, JS_PATH):
        with open(path, encoding='utf-8') as f:
            ctx.eval(f.read())
    return ctx


def _flush(ctx):
    """Vide la file des microtasks (résolution de Promise) -- même technique
    que test_qtc_panel_js.py::test_saveQTCSeries_..."""
    ctx.eval("undefined")


def test_confirmDupBanner_affiche_le_bandeau_avec_le_message():
    ctx = _make_ctx()
    ctx.eval("_confirmDupBanner('F6KQJ déjà loggé — enregistrer quand même ?');")
    assert ctx.eval("document.getElementById('dupConfirmBanner').classList.contains('show')") is True
    assert ctx.eval("document.getElementById('dupConfirmMsg').textContent") == 'F6KQJ déjà loggé — enregistrer quand même ?'


def test_resolveDupConfirm_true_resout_la_promesse_a_true_et_masque_le_bandeau():
    ctx = _make_ctx()
    ctx.eval("""
    var __result = 'pending';
    _confirmDupBanner('test').then(function(r){ __result = r; });
    """)
    ctx.eval("_resolveDupConfirm(true);")
    _flush(ctx)
    assert ctx.eval("__result") is True
    assert ctx.eval("document.getElementById('dupConfirmBanner').classList.contains('show')") is False


def test_resolveDupConfirm_false_resout_la_promesse_a_false():
    ctx = _make_ctx()
    ctx.eval("""
    var __result = 'pending';
    _confirmDupBanner('test').then(function(r){ __result = r; });
    """)
    ctx.eval("_resolveDupConfirm(false);")
    _flush(ctx)
    assert ctx.eval("__result") is False


def test_un_nouvel_appel_annule_automatiquement_le_bandeau_precedent_reste_ouvert():
    """Deux appels successifs à _confirmDupBanner() sans réponse entre les
    deux (ex. l'opérateur retente un envoi pour un autre indicatif pendant
    qu'un bandeau précédent traîne encore) : le premier doit se résoudre à
    false (annulé), pas rester en suspens indéfiniment."""
    ctx = _make_ctx()
    ctx.eval("""
    var __r1 = 'pending', __r2 = 'pending';
    _confirmDupBanner('premier').then(function(r){ __r1 = r; });
    _confirmDupBanner('second').then(function(r){ __r2 = r; });
    """)
    _flush(ctx)
    assert ctx.eval("__r1") is False, "le premier bandeau doit être auto-annulé (résolu à false), pas laissé en suspens"
    assert ctx.eval("__r2") == 'pending', "le second bandeau doit rester ouvert, en attente d'une réponse"
    ctx.eval("_resolveDupConfirm(true);")
    _flush(ctx)
    assert ctx.eval("__r2") is True


def test_cancelPendingDupConfirm_sans_bandeau_ouvert_ne_leve_pas_d_erreur():
    ctx = _make_ctx()
    ctx.eval("_cancelPendingDupConfirm();")   # ne doit rien lever (pas de promesse en attente)


def test_onCallInput_annule_un_bandeau_de_confirmation_reste_ouvert():
    """Reprendre la frappe (nouvel indicatif) doit annuler un bandeau
    resté ouvert d'une tentative de soumission précédente -- sans ça, il
    resterait affiché/orphelin en désaccord avec le QSO en cours de saisie."""
    ctx = _make_ctx()
    ctx.eval("""
    // Neutralise les dépendances de onCallInput() sans rapport avec ce test
    // (autocomplete, lookups QRZ/callbook/cluster...) -- usageMode='simple'
    // court-circuite isDup() par paresse d'évaluation (dup && ...), inutile
    // de la stubber séparément.
    showAC = function(){}; hideAC = function(){}; searchCalls = function(){ return []; };
    checkCallStatus = function(){}; lookupQRZ = function(){}; checkPrevQsos = function(){};
    lookupDXCC = function(){ return null; }; lookupCall = function(){ return null; };
    lookupCluster = function(){ return null; }; applyCallData = function(){};
    crossBandAlert = function(){}; hideCompassInline = function(){};
    usageMode = 'simple'; qsoLog = []; callLookupTimer = null;
    var __result = 'pending';
    _confirmDupBanner('doublon précédent').then(function(r){ __result = r; });
    document.getElementById('inputCall').value = 'F6KQJ';
    """)
    ctx.eval("onCallInput();")
    _flush(ctx)
    assert ctx.eval("__result") is False
    assert ctx.eval("document.getElementById('dupConfirmBanner').classList.contains('show')") is False


def test_pas_de_confirm_natif_restant_dans_submitQSO():
    """Les deux confirm() natifs de submitQSO() (pré-vérification client +
    réponse serveur 409) doivent avoir disparu du CODE (pas des commentaires)
    -- remplacés par _confirmDupBanner()."""
    with open(JS_PATH, encoding='utf-8') as f:
        src = f.read()
    deb = src.index('async function submitQSO(')
    fin = src.index('\nfunction clearForm(', deb)
    corps = src[deb:fin]
    lignes_code = [l for l in corps.splitlines() if not l.strip().startswith('//')]
    assert not any('confirm(' in l for l in lignes_code), \
        "un confirm() natif est resté dans le corps (hors commentaires) de submitQSO()"
