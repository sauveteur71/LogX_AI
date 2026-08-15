# -*- coding: utf-8 -*-
"""Bug remonté par F4GLD (IC-7300 en CAT natif, 15/08/2026) :

1) Choisir 20m + CW dans les sélecteurs BANDE/MODE de LOGBOOK ne faisait
   JAMAIS bascule la radio (ni fréquence ni mode) -- pickBand()/pickMode()
   (logx_logbook.js) ne poussaient RIEN vers /rig/qsy, contrairement à
   bandmapClick() (clic sur un spot du band map) qui le fait déjà. Le carnet
   changeait de bande/mode pour le SCORING/LOG mais la radio restait où elle
   était.
2) Dans l'autre sens : passer la radio de SSB à CW À LA MAIN sur l'appareil
   ne mettait jamais à jour le sélecteur MODE de LOGBOOK -- le polling
   (adaptivePoll -> refreshHardware -> applyRigState -> syncBandModeFromRig,
   logx_hardware_cat.js) ne synchronisait QUE la bande malgré le nom de
   syncBandModeFromRig(), jamais le mode.

Corrigé par :
- pickBand()/pickMode() (logx_logbook.js) : un choix manuel (opts.fromRig
  absent/false) pousse désormais /rig/qsy vers la radio si le CAT est actif
  (_qsyVersRadio()).
- syncBandModeFromRig() (logx_hardware_cat.js) : synchronise maintenant AUSSI
  le mode (pas seulement la bande), via _rigModeVersLog() qui traduit le
  vocabulaire radio (LSB/USB/CW-R/RTTY-R/FSK/RTTY-LSB) vers celui du carnet
  (SSB/CW/RTTY/...).
- Les DEUX chemins passent par pickBand(band, {fromRig:true})/
  pickMode(mode, {fromRig:true}) quand l'origine est le poll radio -- sans
  cette garde, chaque poll aurait renvoyé une commande QSY à la radio qui
  vient tout juste de nous dire où elle est (boucle poll -> QSY -> poll).

Même patron que tests/test_qso_champs_obligatoires.py (VRAI logx_logbook.js
+ logx_hardware_cat.js dans un moteur JS réel via py_mini_racer, DOM minimal,
fetch-espion)."""
import json
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
HARDWARE_JS_PATH = os.path.join(BASE, 'logx_hardware_cat.js')
DXCC_JS_PATH = os.path.join(BASE, 'logx_dxcc_lookup.js')
CALLBOOK_JS_PATH = os.path.join(BASE, 'logx_callbook.js')
LOOKUP_JS_PATH = os.path.join(BASE, 'logx_lookup.js')
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')
VOICE_KEYER_JS_PATH = os.path.join(BASE, 'logx_voice_keyer.js')
LOCATOR_REVERSE_JS_PATH = os.path.join(BASE, 'logx_locator_reverse.js')
MACROS_JS_PATH = os.path.join(BASE, 'logx_macros.js')
FILTRE_SPOTS_JS_PATH = os.path.join(BASE, 'logx_filtre_spots.js')
OUTILS_DIVERS_JS_PATH = os.path.join(BASE, 'logx_outils_divers.js')

# ─── DOM minimal (copie de tests/test_qso_champs_obligatoires.py) ───────────
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

# fetch-espion : capture URL + corps JSON de chaque appel, plutôt qu'une
# simple réponse muette -- ce test doit prouver QUE /rig/qsy est (ou n'est
# PAS) appelé, avec quel corps.
_NET_STUB = r"""
var __fetchCalls = [];
function fetch(url, opts){
  var body = {};
  try{ body = (opts && opts.body) ? JSON.parse(opts.body) : {}; }catch(e){}
  __fetchCalls.push({url:String(url), body:body});
  return Promise.resolve({ok:true, status:200, json:function(){ return Promise.resolve({}); }});
}
function __qsyCalls(){ return __fetchCalls.filter(function(c){ return c.url === '/rig/qsy'; }); }
"""

