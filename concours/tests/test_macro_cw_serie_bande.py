# -*- coding: utf-8 -*-
"""Macro CW {NR} : le numéro ÉMIS sur l'air doit être celui qui est LOGGUÉ.

Deux formules produisaient « le numéro de série » selon qu'il était émis ou
enregistré :

  - émis    : expandMacro()  →  String(qsoLog.length + 1)      (compteur GLOBAL)
  - loggué  : submitQSO()    →  nextSerial(bande) → /log/next_serial
                             →  logx_storage.allocate_next_serial (PAR BANDE)

expandMacro() est le vrai chemin d'émission : copyMacro() poste le texte au
keyer de la radio (POST /rig/cw), et le mode ESM (Entrée enchaîne appel →
échange → log) y passe systématiquement en CW via esmSend('exchange') →
copyMacro(1) — la macro F2 par défaut étant « 59 {NR} {LOC} ».

Les deux formules ne coïncident que sur un concours mono-bande : dès le
premier QSO d'une deuxième bande l'écart est garanti et croît à chaque QSO.
Cela touche tous les concours à auto_serial (DEFAULT_EXCHANGE : tous les
VHF/UHF/SHF multi-bandes — IARU UHF, Marconi, Rallye des Points Hauts — plus
CQ WPX). Le correspondant note alors un numéro absent de notre log, et au
cross-check les deux QSO tombent ; l'opérateur n'a aucun recours, le champ
N° ENVOYÉ étant readOnly par conception (cf. updateSerialDisplay).

Ce module exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via
py_mini_racer) avec un DOM minimal — même approche que
tests/test_logbook_render_window_reset.py — et capture le corps RÉELLEMENT
posté à /rig/cw (keyer) et à /log/add (log), plutôt que de recalculer quoi
que ce soit à côté."""
import os
import subprocess

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
# EV-7 phase 2 : rigState (lu par copyMacro()/esmSend(), tous deux exercés par
# ce scénario) vit désormais dans logx_hardware_cat.js, chargé en <script>
# classique AVANT logx_logbook.js dans logx_logbook.html (portée globale
# partagée, même principe que JS_EXTRAITS_EV7 dans
# test_logbook_menu_debut_fin.py). Seulement pour rev=None (HEAD) -- une
# révision historique antérieure à l'extraction contient déjà tout dans
# logx_logbook.js, le concaténer casserait (redéclaration de "let rigState").
HARDWARE_JS_PATH = os.path.join(BASE, 'logx_hardware_cat.js')
# EV-7 16e incrément : checkCallStatus()/lookupQRZ()/checkPrevQsos() (appelées
# par la saisie de l'indicatif, exercée par __qso() ci-dessous) vivent
# désormais dans logx_callbook.js, même principe que HARDWARE_JS_PATH -- sans
# lui, ces fonctions sont indéfinies et le scénario __run() échoue en silence
# (__done reste false, aucune exception ne remonte à pytest).
CALLBOOK_JS_PATH = os.path.join(BASE, 'logx_callbook.js')
# EV-7 17e incrément : updateCallDB() (appelée par submitQSO() ligne
# "if(loc) updateCallDB(call, loc, null);", exercée par __qso() ci-dessous
# via son locator systématiquement renseigné) vit désormais dans
# logx_lookup.js, même principe que HARDWARE_JS_PATH/CALLBOOK_JS_PATH --
# ajouté PROACTIVEMENT cette fois (pas après un échec CI, cf. le correctif
# précédent sur ce même fichier) en retraçant l'appel réel avant extraction.
LOOKUP_JS_PATH = os.path.join(BASE, 'logx_lookup.js')
# EV-7 19e incrément : esmMode/esmExchanged/esmHandleEnter()/esmSend() (le
# scénario ci-dessous assigne esmMode/esmExchanged directement et appelle
# esmHandleEnter() -- voir __initConcoursCW()/__qso() plus bas) vivent
# désormais dans logx_esm_callbot.js, même principe que les 3 fichiers
# précédents -- ajouté PROACTIVEMENT en retraçant l'appel réel avant
# extraction, comme pour LOOKUP_JS_PATH.
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')

# Commit juste AVANT ce correctif — sert à prouver que le scénario ci-dessous
# échoue bien sur le code d'origine (sinon ce ne serait pas un test de
# non-régression).
REV_AVANT_CORRECTIF = '461b306'

# ─── DOM minimal ──────────────────────────────────────────────────────────────
# logx_logbook.js est un script de page : Proxy générique pour les éléments DOM
# (n'importe quelle propriété lue/écrite est simplement mémorisée).
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

