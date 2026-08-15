# -*- coding: utf-8 -*-
"""Tâche #92bis (15/08/2026, dernier point du backlog CARTE IA) : la dictée
vocale existante (auparavant strictement câblée sur #inputCall, LOGBOOK)
est généralisée pour aussi cibler #userInput (CARTE IA) — poser une question
à l'assistant IA au micro plutôt qu'au clavier.

Vérifie, en exécutant le VRAI logx_voice_dictation.js dans un moteur JS réel
(V8 via py_mini_racer) avec un DOM minimal et un SpeechRecognition simulé,
même approche que test_voicekeyer_panel_visibilite.py :

1. L'API historique (window.initCallDictation/toggleCallDictation) reste
   inchangée et continue de cibler #inputCall, en anglais forcé (alphabet
   OACI), avec la transformation phonétique -> indicatif compact.
2. La nouvelle instance (window.initChatDictation/toggleChatDictation) cible
   #userInput avec le transcript BRUT (pas de compaction façon indicatif),
   dans la langue d'interface courante (rc_lang), et jamais un envoi
   automatique du message (aucune fonction send() n'est appelée).
3. Sans SpeechRecognition disponible, les DEUX boutons micro (#callMicBtn et
   #chatMicBtn) restent masqués -- pas de bouton mort.
"""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_voice_dictation.js')

_DOM_PREAMBLE = r"""
var __store = {};
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:'', title:'', style:{}, checked:false, disabled:false};
  var cls = {_s:new Set(), add:function(){for(var i=0;i<arguments.length;i++) this._s.add(arguments[i]);},
             remove:function(){for(var i=0;i<arguments.length;i++) this._s.delete(arguments[i]);},
             contains:function(c){return this._s.has(c);},
             toggle:function(c,v){ var on = (v!==undefined) ? !!v : !this._s.has(c); if(on) this._s.add(c); else this._s.delete(c); return on;}};
  var handler = {
    get:function(target, prop){
      if(prop === 'classList') return cls;
      if(prop === 'style') return s.style;
      if(prop === 'focus') return function(){ s.focused = true; };
      return s[prop];
    },
    set:function(target, prop, val){ s[prop] = val; return true; }
  };
  return new Proxy({}, handler);
}
var document = {
  getElementById: function(id){ if(!__store[id]) __store[id] = ElProxy(); return __store[id]; },
};
var window = this;
var localStorage = {
  _d:{}, getItem:function(k){ return (k in this._d)? this._d[k] : null; },
  setItem:function(k,v){ this._d[k]=String(v); }, removeItem:function(k){ delete this._d[k]; }
};
var console = {log:function(){}, warn:function(){}, error:function(){}};

// SpeechRecognition simulée : capture la dernière instance créée (une par
// toggle*Dictation()) pour pouvoir déclencher onresult/onerror depuis Python.
function FakeSpeechRecognition(){
  this.onresult = null; this.onerror = null; this.onend = null;
  window.__lastRecognition = this;
}
FakeSpeechRecognition.prototype.start = function(){
  if (window.__forceStartError) throw new Error('start failed');
};
FakeSpeechRecognition.prototype.stop = function(){ if (this.onend) this.onend(); };
window.SpeechRecognition = FakeSpeechRecognition;

var __notified = [];
function notify(msg){ __notified.push(msg); }  // notify() global (logx_logbook.js) réutilisée par l'instance indicatif
window.__notified = __notified;
"""

_DOM_PREAMBLE_SANS_API = _DOM_PREAMBLE.replace(
    'window.SpeechRecognition = FakeSpeechRecognition;', '// pas de SpeechRecognition dans ce contexte')


@pytest.fixture
def moteur():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


@pytest.fixture
def moteur_sans_api():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE_SANS_API)
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_api_historique_conservee(moteur):
    assert moteur.eval("typeof window.initCallDictation") == 'function'
    assert moteur.eval("typeof window.toggleCallDictation") == 'function'


def test_nouvelle_api_chat_exposee(moteur):
    assert moteur.eval("typeof window.initChatDictation") == 'function'
    assert moteur.eval("typeof window.toggleChatDictation") == 'function'


def test_sans_speechrecognition_les_deux_boutons_micro_restent_caches(moteur_sans_api):
    moteur_sans_api.eval("initCallDictation(); initChatDictation();")
    assert moteur_sans_api.eval("document.getElementById('callMicBtn').style.display") == 'none'
    assert moteur_sans_api.eval("document.getElementById('chatMicBtn').style.display") == 'none'


def test_dictee_indicatif_reste_en_anglais_et_compacte_le_transcript(moteur):
    moteur.eval("toggleCallDictation();")
    assert moteur.eval("window.__lastRecognition.lang") == 'en-US'
    moteur.eval("window.__lastRecognition.onresult({results:[[{transcript:'foxtrot four golf lima delta'}]]});")
    assert moteur.eval("document.getElementById('inputCall').value") == 'F4GLD'


def test_dictee_chat_transcript_brut_langue_interface_par_defaut_francais(moteur):
    moteur.eval("toggleChatDictation();")
    assert moteur.eval("window.__lastRecognition.lang") == 'fr-FR'
    moteur.eval("window.__lastRecognition.onresult({results:[[{transcript:'quelle bande est ouverte en ce moment'}]]});")
    assert moteur.eval("document.getElementById('userInput').value") == 'quelle bande est ouverte en ce moment'


def test_dictee_chat_suit_la_langue_dinterface_choisie(moteur):
    moteur.eval("localStorage.setItem('rc_lang', 'de');")
    moteur.eval("toggleChatDictation();")
    assert moteur.eval("window.__lastRecognition.lang") == 'de-DE'


def test_dictee_chat_ne_declenche_jamais_denvoi_automatique(moteur):
    # Aucune fonction send()/isWaiting n'est définie dans ce DOM minimal --
    # si toggleChatDictation() ou son onresult tentait d'appeler send(), le
    # moteur JS lèverait une ReferenceError et ce test échouerait.
    moteur.eval("toggleChatDictation();")
    moteur.eval("window.__lastRecognition.onresult({results:[[{transcript:'CQ WW SSB ce week-end ?'}]]});")
    assert moteur.eval("document.getElementById('userInput').value") == 'CQ WW SSB ce week-end ?'


def test_dictee_chat_utilise_letat_actif_qbtn_coach_pas_active(moteur):
    moteur.eval("toggleChatDictation();")
    assert moteur.eval("document.getElementById('chatMicBtn').classList.contains('qbtn-coach')") is True
    assert moteur.eval("document.getElementById('chatMicBtn').classList.contains('active')") is False


def test_dictee_indicatif_utilise_letat_actif_active_par_defaut(moteur):
    moteur.eval("toggleCallDictation();")
    assert moteur.eval("document.getElementById('callMicBtn').classList.contains('active')") is True


def test_transcript_vide_ou_non_exploitable_notifie_sans_planter(moteur):
    moteur.eval("toggleChatDictation();")
    moteur.eval("window.__lastRecognition.onresult({results:[[{transcript:''}]]});")
    assert moteur.eval("document.getElementById('userInput').value") == ''
