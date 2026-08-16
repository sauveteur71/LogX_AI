# -*- coding: utf-8 -*-
"""Aide au choix du périphérique audio du décodeur CW (retour F4GLD : « est
il possible dans le decodeur cw d'aider le choix du peripherique par
defaut »). Avant ce chantier, #cwDevice/#cwDevice2 ne listaient que des NOMS
système (navigator.mediaDevices.enumerateDevices()) -- aucun moyen de savoir
LEQUEL reçoit vraiment l'audio de la radio avant de cliquer "Démarrer".

CwPanel.testDevice() (logx_cw_panel.js), déclenché par onchange sur
#cwDevice/#cwDevice2, ouvre le MÊME pipeline Goertzel que le décodage réel
(au ton déjà réglé) pendant quelques secondes et réutilise le vumètre
existant + un texte de statut dédié (#cwDeviceTestStatus/-2) pour dire si
un signal a été vu au-dessus du seuil.

Comme test_cwdecoder.py le documente pour le DSP (goertzelMagnitude/
getUserMedia = API navigateur, impossible à exercer sans vraie carte son),
on ne fait PAS tourner le vrai CwAudioDecoder ici : on le remplace par un
FAUX (même patron que MediaRecorder/getUserMedia dans
test_audio_recorder_client.py) qui expose start()/stop()/onLevel de façon
contrôlable depuis le test -- ce qui est exercé ici, c'est le BRANCHEMENT
CwPanel <-> UI (le seul code ajouté par ce chantier), pas le DSP lui-même
(déjà couvert par test_cwdecoder.py)."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CW_PANEL_JS_PATH = os.path.join(BASE, 'logx_cw_panel.js')
CW_PANEL2_AUDIO_JS_PATH = os.path.join(BASE, 'logx_cw_panel2_audio.js')
HTML_PATH = os.path.join(BASE, 'logx_logbook.html')


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


# Même Proxy DOM générique que test_cw_panel_consolidation.py, plus un
# setTimeout/clearTimeout CONTRÔLABLES (le vrai testDevice() programme le
# verdict final -- "signal détecté"/"aucun signal" -- 4s après le début du
# test ; un setTimeout no-op comme dans les autres suites ne le déclencherait
# jamais) et un FAUX CwAudioDecoder qui rejoue le comportement de
# CwAudioDecoder.start()/stop()/onLevel sans dépendre d'aucune API audio
# réelle.
_DOM_PREAMBLE = r"""
var __store = {};
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:'', style:{}, className:'', checked:false, disabled:false, files:[], children:[]};
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
      if(prop === 'replaceChildren') return function(){ s.children = []; };
      return s[prop];
    },
    set:function(target, prop, val){ s[prop] = val; return true; }
  };
  return new Proxy({}, handler);
}
var document = {
  getElementById: function(id){ if(!__store[id]) __store[id] = ElProxy(); return __store[id]; },
  createElement: function(){ return ElProxy(); },
  createTextNode: function(t){ return {text:t}; },
  querySelector: function(){ return ElProxy(); },
  querySelectorAll: function(){ return []; },
  addEventListener: function(){}, removeEventListener: function(){},
  body: ElProxy(), documentElement: ElProxy(),
};
var window = this;
window.addEventListener = function(){};
window.removeEventListener = function(){};
// setTimeout/clearTimeout contrôlables depuis le test (voir __fireTimer ci-dessous)
// -- un simple stub "return 0" (comme les autres suites CW) ne déclencherait
// jamais le verdict final du test de périphérique, qui vit DANS le callback.
var __timerId = 0;
var __timers = {};
function setTimeout(fn, delay){ var id = ++__timerId; __timers[id] = fn; return id; }
function clearTimeout(id){ delete __timers[id]; }
function __fireTimer(id){ var fn = __timers[id]; if(fn){ delete __timers[id]; fn(); } }
function setInterval(){ return 0; }
function clearInterval(){}
var localStorage = {
  _d:{}, getItem:function(k){ return (k in this._d)? this._d[k] : null; },
  setItem:function(k,v){ this._d[k]=String(v); }, removeItem:function(k){ delete this._d[k]; }
};
function fetch(){ return Promise.resolve({ ok:false, json: function(){ return Promise.resolve({}); } }); }
function alert(){}
function confirm(){ return false; }
function prompt(){ return null; }
var navigator = { userAgent:'test', mediaDevices: { enumerateDevices: function(){ return Promise.resolve([]); } }, clipboard:{} };
function notify(msg){ window.__lastNotify = msg; }
function trF(tpl, vars){ return tpl.replace(/\{(\w+)\}/g, function(_, k){ return (vars && vars[k]) || ''; }); }
function cwToCall(){}