_INIT = r"""
function __init(){
  myCall = 'F4TEST'; myLocator = 'JN03QQ'; myOp = 'OP1';
  usageMode = 'contest';
  currentContest = null;
  contestScoringDefs = {};
  qsoLog = [];
  serialByBand = {};
  __fetchCalls = [];
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


def _qsy_calls(ctx):
    """Les objets JS renvoyés par ctx.eval() ne sont pas des listes Python
    utilisables (py_mini_racer les expose en JSObject opaque) -- on repasse
    par JSON.stringify()/json.loads(), même patron que le reste de la suite
    pour inspecter un tableau construit côté JS."""
    return json.loads(ctx.eval('JSON.stringify(__qsyCalls())'))


# ─── 1) Choix manuel de BANDE : doit QSY la radio si le CAT est actif ───────

def test_pickBand_manuel_pousse_qsy_vers_la_radio_si_cat_actif():
    ctx = _make_ctx()
    ctx.eval("""
    rigState.enabled = true;
    _currentVisibleBands = ['144', '432', '14'];
    __fetchCalls = [];
    pickBand('14');
    """)
    calls = _qsy_calls(ctx)
    assert len(calls) == 1, 'pickBand() doit pousser exactement un /rig/qsy quand le CAT est actif'
    body = calls[0]['body']
    # BAND_FREQ['14'] = '14.150' MHz -> 14150 kHz (fréquence d'appel par défaut,
    # la radio n'était pas déjà sur cette bande dans ce test).
    assert body['freq_khz'] == 14150
    assert body['mode'] == 'SSB'   # currentMode inchangé par un choix de bande seul


def test_pickBand_sans_cat_actif_ne_pousse_rien():
    ctx = _make_ctx()
    ctx.eval("""
    rigState.enabled = false;
    _currentVisibleBands = ['144', '432'];
    __fetchCalls = [];
    pickBand('432');
    """)
    assert ctx.eval('__qsyCalls().length') == 0, (
        'sans CAT actif, aucun /rig/qsy ne doit partir (rien à piloter)')


def test_pickBand_seul_ne_touche_pas_rigState_mode():
    """Non-régression trouvée par tests/test_macro_cw_serie_bande.py pendant
    ce chantier : la 1re version poussait `rigState.mode = currentMode` dans
    _qsyVersRadio() (partagée par pickBand() ET pickMode()) -- un simple
    changement de BANDE écrasait alors le VRAI mode radio (rigState.mode,
    posé indépendamment par le polling CAT) par currentMode, qui peut être
    périmé. La mise à jour optimiste doit rester réservée à pickMode()."""
    ctx = _make_ctx()
    ctx.eval("""
    rigState.enabled = true;
    rigState.mode = 'CW';   // radio réellement en CW (ex. lu par le CAT)
    currentMode = 'SSB';    // le carnet n'a jamais suivi (scénario de test)
    _currentVisibleBands = ['144', '432'];
    __fetchCalls = [];
    pickBand('432');
    """)
    assert ctx.eval('rigState.mode') == 'CW', (
        'un choix de BANDE seul ne doit jamais réécrire rigState.mode')


# ─── 2) Choix manuel de MODE : doit QSY la radio (mode) sans déplacer la fréquence ─

def test_pickMode_manuel_pousse_qsy_avec_le_mode_choisi():
    ctx = _make_ctx()
    ctx.eval("""
    rigState.enabled = true;
    document.getElementById('inputFreq').value = '14.023';
    __fetchCalls = [];
    pickMode('CW');
    """)
    calls = _qsy_calls(ctx)
    assert len(calls) == 1, 'pickMode() doit pousser exactement un /rig/qsy quand le CAT est actif'
    body = calls[0]['body']
    assert body['mode'] == 'CW'
    # La fréquence n'est PAS réinventée par mode -- reste celle affichée dans
    # le champ (clause de repli du bug : "au moins changer de mode", jamais
    # une fréquence d'appel par mode devinée sans base réglementaire fiable).
    assert body['freq_khz'] == 14023


def test_pickMode_sans_cat_actif_ne_pousse_rien():
    ctx = _make_ctx()
    ctx.eval("""
    rigState.enabled = false;
    __fetchCalls = [];
    pickMode('CW');
    """)
    assert ctx.eval('__qsyCalls().length') == 0


# ─── 2bis) Symptôme #84 (F4GLD) : « en CW dans LOGBOOK, le décodeur CW    ───
# n'apparaît plus » -- signalé par le coordinateur PENDANT ce chantier comme
# lien probable avec le même bug. updateKeyerPanels() (logx_logbook.js) et
# esmSend() (logx_esm_callbot.js) priorisent rigState.mode sur currentMode
# dès qu'il est non vide -- avant ce correctif, choisir CW dans le sélecteur
# ne pilotait jamais la radio (bug #1 ci-dessus), donc rigState.mode restait
# sur le VRAI mode radio (resté SSB) et masquait le décodeur malgré
# currentMode==='CW'. pickMode() pose maintenant rigState.mode de façon
# optimiste, AVANT d'appeler updateKeyerPanels() -- ces tests vérifient le
# symptôme visible (affichage du panneau), pas seulement la variable.

def test_pickMode_cw_met_a_jour_rigState_mode_immediatement():
    ctx = _make_ctx()
    ctx.eval("""
    rigState.enabled = true;
    rigState.mode = 'USB';   // dernier mode radio connu, pas encore CW
    pickMode('CW');
    """)
    assert ctx.eval('rigState.mode') == 'CW', (
        'pickMode() doit poser rigState.mode tout de suite, sans attendre le '
        'prochain sondage matériel (adaptivePoll)')


def test_pickMode_cw_affiche_immediatement_le_decodeur_cw():
    """Vérifie le SYMPTÔME lui-même (panneau #cwPanel), pas juste la variable
    interne -- reproduit exactement le rapport #84 : sélecteur MODE mis sur
    CW dans LOGBOOK, CAT actif mais radio pas encore confirmée en CW par le
    poll suivant."""
    ctx = _make_ctx()
    ctx.eval("""
    rigState.enabled = true;
    rigState.mode = 'USB';
    document.getElementById('cwPanel').style.display = 'none';
    pickMode('CW');
    """)
    assert ctx.eval("document.getElementById('cwPanel').style.display") == '', (
        'le panneau décodeur CW doit apparaître dès le clic sur CW, pas '
        'seulement après le prochain sondage radio')


def test_pickMode_fromRig_ne_pousse_pas_de_mise_a_jour_optimiste_en_double():
    """pickMode(mode, {fromRig:true}) (appelée par syncBandModeFromRig()) ne
    doit pas re-déclencher la mise à jour optimiste -- rigState.mode est à ce
    moment-là DÉJÀ la valeur réelle posée par applyRigState() juste avant,
    pas une anticipation."""
    ctx = _make_ctx()
    ctx.eval("""
    rigState.enabled = true;
    rigState.mode = 'CW';
    currentMode = 'SSB';
    __fetchCalls = [];
    pickMode('CW', {fromRig: true});
    """)
    assert ctx.eval('__qsyCalls().length') == 0, (
        'un mode reçu DE la radio ne doit jamais repartir en /rig/qsy')


# ─── 2ter) rigState.mode ne doit pas rester périmé après désactivation ──────

def test_applyRigState_disable_remet_rigState_mode_a_vide():
    """Si le CAT était actif (rigState.mode='USB' par ex.) puis se désactive
    (radio débranchée, CONFIG changée...), rigState.mode ne doit pas rester
    bloqué sur cette dernière valeur indéfiniment -- sinon updateKeyerPanels()
    /esmSend() continueraient à la prioriser sur currentMode pour toujours,
    alors qu'elle ne reflète plus rien de réel."""
    ctx = _make_ctx()
    ctx.eval("""
    rigState.enabled = true;
    rigState.mode = 'USB';
    applyRigState({enabled: false});
    """)
    assert ctx.eval('rigState.enabled') is False
    assert ctx.eval('rigState.mode') == ''


def test_applyRigState_disable_laisse_le_decodeur_cw_suivre_currentMode():
    """Symptôme concret de la remise à zéro ci-dessus : une fois le CAT
    désactivé, le panneau décodeur CW doit suivre currentMode (l'opérateur
    est peut-être en CW manuel, sans CAT) -- pas rester bloqué sur l'ancien
    mode radio (USB) qui masquerait le décodeur à tort."""
    ctx = _make_ctx()
    ctx.eval("""
    rigState.enabled = true;
    rigState.mode = 'USB';
    currentMode = 'CW';
    document.getElementById('cwPanel').style.display = 'none';
    applyRigState({enabled: false});
    """)
    assert ctx.eval("document.getElementById('cwPanel').style.display") == ''


# ─── 3) Radio -> logiciel : syncBandModeFromRig() doit refléter le MODE ─────

def test_syncBandModeFromRig_repercute_un_changement_de_mode_fait_sur_la_radio():
    """Cœur du bug #2 remonté par F4GLD : passer la radio de SSB à CW sur
    l'appareil (pas dans LOGBOOK) doit mettre à jour currentMode."""
    ctx = _make_ctx()
    ctx.eval("""
    rigState.enabled = true;
    currentBand = '14'; currentMode = 'SSB';
    _currentVisibleBands = ['14'];
    _currentVisibleModes = ['SSB', 'CW'];
    __fetchCalls = [];
    syncBandModeFromRig(14023, 'CW');
    """)
    assert ctx.eval('currentMode') == 'CW', (
        'syncBandModeFromRig() doit répercuter le mode radio dans le carnet, '
        'pas seulement la bande')


def test_syncBandModeFromRig_ne_reboucle_pas_de_qsy_vers_la_radio():
    """La synchro radio -> carnet ne doit JAMAIS renvoyer une commande QSY à
    la radio -- elle vient de nous dire où elle est ; repousser créerait une
    boucle poll -> QSY -> poll (voir pickMode(mode, {fromRig:true}))."""
    ctx = _make_ctx()
    ctx.eval("""
    rigState.enabled = true;
    currentBand = '14'; currentMode = 'SSB';
    _currentVisibleBands = ['14'];
    _currentVisibleModes = ['SSB', 'CW'];
    __fetchCalls = [];
    syncBandModeFromRig(14023, 'CW');
    """)
    assert ctx.eval('__qsyCalls().length') == 0, (
        'la synchro radio->carnet ne doit poser aucun /rig/qsy en retour')


def test_syncBandModeFromRig_traduit_usb_lsb_vers_ssb():
    """La radio parle LSB/USB, le carnet ne connaît que SSB (un seul mode
    phonie) -- CIV_MODES/normaliser_mode côté serveur (logx_cat.py) posent
    déjà cette dualité, ce test vérifie juste le sens INVERSE côté carnet."""
    ctx = _make_ctx()
    ctx.eval("""
    rigState.enabled = true;
    currentBand = '14'; currentMode = 'CW';
    _currentVisibleBands = ['14'];
    _currentVisibleModes = ['SSB', 'CW'];
    syncBandModeFromRig(14200, 'USB');
    """)
    assert ctx.eval('currentMode') == 'SSB'


def test_syncBandModeFromRig_ignore_un_mode_non_autorise_par_le_concours():
    """Si le concours/les toggles n'autorisent pas AM (absent de
    _currentVisibleModes), la synchro ne doit RIEN changer plutôt que de
    forcer un mode que l'opérateur n'a pas activé."""
    ctx = _make_ctx()
    ctx.eval("""
    rigState.enabled = true;
    currentBand = '14'; currentMode = 'SSB';
    _currentVisibleBands = ['14'];
    _currentVisibleModes = ['SSB', 'CW'];
    syncBandModeFromRig(14200, 'AM');
    """)
    assert ctx.eval('currentMode') == 'SSB'


def test_syncBandModeFromRig_synchronise_toujours_aussi_la_bande():
    """Non-régression : le comportement bande déjà existant (seul chemin
    testé avant ce correctif) ne doit pas casser en ajoutant le mode."""
    ctx = _make_ctx()
    ctx.eval("""
    rigState.enabled = true;
    currentBand = '144'; currentMode = 'SSB';
    _currentVisibleBands = ['144', '14'];
    _currentVisibleModes = ['SSB', 'CW'];
    syncBandModeFromRig(14200, 'USB');
    """)
    assert ctx.eval('currentBand') == '14'
    assert ctx.eval('currentMode') == 'SSB'
