# -*- coding: utf-8 -*-
"""A02 (docs/FEUILLE_DE_ROUTE.md) : annuler le dernier QSO doit viser l'id
RÉELLEMENT attribué par le serveur, pas l'id optimiste proposé par le client.

Contexte : le client propose un id (Date.now()) au moment de la saisie, AVANT
de connaître la réponse du serveur. En cas de collision (typiquement juste
après un import ADIF, dont les id sont alloués en série à partir de
l'horloge), le serveur réattribue un id différent (reserve_qso_id_locked(),
logx_http.py) SANS RIEN DIRE d'autre qu'un champ 'id' dans sa réponse JSON.

Si le client n'adopte pas cet id avant de pousser le QSO dans qsoLog,
undoLastQSO() (logx_edit_qso.js) supprime /log/delete/<id périmé> : un QSO du
carnet HISTORIQUE porte peut-être déjà cet id-là (collision), auquel cas
c'est LUI qui disparaît -- le QSO qu'on croyait annuler reste en place. C'est
le scénario réel décrit par l'audit du 18/08 pour ce point.

Le correctif existe déjà dans le code (_adopterIdServeur(), logx_logbook.js)
: ce test l'exécute réellement (V8 via py_mini_racer), pas une réimplémentation
du mécanisme -- sinon on ne testerait que le mannequin, pas le produit."""
import os
import sys

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGBOOK_JS = os.path.join(BASE, 'logx_logbook.js')
EDIT_QSO_JS = os.path.join(BASE, 'logx_edit_qso.js')
# Même convention que test_export_edi_num_sent.py : logx_logbook.js référence
# au niveau racine des fonctions extraites vers ces fichiers -- sans eux
# chargés AVANT, le parse lève un ReferenceError.
ESM_CALLBOT_JS = os.path.join(BASE, 'logx_esm_callbot.js')
VOICE_KEYER_JS = os.path.join(BASE, 'logx_voice_keyer.js')
EXPORT_EDI_JS = os.path.join(BASE, 'logx_export_edi.js')
SOAPBOX_JS = os.path.join(BASE, 'logx_soapbox.js')
FILTRE_SPOTS_JS = os.path.join(BASE, 'logx_filtre_spots.js')

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
function setTimeout(fn){ if(typeof fn === 'function') fn(); return 0; }
function clearInterval(){}
function clearTimeout(){}
var localStorage = {
  _d:{}, getItem:function(k){ return (k in this._d)? this._d[k] : null; },
  setItem:function(k,v){ this._d[k]=String(v); }, removeItem:function(k){ delete this._d[k]; }
};
var __fetchCalls = [];
function fetch(url, opts){
  __fetchCalls.push({url:url, opts:opts||{}});
  if(String(url).indexOf('/log/delete/') === 0){
    return Promise.resolve({ ok:true, json:function(){ return Promise.resolve({ok:true, deleted:1}); } });
  }
  return Promise.resolve({ ok:false, json:function(){ return Promise.resolve({}); } });
}
function alert(){}
function confirm(){ return false; }
function prompt(){ return null; }
var navigator = { userAgent:'test', mediaDevices: { enumerateDevices: function(){ return Promise.resolve([]); } }, clipboard:{} };
var location = { protocol:'http:', hostname:'127.0.0.1', href:'http://127.0.0.1/', search:'', reload:function(){} };
window.location = location;
window.open = function(){ return null; };
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
function renderLog(){}
function updateStats(){}
function bcBroadcast(){}
"""


def _load_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    src = ''
    for p in (ESM_CALLBOT_JS, VOICE_KEYER_JS, EXPORT_EDI_JS, SOAPBOX_JS,
              FILTRE_SPOTS_JS, LOGBOOK_JS, EDIT_QSO_JS):
        with open(p, encoding='utf-8') as f:
            src += '\n' + f.read()
    ctx.eval(src)
    # undoLastQSO() confirme via un bandeau non bloquant (pas confirm() natif)
    ctx.eval("_confirmDupBanner = function(){ return Promise.resolve(true); };")
    return ctx


def test_undo_vise_l_id_adopte_pas_l_id_optimiste_perime():
    """Reproduit le scénario réel : le 2e QSO propose l'id 2000, le serveur
    en réattribue un autre (9999, collision simulée) -- undoLastQSO() doit
    supprimer 9999, jamais 2000 (qui n'existe plus côté serveur, ou pire,
    identifie un AUTRE QSO du carnet historique)."""
    ctx = _load_ctx()
    ctx.eval("""
    qsoLog = [
      {id: 1000, call:'F1AAA', band:'14', mode:'SSB', time:'10:00'},
      {id: 2000, call:'F2BBB', band:'14', mode:'SSB', time:'10:01'}
    ];
    var fakeRes = { ok:true, json:function(){ return Promise.resolve({ok:true, id:9999, total:2, duplicate:false}); } };
    _adopterIdServeur(fakeRes, qsoLog[1]);
    """)
    # id adopté AVANT tout appel à undoLastQSO() -- le coeur du correctif
    assert ctx.eval('qsoLog[1].id') == 9999

    ctx.eval('undoLastQSO();')
    calls = ctx.eval('JSON.stringify(__fetchCalls)')
    import json
    delete_urls = [c['url'] for c in json.loads(calls) if '/log/delete/' in c['url']]
    assert delete_urls == ['/log/delete/9999'], (
        f"undoLastQSO() a visé {delete_urls!r} au lieu de l'id adopté 9999 "
        "(id optimiste périmé 2000 encore utilisé ?)")


def test_sans_adoption_le_defaut_original_se_reproduit():
    """Contre-épreuve inverse : SANS l'appel à _adopterIdServeur() (comme
    avant le correctif), le QSO garde son id optimiste 2000 -- undoLastQSO()
    viserait alors le mauvais id. Prouve que le test ci-dessus contraint
    réellement le mécanisme, pas un absent."""
    ctx = _load_ctx()
    ctx.eval("""
    qsoLog = [
      {id: 1000, call:'F1AAA', band:'14', mode:'SSB', time:'10:00'},
      {id: 2000, call:'F2BBB', band:'14', mode:'SSB', time:'10:01'}
    ];
    """)
    assert ctx.eval('qsoLog[1].id') == 2000
    ctx.eval('undoLastQSO();')
    calls = ctx.eval('JSON.stringify(__fetchCalls)')
    import json
    delete_urls = [c['url'] for c in json.loads(calls) if '/log/delete/' in c['url']]
    assert delete_urls == ['/log/delete/2000']