# ─── Serveur minimal ─────────────────────────────────────────────────────────
# /log/next_serial reproduit fidèlement logx_storage.allocate_next_serial :
# une séquence PAR BANDE (dans la portée du concours en cours). /rig/cw et
# /log/add ne font qu'enregistrer ce que le code envoie réellement.
_NET_STUB = r"""
var __cwSent = [];        // textes réellement postés au keyer de la radio
var __logged = [];        // QSO réellement postés à /log/add
var __serverSerial = {};  // allocateur serveur, par bande
function __ok(payload){
  return Promise.resolve({ok:true, status:200, json:function(){ return Promise.resolve(payload); }});
}
function fetch(url, opts){
  url = String(url);
  var body = {};
  try{ body = (opts && opts.body) ? JSON.parse(opts.body) : {}; }catch(e){}
  if(url.indexOf('/log/next_serial') === 0){
    var band = decodeURIComponent((url.split('band=')[1] || '').split('&')[0]);
    __serverSerial[band] = (__serverSerial[band] || 0) + 1;
    var s = String(__serverSerial[band]);
    while(s.length < 3) s = '0' + s;
    return __ok({serial: s});
  }
  if(url.indexOf('/rig/cw') === 0){ __cwSent.push(body.text); return __ok({ok:true}); }
  if(url.indexOf('/log/add') === 0){ __logged.push(body); return __ok({ok:true}); }
  return __ok({});
}
"""

# ─── Le scénario terrain ─────────────────────────────────────────────────────
# IARU UHF/SHF (absent de CONTEST_EXCHANGE → DEFAULT_EXCHANGE, auto_serial),
# radio pilotée en CW, ESM actif : chaque QSO passe par esmHandleEnter() →
# esmSend('exchange') → copyMacro(1) (macro F2 « 59 {NR} {LOC} »), puis
# submitQSO(). On enregistre, pour chaque QSO, le texte envoyé au keyer, la
# valeur affichée dans le champ N° ENVOYÉ et le num_sent réellement loggué.
_SCENARIO = r"""
var __results = [];
var __done = false;

function __initConcoursCW(){
  localStorage.setItem('logx_config', JSON.stringify({callsign:'F4TEST', locator:'JN03QQ'}));
  myCall = 'F4TEST'; myLocator = 'JN03QQ'; myOp = 'OP1';
  usageMode = 'contest';
  currentContest = 'IARU_UHF';
  applyExchangeFormat('IARU_UHF');
  qsoLog = [];
  serialByBand = {};
  __cwSent = []; __logged = []; __serverSerial = {};
  rigState.enabled = true; rigState.mode = 'CW';   // keyer radio actif
  esmMode = true; esmExchanged = false;            // ESM : Entrée enchaîne
  pickBand('144');
}

async function __qso(call, band){
  if(band !== currentBand) pickBand(band);
  document.getElementById('inputCall').value = call;
  document.getElementById('inputLocator').value = 'JN03QQ';
  var ui = document.getElementById('inputNumSent').value;      // ce que voit l'opérateur
  esmHandleEnter();                                            // → keyer CW
  var keyer = __cwSent[__cwSent.length - 1];
  await submitQSO();                                           // → /log/add
  __results.push({call:call, band:band, ui:ui, keyer:keyer,
                  logged: __logged[__logged.length - 1].num_sent});
}

async function __run(plan){
  __initConcoursCW();
  for(var i = 0; i < plan.length; i++){
    await __qso(plan[i][0], plan[i][1]);
  }
  __done = true;
}
"""

_PLAN = [['DL1AAA', '144'], ['ON4BBB', '144'], ['G3CCC', '144'],
         ['PA0DDD', '432'], ['EA1EEE', '432'], ['OK1FFF', '1296']]


def _real_source(rev=None):
    """Source réelle de logx_logbook.js : HEAD par défaut, ou `rev` pour
    rejouer le scénario tel qu'il était AVANT ce correctif."""
    if rev is None:
        with open(HARDWARE_JS_PATH, encoding='utf-8') as f:
            hw = f.read()
        with open(CALLBOOK_JS_PATH, encoding='utf-8') as f:
            cb = f.read()
        with open(LOOKUP_JS_PATH, encoding='utf-8') as f:
            lk = f.read()
        with open(ESM_CALLBOT_JS_PATH, encoding='utf-8') as f:
            esm = f.read()
        with open(JS_PATH, encoding='utf-8') as f:
            return hw + '\n' + cb + '\n' + lk + '\n' + esm + '\n' + f.read()
    out = subprocess.run(
        ['git', 'show', f'{rev}:concours/logx_logbook.js'],
        cwd=BASE, capture_output=True, text=True, encoding='utf-8', check=True)
    return out.stdout