// ─── FAUX CwAudioDecoder : même surface que logx_cwdecoder.js, sans DSP réel ──
var __cwDecoderInstances = [];
var __cwStartShouldReject = false;
function CwAudioDecoder(opts){
  this.freq = opts.freq;
  this.onChar = opts.onChar || function(){};
  this.onLevel = opts.onLevel || function(){};
  this.started = false;
  this.stopped = false;
  __cwDecoderInstances.push(this);
}
CwAudioDecoder.prototype.start = function(deviceId){
  this.deviceId = deviceId;
  var self = this;
  if(__cwStartShouldReject) return Promise.reject(new Error('Permission refusée (test)'));
  return Promise.resolve().then(function(){ self.started = true; });
};
CwAudioDecoder.prototype.stop = function(){ this.stopped = true; };
CwAudioDecoder.prototype.setFreq = function(hz){ this.freq = hz; };
"""


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_read(CW_PANEL_JS_PATH))
    ctx.eval(_read(CW_PANEL2_AUDIO_JS_PATH))
    return ctx


def _last_decoder(ctx):
    return "__cwDecoderInstances[__cwDecoderInstances.length-1]"


# ─── Câblage HTML : le sélecteur déclenche bien le test au changement ───────

def test_html_declenche_le_test_au_changement_de_peripherique():
    html = _read(HTML_PATH)
    assert 'id="cwDevice"' in html and 'onchange="cwTestDevice()"' in html
    assert 'id="cwDevice2"' in html and 'onchange="cwTestDevice2()"' in html
    # Élément de statut dédié pour les deux radios (SO2R Phase 2)
    assert 'id="cwDeviceTestStatus"' in html
    assert 'id="cwDeviceTestStatus2"' in html


# ─── Signal détecté / aucun signal ───────────────────────────────────────────

def test_signal_detecte_pendant_le_test_affiche_le_verdict_positif():
    ctx = _make_ctx()
    ctx.eval("cwTestDevice();")   # await dec.start() se résout en microtâche
    assert ctx.eval("__cwDecoderInstances.length") == 1
    assert ctx.eval(f"{_last_decoder(ctx)}.started") is True
    # Statut affiché pendant le test
    assert 'Test du périphérique' in ctx.eval("document.getElementById('cwDeviceTestStatus').textContent")

    # Le pipeline (faux) rapporte un niveau au-dessus du seuil, comme un vrai
    # signal CW reçu sur ce périphérique.
    ctx.eval(f"{_last_decoder(ctx)}.onLevel(0.5, 0.1, 0);")
    timer_id = ctx.eval("_cwPanel('').testTimer")
    assert timer_id, "testDevice() doit programmer le verdict final via setTimeout"
    ctx.eval(f"__fireTimer({timer_id});")

    status = ctx.eval("document.getElementById('cwDeviceTestStatus').textContent")
    assert 'Signal détecté' in status
    assert ctx.eval("document.getElementById('cwDeviceTestStatus').className") == 'cw-device-test good'
    # Le décodeur de test est bien arrêté une fois le verdict rendu (pas de
    # flux micro qui continue à tourner en arrière-plan après le test).
    assert ctx.eval(f"{_last_decoder(ctx)}.stopped") is True


def test_aucun_signal_pendant_le_test_affiche_le_verdict_negatif():
    ctx = _make_ctx()
    ctx.eval("cwTestDevice();")
    timer_id = ctx.eval("_cwPanel('').testTimer")
    ctx.eval(f"__fireTimer({timer_id});")   # jamais de onLevel au-dessus du seuil entre-temps

    status = ctx.eval("document.getElementById('cwDeviceTestStatus').textContent")
    assert 'Aucun signal détecté' in status
    assert ctx.eval("document.getElementById('cwDeviceTestStatus').className") == 'cw-device-test bad'


def test_micro_indisponible_affiche_un_message_d_erreur():
    ctx = _make_ctx()
    ctx.eval("__cwStartShouldReject = true;")
    ctx.eval("cwTestDevice();")
    status = ctx.eval("document.getElementById('cwDeviceTestStatus').textContent")
    assert 'Micro indisponible' in status
    assert 'Permission refusée' in status


# ─── Ouverture du panneau : test automatique du périphérique déjà affiché ───
# Avant ce correctif (15/08/2026), testDevice() n'était déclenché QUE par le
# onchange du sélecteur -- un opérateur qui ouvre le panneau, voit une liste
# déjà remplie et clique directement sur Démarrer SANS jamais toucher au
# sélecteur ne recevait donc AUCUNE validation avant de lancer une session :
# un mauvais périphérique par défaut (micro intégré du PC au lieu de
# l'interface radio) donnait un silence total, indiscernable d'un bug DSP.

def test_ouverture_du_panneau_teste_automatiquement_le_peripherique():
    ctx = _make_ctx()
    assert ctx.eval("__cwDecoderInstances.length") == 0
    ctx.eval("toggleCwPanel();")   # ouverture -- pas de await, comme testDevice() lui-même
    assert ctx.eval("__cwDecoderInstances.length") == 1, (
        "l'ouverture du panneau doit déclencher un test de périphérique automatique")
    assert ctx.eval(f"{_last_decoder(ctx)}.started") is True
    assert 'Test du périphérique' in ctx.eval("document.getElementById('cwDeviceTestStatus').textContent")


def test_ouverture_du_panneau_radio2_teste_le_bon_selecteur():
    ctx = _make_ctx()
    ctx.eval("toggleCwPanel2();")
    assert ctx.eval("__cwDecoderInstances.length") == 1
    # Le statut de la RADIO 2 est renseigné, celui de la radio 1 reste vierge.
    assert 'Test du périphérique' in ctx.eval("document.getElementById('cwDeviceTestStatus2').textContent")
    assert ctx.eval("document.getElementById('cwDeviceTestStatus').textContent") == ''


def test_ouverture_du_panneau_pendant_un_decodage_reel_ne_lance_pas_de_second_test():
    """testDevice() refuse déjà d'ouvrir un second flux si un décodage réel
    tourne (voir plus bas) -- vérifie que le déclenchement automatique à
    l'ouverture respecte la même règle."""
    ctx = _make_ctx()
    ctx.eval("toggleCwDecoder();")   # démarre un vrai décodage (radio 1)
    assert ctx.eval("__cwDecoderInstances.length") == 1
    ctx.eval("_cwPanelInstances[''].devicesLoaded = false;")   # force le chemin "première ouverture"
    ctx.eval("toggleCwPanel();")
    assert ctx.eval("__cwDecoderInstances.length") == 1, (
        "aucun second flux ne doit s'ouvrir tant qu'un décodage réel tourne déjà")


