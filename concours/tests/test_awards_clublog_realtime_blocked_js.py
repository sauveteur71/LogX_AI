# -*- coding: utf-8 -*-
"""showAwards() (concours/logx_logbook.js, commit 1720e6b) — le champ
clublog_realtime_blocked ajouté par qsl_status() (concours/logx_qsl.py,
exposé par GET /qsl/status) n'était affiché NULLE PART dans la popup
Diplômes/QSL : un opérateur d'expédition dont le flux ClubLog Live est
suspendu (disjoncteur déclenché après un refus HTTP 403 — voir
logx_qsl.realtime_push) n'avait AUCUN moyen de le savoir depuis
l'interface ; ses QSO suivants ne partent plus vers Club Log en silence.

Ce module exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via
py_mini_racer, même technique que tests/test_logbook_render_window_reset.py),
avec /qsl/status mocké pour renvoyer clublog_realtime_blocked, pour
reproduire le scénario concrètement plutôt que de grepper une chaîne dans
le fichier source."""
import os
import subprocess

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')

# ─── DOM minimal (Proxy permissif, voir tests/test_logbook_render_window_reset.py
# pour la version commentée de ce Proxy) ──────────────────────────────────────
_DOM_PREAMBLE = r"""
var __store = {};
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:'', style:{}, checked:false, disabled:false, files:[], children:[], classList_set:new Set()};
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
    """Source réelle de logx_logbook.js : HEAD (fichier sur disque) par
    défaut, ou `rev` pour rejouer le scénario tel qu'il était à ce commit
    (ex. 1720e6b, avant ce fix — clublog_realtime_blocked jamais affiché)."""
    if rev is None:
        with open(JS_PATH, encoding='utf-8') as f:
            return f.read()
    out = subprocess.run(
        ['git', 'show', f'{rev}:concours/logx_logbook.js'],
        cwd=BASE, capture_output=True, text=True, encoding='utf-8', check=True)
    return out.stdout


def _make_ctx(clublog_realtime_blocked, rev=None):
    """Contexte V8 avec fetch() mocké : 5 endpoints attendus par showAwards()
    (Promise.all), données minimales mais suffisantes pour ne rien faire
    planter dans renderWorkedMatrix/renderDxRecords/renderActivityChart
    (toutes gèrent déjà l'absence de données — voir leurs gardes `if(!m...)`)."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(f"""
    function fetch(url){{
      var responses = {{
        '/awards/summary': {{qso_total:0, departments:{{}}, per_band:{{}}, continents:[],
                              has_confirmations:false, confirmed_total:0,
                              dxcc:{{worked:0, confirmed:0}}}},
        '/qsl/status': {{eqsl:false, clublog:true, lotw:false, qrzcq:false, hrdlog:false,
                          last:{{}}, confirmations:0,
                          clublog_realtime_blocked: {str(bool(clublog_realtime_blocked)).lower()}}},
        '/awards/matrix': {{}},
        '/data/dx_records': {{}},
        '/awards/activity?days=21': {{days:[]}},
      }};
      var body = responses[url] !== undefined ? responses[url] : {{}};
      return Promise.resolve({{ ok:true, json:function(){{ return Promise.resolve(body); }} }});
    }}
    """)
    ctx.eval(_real_source(rev))
    return ctx


def _run_show_awards(ctx):
    # showAwards() est async (Promise.all de 5 fetch + plusieurs .then en
    # chaîne) : on attend la fin RÉELLE (flag posé par un .then()) plutôt que
    # de deviner un nombre de passages microtâches, pour ne pas lire
    # #awardsInner avant qu'il soit rempli.
    ctx.eval("""
    var _testDone = false; var _testError = null;
    showAwards().then(function(){ _testDone = true; })
                .catch(function(e){ _testError = String(e && e.stack || e); _testDone = true; });
    """)
    for _ in range(50):
        if ctx.eval("_testDone"):
            break
        ctx.eval("undefined")
    err = ctx.eval("_testError")
    assert ctx.eval("_testDone") is True and not err, f"showAwards() n'a jamais terminé (erreur : {err})"
    return ctx.eval("document.getElementById('awardsInner').innerHTML")


def test_avertissement_clublog_realtime_blocked_affiche_quand_disjoncteur_declenche():
    ctx = _make_ctx(clublog_realtime_blocked=True)
    html = _run_show_awards(ctx)
    assert 'ClubLog' in html and ('403' in html or 'suspendu' in html.lower())


def test_pas_davertissement_quand_disjoncteur_non_declenche():
    ctx = _make_ctx(clublog_realtime_blocked=False)
    html = _run_show_awards(ctx)
    assert '403' not in html and 'suspendu' not in html.lower()


def test_reproduction_avant_fix_commit_1720e6b_najoute_aucun_avertissement():
    """Contrôle négatif : rejoue EXACTEMENT le showAwards() du commit
    1720e6b (avant ce fix) avec le même /qsl/status bloqué — confirme que
    le scénario était bien silencieux à l'époque, pour que ce test échoue
    de façon lisible si quelqu'un retire un jour l'avertissement."""
    ctx = _make_ctx(clublog_realtime_blocked=True, rev='1720e6b')
    html = _run_show_awards(ctx)
    assert '403' not in html and 'suspendu' not in html.lower()
