# -*- coding: utf-8 -*-
"""Designer de carte QSL imprimable minimal (export PNG/JPG) -- demande
F4GLD, chantier concurrentiel (Wavelog/Log4OM/GridTracker2 ont tous un outil
équivalent). Rendu 100% client-side (canvas 2D), aucun endpoint serveur.

Même patron que tests/test_qso_champs_obligatoires.py : le VRAI
logx_logbook.js (+ logx_callbook.js pour fmtDate() + notre nouveau
logx_qsl_card.js) exécuté dans un moteur JS réel (V8 via py_mini_racer), DOM
minimal et fetch stub -- __init() n'est PAS appelée ici (pas besoin de
pickBand()/applyExpeditionMode(), qui vivent dans d'autres fichiers EV-7 non
chargés par ce module) : l'état (qsoLog/myCall/myLocator) est posé
directement par chaque test."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
RULES_JS_PATH = os.path.join(BASE, 'logx_contest_rules.js')
CALLBOOK_JS_PATH = os.path.join(BASE, 'logx_callbook.js')   # fmtDate()
QSL_JS_PATH = os.path.join(BASE, 'logx_qsl_card.js')
# logx_logbook.js référence certains symboles (ex. refreshBandMap) à son
# PROPRE niveau top-level (setInterval(refreshBandMap, ...)) : ils doivent
# être déclarés AVANT l'exécution du fichier, sinon ReferenceError immédiate
# -- même liste de dépendances que tests/test_qso_champs_obligatoires.py.
HARDWARE_JS_PATH = os.path.join(BASE, 'logx_hardware_cat.js')
DXCC_JS_PATH = os.path.join(BASE, 'logx_dxcc_lookup.js')
LOOKUP_JS_PATH = os.path.join(BASE, 'logx_lookup.js')
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')
VOICE_KEYER_JS_PATH = os.path.join(BASE, 'logx_voice_keyer.js')
LOCATOR_REVERSE_JS_PATH = os.path.join(BASE, 'logx_locator_reverse.js')
MACROS_JS_PATH = os.path.join(BASE, 'logx_macros.js')
FILTRE_SPOTS_JS_PATH = os.path.join(BASE, 'logx_filtre_spots.js')
OUTILS_DIVERS_JS_PATH = os.path.join(BASE, 'logx_outils_divers.js')

# ─── DOM minimal (copie de tests/test_qso_champs_obligatoires.py, lui-même
# copié de tests/test_macro_cw_serie_bande.py) ────────────────────────────
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
var __lastCreatedA = null;
var document = {
  getElementById: function(id){ if(!__store[id]) __store[id] = ElProxy(); return __store[id]; },
  addEventListener: function(){}, removeEventListener: function(){},
  createElement: function(tag){ var el = ElProxy(); if(tag === 'a') __lastCreatedA = el; return el; },
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


def _real_source():
    parts = []
    for path in (RULES_JS_PATH, HARDWARE_JS_PATH, DXCC_JS_PATH, CALLBOOK_JS_PATH, LOOKUP_JS_PATH,
                 ESM_CALLBOT_JS_PATH, VOICE_KEYER_JS_PATH, LOCATOR_REVERSE_JS_PATH,
                 MACROS_JS_PATH, FILTRE_SPOTS_JS_PATH, OUTILS_DIVERS_JS_PATH,
                 JS_PATH, QSL_JS_PATH):
        with open(path, encoding='utf-8') as f:
            parts.append(f.read())
    return '\n'.join(parts)


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_real_source())
    ctx.eval("""
    myCall = 'F4TEST'; myLocator = 'JN03QQ'; myOp = 'OP1';
    qsoLog = [];
    """)
    return ctx


def _un_qso(**over):
    q = {
        'id': 1723000000000, 'call': 'F6KQJ', 'band': '144', 'mode': 'SSB',
        'freq': '144.300', 'date': '20260810', 'time': '14:30',
        'rst_sent': '59', 'rst_rcvd': '57', 'locator': 'JN15XC',
        'my_call': 'F4TEST', 'my_locator': 'JN03QQ',
    }
    q.update(over)
    return q


# ─── qsoLog vide : pas d'explosion, état vide explicite ─────────────────────

def test_showQslCardDesigner_qsoLog_vide_n_explose_pas():
    ctx = _make_ctx()
    ctx.eval('showQslCardDesigner();')   # ne doit lever aucune exception JS
    ov = ctx.eval("document.getElementById('qslCardOverlay')")
    assert ov is not None


def test_qsoLog_vide_affiche_un_etat_vide_explicite_sans_undefined():
    ctx = _make_ctx()
    ctx.eval('showQslCardDesigner();')
    html = ctx.eval("document.getElementById('qslQsoSelect').innerHTML")
    assert 'undefined' not in html
    assert 'aucun' in html.lower()
    # Aucun QSO sélectionnable -> _qslSelectedQso() doit renvoyer null, pas planter.
    assert ctx.eval('_qslSelectedQso()') is None


def test_qsoLog_vide_ne_bloque_pas_le_changement_de_gabarit():
    """Changer de gabarit sans QSO ne doit pas non plus planter (_qslRender()
    est appelé par tous les onchange du panneau)."""
    ctx = _make_ctx()
    ctx.eval('showQslCardDesigner();')
    ctx.eval("document.getElementById('qslTemplateSelect').value = 'epure';")
    ctx.eval('_qslRender();')   # ne doit lever aucune exception JS


# ─── Canvas peuplé quand un QSO existe ───────────────────────────────────────

def test_canvas_peuple_avec_un_qso():
    ctx = _make_ctx()
    ctx.eval("qsoLog = [%s];" % _un_qso_js())
    ctx.eval('showQslCardDesigner();')
    assert ctx.eval("document.getElementById('qslCanvas').width") == 1500
    assert ctx.eval("document.getElementById('qslCanvas').height") == 1000


def test_le_qso_le_plus_recent_est_selectionne_par_defaut():
    """qsoLog est ordonné du plus ancien au plus récent (qsoLog.push) --
    showQslCardDesigner() doit présélectionner le DERNIER (le plus récent),
    pas le premier."""
    ctx = _make_ctx()
    ctx.eval("""
    qsoLog = [
      %s,
      Object.assign({}, %s, {id: 999, call: 'F5ABC'})
    ];
    """ % (_un_qso_js(), _un_qso_js()))
    ctx.eval('showQslCardDesigner();')
    assert ctx.eval("document.getElementById('qslQsoSelect').value") == '999'


def test_qsoLog_avec_qso_ne_montre_aucun_champ_undefined_dans_la_liste():
    ctx = _make_ctx()
    ctx.eval("qsoLog = [%s];" % _un_qso_js())
    ctx.eval('showQslCardDesigner();')
    html = ctx.eval("document.getElementById('qslQsoSelect').innerHTML")
    assert 'undefined' not in html
    assert 'F6KQJ' in html


def _un_qso_js():
    return ("{id:1723000000000, call:'F6KQJ', band:'144', mode:'SSB', "
            "freq:'144.300', date:'20260810', time:'14:30', "
            "rst_sent:'59', rst_rcvd:'57', locator:'JN15XC', "
            "my_call:'F4TEST', my_locator:'JN03QQ'}")


# ─── L'indicatif affiché est celui du QSO (q.my_call), pas la session en
# cours -- un opérateur portable peut changer d'identité (F4GLD/P -> F4GLD/M)
# dans la même journée sans changer de portée (concours+année) : qsoLog
# mélange alors des QSO faits sous des indicatifs différents. ────────────────

def test_qsl_utilise_my_call_du_qso_pas_l_indicatif_de_la_session_en_cours():
    import json
    ctx = _make_ctx()
    ctx.eval("myCall = 'F4TEST/M';")   # identité ACTUELLE de la session
    ctx.eval("qsoLog = [Object.assign({}, %s, {my_call: 'F4TEST/P'})];" % _un_qso_js())
    data = json.loads(ctx.eval("JSON.stringify(_qslBuildCardData(qsoLog[0], ''))"))
    assert data['myCall'] == 'F4TEST/P'


def test_qsl_repli_sur_myCall_session_si_q_my_call_absent():
    import json
    ctx = _make_ctx()
    ctx.eval("myCall = 'F4TEST';")
    ctx.eval("qsoLog = [Object.assign({}, %s, {my_call: ''})];" % _un_qso_js())
    data = json.loads(ctx.eval("JSON.stringify(_qslBuildCardData(qsoLog[0], ''))"))
    assert data['myCall'] == 'F4TEST'


def test_telechargement_utilise_aussi_my_call_du_qso():
    ctx = _make_ctx()
    ctx.eval("myCall = 'F4TEST/M';")
    ctx.eval("qsoLog = [Object.assign({}, %s, {my_call: 'F4TEST/P'})];" % _un_qso_js())
    ctx.eval('showQslCardDesigner();')
    ctx.eval("""
    document.getElementById('qslCanvas').toDataURL = function(mime){ return 'data:' + mime + ';base64,AAAA'; };
    """)
    ctx.eval("downloadQslCard('png');")
    name = ctx.eval('__lastCreatedA.download')
    assert 'F4TEST_P' in name
    assert 'F4TEST_M' not in name


# ─── Réouverture du panneau : le champ de recherche repart vide ────────────

def test_reouverture_du_panneau_vide_le_champ_de_recherche():
    ctx = _make_ctx()
    ctx.eval("qsoLog = [%s];" % _un_qso_js())
    ctx.eval('showQslCardDesigner();')
    ctx.eval("document.getElementById('qslQsoSearch').value = 'F6K';")
    ctx.eval('_qslFiltrerListeQso();')   # simule une recherche tapée par l'utilisateur
    ctx.eval('showQslCardDesigner();')   # puis une fermeture/réouverture (menu ☰)
    assert ctx.eval("document.getElementById('qslQsoSearch').value") == ''


# ─── Nom de fichier de téléchargement : jamais de '/' brut ─────────────────

def test_telechargement_nom_de_fichier_sans_slash_indicatif_portable():
    """Un indicatif portable (F4GLD/P) ou un correspondant en /P/M ne doit
    jamais casser le nom de fichier généré."""
    ctx = _make_ctx()
    ctx.eval("myCall = 'F4TEST/P';")
    ctx.eval("qsoLog = [Object.assign({}, %s, {call: 'F5ABC/M'})];" % _un_qso_js())
    ctx.eval('showQslCardDesigner();')
    # canvas.toDataURL n'existe pas dans le stub DOM minimal -- posé ici pour
    # ce test précis, comme le ferait un vrai navigateur.
    ctx.eval("""
    document.getElementById('qslCanvas').toDataURL = function(mime){ return 'data:' + mime + ';base64,AAAA'; };
    """)
    ctx.eval("downloadQslCard('png');")
    name = ctx.eval('__lastCreatedA.download')
    assert '/' not in name
    assert name.endswith('.png')


def test_qslSanitizeFilename_neutralise_tous_les_caracteres_a_risque():
    ctx = _make_ctx()
    assert '/' not in ctx.eval("_qslSanitizeFilename('F4GLD/P')")
    assert '\\' not in ctx.eval("_qslSanitizeFilename('A\\\\B')")
    assert ctx.eval("_qslSanitizeFilename('')") == 'QSO'


# ─── Menu LOGBOOK : entrée réelle, hors expert-only ─────────────────────────

def _bloc_menu(src):
    """itemsMenuLogbook() extraite telle quelle, par comptage d'accolades
    (même technique que tests/test_logbook_menu_debut_fin.py)."""
    deb = src.index('function itemsMenuLogbook(')
    ouv = src.index('{', deb)
    prof, i = 0, ouv
    while True:
        c = src[i]
        if c == '{':
            prof += 1
        elif c == '}':
            prof -= 1
            if prof == 0:
                return src[deb:i + 1]
        i += 1


def test_menu_contient_showQslCardDesigner_et_le_garde_hors_expert_only():
    with open(JS_PATH, encoding='utf-8') as f:
        src = f.read()
    ctx = py_mini_racer.MiniRacer()
    ctx.eval('function contestActif(){ return false; }')
    ctx.eval(_bloc_menu(src))
    deb = src.index('const MENU_LB_EXPERT_ONLY_FN')
    fin = src.index(';', deb) + 1
    ctx.eval(src[deb:fin])
    fns = [x[2] for _titre, items in
           __import__('json').loads(ctx.eval('JSON.stringify(itemsMenuLogbook())'))
           for x in items]
    assert 'showQslCardDesigner' in fns
    assert ctx.eval("MENU_LB_EXPERT_ONLY_FN.has('showQslCardDesigner')") is False
