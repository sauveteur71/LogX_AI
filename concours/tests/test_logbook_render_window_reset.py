# -*- coding: utf-8 -*-
"""Fenêtre de rendu du logbook (logRenderLimit, commit e68907d) — reset quand
qsoLog est REMPLACÉ, pas seulement quand le filtre/la recherche changent.

logRenderLimit ne peut que CROÎTRE via showMoreLog() ; renderLog() ne le
remet à LOG_RENDER_DEFAULT que si (currentFilter + search) change. Or trois
chemins remplacent qsoLog par un tout autre contenu SANS toucher au filtre
ni à la recherche : resetLog(), la branche « clear » de archiveLog(), et un
resync serveur complet non-delta (fetchLog() quand data.delta est absent).
Sans reset explicite de la fenêtre à ces trois endroits, un opérateur qui a
cliqué « Afficher plus » plusieurs fois pendant un concours garde une
fenêtre de rendu énorme après avoir remis le log à zéro : la limitation à
300 lignes ajoutée par e68907d se retrouve silencieusement désactivée pour
tout le log suivant, alors que c'est exactement le scénario (nouveau
concours après RESET) que le correctif était censé couvrir.

Ce module exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via
py_mini_racer), avec un DOM minimal (Proxy permissif), pour reproduire le
scénario concrètement plutôt que de grepper une chaîne dans le fichier."""
import os
import subprocess

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
# EV-7 : resetLog()/archiveLog() ont été extraites vers ce fichier -- ajouté
# UNIQUEMENT pour la révision courante (rev=None). Au commit historique rejoué
# ci-dessous (e68907d), les deux fonctions vivaient encore dans logx_logbook.js
# : ce fichier n'existait pas à l'époque.
OUTILS_JS_PATH = os.path.join(BASE, 'logx_outils_autonomes.js')
# EV-7 19e incrément : appel TOP-LEVEL renderVoiceDynPanel() dans
# logx_logbook.js -- ReferenceError au parse sans ce fichier chargé avant.
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')

# ─── DOM minimal ──────────────────────────────────────────────────────────────
# logx_logbook.js est un script de page (pas un module) : il référence document/
# window/localStorage/fetch/confirm/prompt/... à la volée. Un Proxy générique
# pour les éléments DOM (getElementById) évite d'avoir à lister tous les id du
# fichier — n'importe quelle propriété lue/écrite est simplement mémorisée.
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


def _real_source(rev=None):
    """Source réelle de logx_logbook.js (+ logx_outils_autonomes.js, où EV-7 a
    déplacé resetLog()/archiveLog()) : HEAD par défaut, ou `rev` (ex. le
    commit e68907d) pour rejouer le scénario tel qu'il était AVANT ce fix."""
    if rev is None:
        with open(ESM_CALLBOT_JS_PATH, encoding='utf-8') as f:
            src = f.read()
        with open(JS_PATH, encoding='utf-8') as f:
            src += '\n' + f.read()
        with open(OUTILS_JS_PATH, encoding='utf-8') as f:
            src += '\n' + f.read()
        return src
    out = subprocess.run(
        ['git', 'show', f'{rev}:concours/logx_logbook.js'],
        cwd=BASE, capture_output=True, text=True, encoding='utf-8', check=True)
    return out.stdout


def _make_ctx(rev=None):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_real_source(rev))
    return ctx


def _seed_big_log(ctx, n, prefix='F4TEST'):
    """Place n QSO factices dans qsoLog, un filtre neutre, puis rend une
    première fois et étend la fenêtre deux fois (comme un opérateur qui a
    cliqué « Afficher plus » pendant le concours)."""
    ctx.eval(f"""
    qsoLog = (function(){{
      const arr = [];
      for(let i=0;i<{n};i++){{
        arr.push({{id:i+1, call:'{prefix}'+i, band:'14', mode:'SSB', time:'12:00', date:'20260101',
          rst_sent:'59', num_sent:String(i+1), rst_rcvd:'59', num_rcvd:'1', locator:'', operator:'OP1',
          dist:0, points:1}});
      }}
      return arr;
    }})();
    currentFilter = 'all';
    document.getElementById('logSearch').value = '';
    usageMode = 'contest';
    myOp = 'OP1';
    renderLog();
    showMoreLog();
    showMoreLog();
    """)
    return ctx.eval('logRenderLimit')


def _refill_same_filter(ctx, n, prefix='NEWLOG'):
    """Remplace qsoLog par un autre contenu (même filtre/recherche qu'avant)
    et rend à nouveau — simule le concours suivant qui regrossit le log."""
    ctx.eval(f"""
    qsoLog = (function(){{
      const arr = [];
      for(let i=0;i<{n};i++){{
        arr.push({{id:i+1, call:'{prefix}'+i, band:'14', mode:'SSB', time:'12:00', date:'20260101',
          rst_sent:'59', num_sent:String(i+1), rst_rcvd:'59', num_rcvd:'1', locator:'', operator:'OP1',
          dist:0, points:1}});
      }}
      return arr;
    }})();
    renderLog();
    """)


# ─── Le scénario, sur le commit d'origine (AVANT le fix de ce module) ────────
# Sert de garde-fou : si ces trois assertions passaient déjà sur e68907d, ce
# ne serait pas un vrai test de non-régression.