# ─── Radio 2 : instance indépendante (SO2R Phase 2) ─────────────────────────

def test_cwtestdevice2_est_independant_de_la_radio_1():
    ctx = _make_ctx()
    ctx.eval("cwTestDevice();")
    ctx.eval("cwTestDevice2();")
    assert ctx.eval("__cwDecoderInstances.length") == 2
    # Chaque radio a son propre texte de statut, non partagé.
    ctx.eval("document.getElementById('cwDeviceTestStatus').textContent = 'RADIO1';")
    ctx.eval("document.getElementById('cwDeviceTestStatus2').textContent = 'RADIO2';")
    assert ctx.eval("document.getElementById('cwDeviceTestStatus').textContent") == 'RADIO1'
    assert ctx.eval("document.getElementById('cwDeviceTestStatus2').textContent") == 'RADIO2'


# ─── Non-interférence avec un vrai décodage en cours ────────────────────────

def test_toggleDecoder_arrete_un_test_en_cours_avant_de_demarrer():
    """Un clic sur "Démarrer" pendant qu'un test de périphérique tourne encore
    doit d'abord couper le flux du test -- sinon deux flux audio concurrents
    sur la même entrée (voir _stopTest() dans toggleDecoder())."""
    ctx = _make_ctx()
    ctx.eval("cwTestDevice();")
    # Capture l'INDICE de l'instance de test (pas "la dernière", qui pointera
    # vers le décodeur réel une fois toggleCwDecoder() appelé juste après).
    test_index = ctx.eval("__cwDecoderInstances.length - 1")
    assert ctx.eval(f"__cwDecoderInstances[{test_index}].stopped") is False

    ctx.eval("toggleCwDecoder();")   # démarre le VRAI décodage
    assert ctx.eval(f"__cwDecoderInstances[{test_index}].stopped") is True, (
        "le décodeur du test aurait dû être arrêté avant le démarrage du vrai décodage")
    assert ctx.eval("__cwDecoderInstances.length") == 2   # 1 test + 1 décodage réel
    assert ctx.eval("_cwPanel('').decoder") is not None


def test_testDevice_ignore_si_un_decodage_reel_tourne_deja():
    """Changer de périphérique PENDANT un décodage réel ne doit pas ouvrir un
    second flux concurrent -- le vumètre appartient déjà au décodage réel."""
    ctx = _make_ctx()
    ctx.eval("toggleCwDecoder();")   # démarre un vrai décodage
    assert ctx.eval("__cwDecoderInstances.length") == 1

    ctx.eval("cwTestDevice();")   # changement de périphérique pendant ce décodage
    assert ctx.eval("__cwDecoderInstances.length") == 1, (
        "testDevice() n'aurait pas dû créer un second flux pendant un décodage réel")