def _make_ctx(rev=None):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_real_source(rev))
    ctx.eval(_NET_STUB)      # après la source : remplace le fetch du préambule
    ctx.eval(_SCENARIO)
    return ctx


def _run_plan(rev=None, plan=None):
    ctx = _make_ctx(rev)
    import json
    ctx.eval(f'__run({json.dumps(plan or _PLAN)});')
    assert ctx.eval('__done') is True, 'le scénario ne s’est pas déroulé entièrement'
    return ctx, ctx.eval('JSON.stringify(__results)')


def _results(rev=None, plan=None):
    import json
    ctx, raw = _run_plan(rev, plan)
    return ctx, json.loads(raw)


def _nr_du_keyer(texte):
    """« 59 004 JN03QQ » → « 004 » (2e jeton de la macro F2 par défaut)."""
    return texte.split()[1]


# ─── Reproduction du bug sur le code d'AVANT le correctif ────────────────────

def test_reproduction_bug_avant_correctif():
    """Sur le commit d'origine, le keyer envoie un numéro absent du log dès
    qu'on change de bande — et l'écart croît à chaque QSO."""
    _, res = _results(rev=REV_AVANT_CORRECTIF)
    assert len(res) == 6
    # Mono-bande : les deux formules coïncident encore.
    for r in res[:3]:
        assert _nr_du_keyer(r['keyer']) == r['logged']
    # Dès la 2e bande, divergence garantie sur TOUS les QSO suivants.
    diverge = [r for r in res if _nr_du_keyer(r['keyer']) != r['logged']]
    assert [r['call'] for r in diverge] == ['PA0DDD', 'EA1EEE', 'OK1FFF']
    assert [_nr_du_keyer(r['keyer']) for r in diverge] == ['004', '005', '006']
    assert [r['logged'] for r in diverge] == ['001', '002', '001']


def test_reproduction_ecart_croissant_avant_correctif():
    """30 QSO sur 144 puis passage sur 432 : le keyer annonce 031 alors que le
    log enregistre 001 (et l'écart ne se résorbe jamais)."""
    plan = [[f'F4X{i:03d}', '144'] for i in range(30)] + [['PA0DDD', '432']]
    _, res = _results(rev=REV_AVANT_CORRECTIF, plan=plan)
    dernier = res[-1]
    assert dernier['band'] == '432'
    assert _nr_du_keyer(dernier['keyer']) == '031'
    assert dernier['ui'] == '001'
    assert dernier['logged'] == '001'


# ─── Le même scénario sur le code ACTUEL ─────────────────────────────────────

def test_keyer_cw_envoie_le_numero_reellement_loggue():
    """Chemin ESM/CW complet : ce que la radio émet == ce qui est loggué."""
    _, res = _results()
    assert len(res) == 6
    for r in res:
        assert _nr_du_keyer(r['keyer']) == r['logged'], r
        assert r['keyer'] == f"59 {r['logged']} JN03QQ", r
        # …et ce que voit l'opérateur à l'écran est ce même numéro.
        assert r['ui'] == r['logged'], r
    # La série est bien repartie à 001 sur chaque nouvelle bande.
    assert [r['logged'] for r in res] == ['001', '002', '003', '001', '002', '001']


def test_keyer_cw_ecart_croissant_corrige():
    """Le cas qui divergeait le plus fort (30 QSO d'avance) est corrigé."""
    plan = [[f'F4X{i:03d}', '144'] for i in range(30)] + [['PA0DDD', '432']]
    _, res = _results(plan=plan)
    dernier = res[-1]
    assert _nr_du_keyer(dernier['keyer']) == '001'
    assert dernier['ui'] == '001'
    assert dernier['logged'] == '001'


def test_bouton_macro_f2_hors_esm():
    """ESM désactivé, simple clic sur le bouton F2 du panneau macros (et son
    infobulle) : même numéro que le champ N° ENVOYÉ, après changement de bande."""
    plan = [[f'F4X{i:03d}', '144'] for i in range(30)]
    ctx, _ = _results(plan=plan)
    ctx.eval("""
    esmMode = false;
    pickBand('432');
    renderMacroPanel();
    __cwSent = [];
    copyMacro(1);              // clic sur le bouton « F2 » (macro échange)
    """)
    champ = ctx.eval("document.getElementById('inputNumSent').value")
    infobulle = ctx.eval("document.getElementById('macroBtns').children[1].title")
    keyer = ctx.eval('__cwSent[__cwSent.length - 1]')
    assert champ == '001'
    assert infobulle == '59 001 JN03QQ'
    assert keyer == '59 001 JN03QQ'