def test_reproduction_bug_sur_e68907d_reset():
    """Sur le commit d'origine, resetLog() NE remet PAS la fenêtre à zéro."""
    ctx = _make_ctx(rev='e68907d')
    extended = _seed_big_log(ctx, 1000)
    assert extended > ctx.eval('LOG_RENDER_DEFAULT')  # fenêtre bien étendue au préalable
    ctx.eval("""
    confirm = function(){ return true; };
    prompt = function(){ return 'RESET'; };
    fetch = function(){ return Promise.resolve({ ok:true, json:function(){ return Promise.resolve({folders:['x']}); } }); };
    resetLog();
    """)
    # Le bug : la fenêtre reste à la valeur étendue au lieu de revenir au défaut.
    assert ctx.eval('logRenderLimit') == extended


def test_reproduction_bug_sur_e68907d_archive_clear():
    ctx = _make_ctx(rev='e68907d')
    extended = _seed_big_log(ctx, 1000)
    ctx.eval("""
    confirm = function(){ return true; };
    fetch = function(){ return Promise.resolve({ ok:true, json:function(){
      return Promise.resolve({ok:true, qso_count:1000, name:'x', cleared:true}); } }); };
    archiveLog();
    """)
    assert ctx.eval('logRenderLimit') == extended


def test_reproduction_bug_sur_e68907d_resync_complet():
    ctx = _make_ctx(rev='e68907d')
    extended = _seed_big_log(ctx, 1000)
    ctx.eval("""
    fetch = function(){ return Promise.resolve({ ok:true, json:function(){
      return Promise.resolve({ version:2, qsos: (function(){
        const arr=[]; for(let i=0;i<1000;i++){ arr.push({id:i+1, call:'G3NEW'+i, band:'14', mode:'SSB',
          time:'12:00', date:'20260101', rst_sent:'59', num_sent:String(i+1), rst_rcvd:'59', num_rcvd:'1',
          locator:'', operator:'OP1', dist:0, points:1}); } return arr; })() }); } }); };
    fetchLog();
    """)
    assert ctx.eval('logRenderLimit') == extended


# ─── Le même scénario, sur le code ACTUEL : la fenêtre doit revenir au défaut ─

def test_resetLog_reinitialise_la_fenetre_de_rendu():
    ctx = _make_ctx()
    extended = _seed_big_log(ctx, 1000)
    default = ctx.eval('LOG_RENDER_DEFAULT')
    assert extended > default
    ctx.eval("""
    confirm = function(){ return true; };
    prompt = function(){ return 'RESET'; };
    fetch = function(){ return Promise.resolve({ ok:true, json:function(){ return Promise.resolve({folders:['x']}); } }); };
    resetLog();
    """)
    assert ctx.eval('logRenderLimit') == default
    assert ctx.eval('qsoLog.length') == 0
    # Le concours suivant regrossit le log sous le MÊME filtre : la fenêtre
    # doit être repartie à zéro, donc le bouton "Afficher plus" doit réapparaître.
    _refill_same_filter(ctx, 1000)
    assert ctx.eval('logRenderLimit') == default
    assert ctx.eval("document.getElementById('logMoreBar').classList.contains('show')") is True


def test_archiveLog_clear_reinitialise_la_fenetre_de_rendu():
    ctx = _make_ctx()
    extended = _seed_big_log(ctx, 1000)
    default = ctx.eval('LOG_RENDER_DEFAULT')
    assert extended > default
    ctx.eval("""
    confirm = function(){ return true; };
    fetch = function(){ return Promise.resolve({ ok:true, json:function(){
      return Promise.resolve({ok:true, qso_count:1000, name:'x', cleared:true}); } }); };
    archiveLog();
    """)
    assert ctx.eval('logRenderLimit') == default
    assert ctx.eval('qsoLog.length') == 0


def test_resync_complet_reinitialise_la_fenetre_de_rendu():
    """fetchLog() en mode NON-delta (data.delta absent) remplace qsoLog en
    entier — même sans clic RESET/archivage, ce cas doit aussi réinitialiser
    la fenêtre (ex. reconnexion après un redémarrage serveur)."""
    ctx = _make_ctx()
    extended = _seed_big_log(ctx, 1000)
    default = ctx.eval('LOG_RENDER_DEFAULT')
    assert extended > default
    ctx.eval("""
    fetch = function(){ return Promise.resolve({ ok:true, json:function(){
      return Promise.resolve({ version:2, qsos: (function(){
        const arr=[]; for(let i=0;i<1000;i++){ arr.push({id:i+1, call:'G3NEW'+i, band:'14', mode:'SSB',
          time:'12:00', date:'20260101', rst_sent:'59', num_sent:String(i+1), rst_rcvd:'59', num_rcvd:'1',
          locator:'', operator:'OP1', dist:0, points:1}); } return arr; })() }); } }); };
    fetchLog();
    """)
    assert ctx.eval('logRenderLimit') == default
    assert ctx.eval('qsoLog.length') == 1000


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    with open(JS_PATH, encoding='utf-8') as f:
        assert 'QSO Director' not in f.read()