def test_echange_non_seriel_reste_la_valeur_du_champ():
    """Concours à échange non sériel (CQ WW : zone CQ) — {NR} doit rendre la
    valeur du champ, jamais un numéro de série inventé."""
    ctx = _make_ctx()
    ctx.eval("""
    __initConcoursCW();
    currentContest = 'CQ_WW_CW';
    applyExchangeFormat('CQ_WW_CW');
    document.getElementById('inputNumSent').value = '14';
    """)
    assert ctx.eval("currentExchange.auto_serial") is False
    assert ctx.eval("expandMacro('59 {NR}')") == '59 14'


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    with open(JS_PATH, encoding='utf-8') as f:
        assert 'QSO Director' not in f.read()


# ─── esmSend() : CW manuel (sans CAT) ne doit JAMAIS partir en voix ──────────
# Bug trouvé le 08/08/2026 pendant l'extraction EV-7 du bloc RADIO CAT :
# esmSend() exigeait rigState.enabled pour router en CW, contrairement à
# updateKeyerPanels() (juste à côté) qui se contente du repli
# rigState.mode||currentMode SANS exiger .enabled -- un opérateur en CW
# manuel (clé/manip externe, pas de CAT branché) voyait ESM jouer un message
# VOCAL réel au lieu du CW attendu. Corrigé en alignant esmSend() sur le
# même repli que updateKeyerPanels().

def test_esm_en_cw_manuel_sans_cat_route_vers_le_keyer_pas_la_voix():
    """rigState.enabled=false (pas de CAT) mais currentMode='CW' : ESM doit
    quand même déclencher le keyer CW, jamais un message vocal audible."""
    ctx = _make_ctx()
    ctx.eval("""
    __initConcoursCW();
    rigState.enabled = false; rigState.mode = '';   // pas de CAT branché
    currentMode = 'CW';                              // mode saisi manuellement
    var __appels = {copyMacro: [], voicePlay: []};
    var _copyMacroReel = copyMacro, _voicePlayReel = voicePlay;
    copyMacro = function(idx){ __appels.copyMacro.push(idx); };
    voicePlay = function(slot){ __appels.voicePlay.push(slot); };
    esmSend('exchange');
    """)
    appels = ctx.eval('JSON.stringify(__appels)')
    import json
    appels = json.loads(appels)
    assert appels['copyMacro'] == [1], appels
    assert appels['voicePlay'] == [], appels


def test_esm_avec_cat_le_mode_radio_prime_sur_currentMode():
    """CAT connecté, radio en SSB mais le sélecteur de mode de saisie
    (currentMode) traîne encore sur CW (ex. juste après un changement de
    bande) -- c'est rigState.mode (la radio) qui doit faire foi, jamais
    currentMode quand le CAT est disponible."""
    ctx = _make_ctx()
    ctx.eval("""
    __initConcoursCW();
    rigState.enabled = true; rigState.mode = 'SSB';
    currentMode = 'CW';
    var __appels = {copyMacro: [], voicePlay: []};
    copyMacro = function(idx){ __appels.copyMacro.push(idx); };
    voicePlay = function(slot){ __appels.voicePlay.push(slot); };
    esmSend('exchange');
    """)
    appels = ctx.eval('JSON.stringify(__appels)')
    import json
    appels = json.loads(appels)
    assert appels['copyMacro'] == [], appels
    assert appels['voicePlay'] == ['V3'], appels


def test_esm_en_ssb_sans_cat_route_toujours_vers_la_voix():
    """Non-régression du cas sain : sans CAT et en SSB, ESM doit continuer à
    utiliser le keyer vocal (rien à voir avec .enabled, tout avec le mode)."""
    ctx = _make_ctx()
    ctx.eval("""
    __initConcoursCW();
    rigState.enabled = false; rigState.mode = '';
    currentMode = 'SSB';
    var __appels = {copyMacro: [], voicePlay: []};
    copyMacro = function(idx){ __appels.copyMacro.push(idx); };
    voicePlay = function(slot){ __appels.voicePlay.push(slot); };
    esmSend('exchange');
    """)
    appels = ctx.eval('JSON.stringify(__appels)')
    import json
    appels = json.loads(appels)
    assert appels['copyMacro'] == [], appels
    assert appels['voicePlay'] == ['V3'], appels
