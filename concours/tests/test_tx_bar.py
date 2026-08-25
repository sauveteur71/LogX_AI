# -*- coding: utf-8 -*-
"""Barre d'émission du LOGBOOK (concours/logx_tx_bar.js) — surface CLIENT du
consentement « émission unique » (#255). L'IA prépare via LogxTxBar.proposer(),
l'humain déclenche. On teste la LOGIQUE PURE (formatage, compte à rebours du
jeton, corps des requêtes /tx/*, machine d'état) dans un vrai moteur JS (V8),
pas le DOM ni les fetch (comme les autres tests JS du dépôt).
"""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_tx_bar.js')

# DOM minimal : logx_tx_bar.js s'auto-monte sur DOMContentLoaded, jamais tiré
# ici (aucun addEventListener déclenché). On expose juste ce qu'il lit au chargement.
_PREAMBLE = r"""
var window = {};
var document = { addEventListener:function(){}, getElementById:function(){return null;},
  createElement:function(){return {style:{},classList:{add:function(){},remove:function(){}},
    appendChild:function(){},setAttribute:function(){}};},
  head:{appendChild:function(){}}, body:{appendChild:function(){}} };
var setInterval = function(){ return 0; };
var clearInterval = function(){};
"""


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_PREAMBLE)
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_module_expose_api():
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxTxBar") == 'object'
    for fn in ('fmtFreqKhz', 'secondsLeft', 'ringPct', 'preparePayload',
               'authorizePayload', 'nextState'):
        assert ctx.eval(f"typeof window.LogxTxBar.{fn}") == 'function', fn


def test_proposer_avec_callback_client_declenche_le_callback():
    # Chemin CLIENT (ex. FT8) : ÉMETTRE exécute le callback local, PAS /tx/authorize.
    ctx = _ctx()
    ctx.eval("""
      window.LogxTxBar.state = 'idle';
      globalThis.__emis = 0;
      window.LogxTxBar.proposer({mode:'FT8', message:'F4ABC F1XYZ -12'},
                                function(){ globalThis.__emis++; });
    """)
    assert ctx.eval("window.LogxTxBar.state") == 'prepared'
    assert ctx.eval("typeof window.LogxTxBar._onConfirm") == 'function'
    ctx.eval("window.LogxTxBar._emettre();")
    assert ctx.eval("globalThis.__emis") == 1              # callback exécuté une fois
    assert ctx.eval("window.LogxTxBar._onConfirm") is None  # consommé (usage unique)


def test_proposer_auto_emet_apres_delai():
    # Niveau 2 copilote : proposer(em, cb, autoMs) arme une auto-émission après
    # `autoMs` ms. _tick l'exécute UNE fois le délai écoulé (sauf annulation).
    ctx = _ctx()
    ctx.eval("""
      window.LogxTxBar.state = 'idle';
      globalThis.__emis = 0;
      window.LogxTxBar.proposer({mode:'FT8', message:'F4ABC F1XYZ -12'},
                                function(){ globalThis.__emis++; }, 8000);
    """)
    assert ctx.eval("window.LogxTxBar._autoAt > 0") is True   # auto-émission armée
    # délai NON écoulé -> aucun _tick n'émet
    ctx.eval("window.LogxTxBar._tick();")
    assert ctx.eval("globalThis.__emis") == 0
    # délai écoulé (_autoAt dans le passé) -> auto-émission UNE fois
    ctx.eval("window.LogxTxBar._autoAt = 1; window.LogxTxBar._tick();")
    assert ctx.eval("globalThis.__emis") == 1
    # trace : l'auto-émission est marquée 'copilote_auto' (délai écoulé, pas un clic)
    assert ctx.eval("window.LogxTxBar._declencheur") == 'copilote_auto'
    ctx.eval("window.LogxTxBar._tick();")                     # pas de ré-émission
    assert ctx.eval("globalThis.__emis") == 1


def test_emission_copilote_poste_une_trace_audit():
    # Traçabilité verrouillée : à l'émission copilote (chemin client FT8), la
    # barre POSTe /tx/trace pour graver l'action dans le journal d'audit serveur.
    ctx = _ctx()
    ctx.eval("""
      globalThis.__fetches = [];
      globalThis.fetch = function(url, opts){
        globalThis.__fetches.push({url:url, body:(opts&&opts.body)||''});
        return { then: function(){ return { then: function(){} }; } };
      };
      window.LogxTxBar.state = 'idle';
      window.LogxTxBar.proposer({mode:'FT8', message:'F4ABC F1XYZ -12',
        operator:'F1XYZ', radio_id:'F4ABC', frequency_hz:14074000}, function(){});
      window.LogxTxBar._emettre();
    """)
    urls = ctx.eval("globalThis.__fetches.map(function(f){return f.url;}).join(',')")
    assert '/tx/trace' in urls                    # trace POSTée
    body = ctx.eval("(globalThis.__fetches.filter(function(f){"
                    "return f.url==='/tx/trace';})[0]||{}).body")
    assert 'F4ABC F1XYZ -12' in body              # le message émis est tracé
    assert 'copilote' in body                     # déclencheur présent (manuel ici)


def test_proposer_sans_delai_n_auto_emet_jamais():
    # Niveau 1 'copilote' (autoMs omis) : jamais d'auto-émission, geste humain requis.
    ctx = _ctx()
    ctx.eval("""
      window.LogxTxBar.state = 'idle';
      globalThis.__emis = 0;
      window.LogxTxBar.proposer({mode:'FT8', message:'x'},
                                function(){ globalThis.__emis++; });
    """)
    assert ctx.eval("window.LogxTxBar._autoAt") == 0          # pas armée
    ctx.eval("window.LogxTxBar._tick();")
    assert ctx.eval("globalThis.__emis") == 0


def test_fmt_freq_khz_francais():
    ctx = _ctx()
    # 14 074 000 Hz -> "14 074,0" kHz (espace milliers, virgule décimale FR)
    assert ctx.eval("window.LogxTxBar.fmtFreqKhz(14074000)") == '14 074,0'
    assert ctx.eval("window.LogxTxBar.fmtFreqKhz(7040000)") == '7 040,0'


def test_seconds_left_borne_0_30():
    ctx = _ctx()
    exp = "'2026-08-25T12:00:30Z'"
    # à T0 il reste 30 s
    assert ctx.eval(f"window.LogxTxBar.secondsLeft({exp}, Date.parse('2026-08-25T12:00:00Z'))") == 30
    # à T0+22s il reste 8 s
    assert ctx.eval(f"window.LogxTxBar.secondsLeft({exp}, Date.parse('2026-08-25T12:00:22Z'))") == 8
    # expiré -> jamais négatif
    assert ctx.eval(f"window.LogxTxBar.secondsLeft({exp}, Date.parse('2026-08-25T12:00:45Z'))") == 0


def test_auto_seconds_left():
    # Décompte d'auto-émission (niveau 2) affiché à l'opérateur : secondes
    # ENTIÈRES restantes (arrondi au plafond), jamais négatif, 0 si non armé.
    ctx = _ctx()
    now = "Date.parse('2026-08-25T12:00:00Z')"
    at8 = "Date.parse('2026-08-25T12:00:08Z')"
    assert ctx.eval(f"window.LogxTxBar.autoSecondsLeft({at8}, {now})") == 8
    # 7,4 s restantes -> 8 (plafond, on n'annonce pas moins de temps qu'il n'en reste)
    assert ctx.eval(f"window.LogxTxBar.autoSecondsLeft({at8}, {now} + 600)") == 8
    # 0,3 s restantes -> 1
    assert ctx.eval(f"window.LogxTxBar.autoSecondsLeft({at8}, {now} + 7700)") == 1
    # écoulé -> 0
    assert ctx.eval(f"window.LogxTxBar.autoSecondsLeft({at8}, {now} + 9000)") == 0
    # non armé (0) -> 0
    assert ctx.eval(f"window.LogxTxBar.autoSecondsLeft(0, {now})") == 0


def test_ring_pct():
    ctx = _ctx()
    assert ctx.eval("window.LogxTxBar.ringPct(30, 30)") == 100
    assert ctx.eval("window.LogxTxBar.ringPct(15, 30)") == 50
    assert ctx.eval("window.LogxTxBar.ringPct(0, 30)") == 0


def test_prepare_payload_reprend_l_apercu():
    ctx = _ctx()
    em = ("{operator:'F4GLD', radio_id:'rig1', frequency_hz:14074000, mode:'USB',"
          " power_w:50, message:'CQ TEST', ptt_method:'CAT'}")
    ctx.eval(f"var p = window.LogxTxBar.preparePayload({em});")
    assert ctx.eval("p.frequency_hz") == 14074000
    assert ctx.eval("p.mode") == 'USB'
    assert ctx.eval("p.power_w") == 50
    assert ctx.eval("p.message") == 'CQ TEST'
    assert ctx.eval("p.operator") == 'F4GLD'


def test_prepare_payload_inclut_voice_source():
    # choix WAV/TTS pour la phonie : transmis au serveur (/tx/prepare)
    ctx = _ctx()
    ctx.eval("var p = window.LogxTxBar.preparePayload({frequency_hz:14074000, mode:'USB', voice_source:'tts'});")
    assert ctx.eval("p.voice_source") == 'tts'
    # défaut = 'auto' (le serveur choisit selon accès internet/IA dispo)
    ctx.eval("var q = window.LogxTxBar.preparePayload({frequency_hz:14074000, mode:'USB'});")
    assert ctx.eval("q.voice_source") == 'auto'


def test_trace_payload_copilote():
    # Trace d'audit POSTée au serveur au déclenchement d'une émission copilote
    # (chemin client FT8). Reprend l'aperçu + le DÉCLENCHEUR (manuel vs auto).
    ctx = _ctx()
    em = ("{operator:'F1XYZ', radio_id:'F4ABC', frequency_hz:14074000,"
          " mode:'FT8', message:'F4ABC F1XYZ R-12'}")
    ctx.eval(f"var p = window.LogxTxBar.tracePayload({em}, 'copilote_auto');")
    assert ctx.eval("p.operator") == 'F1XYZ'
    assert ctx.eval("p.radio_id") == 'F4ABC'          # DX visé
    assert ctx.eval("p.frequency_hz") == 14074000
    assert ctx.eval("p.mode") == 'FT8'
    assert ctx.eval("p.message") == 'F4ABC F1XYZ R-12'
    assert ctx.eval("p.declencheur") == 'copilote_auto'
    # déclencheur par défaut = 'copilote' (confirmation manuelle)
    ctx.eval(f"var q = window.LogxTxBar.tracePayload({em});")
    assert ctx.eval("q.declencheur") == 'copilote'


def test_authorize_payload_borne_duree():
    ctx = _ctx()
    # duree_max OBLIGATOIRE (garde-fou serveur : émission bornée) + armed
    ctx.eval("var a = window.LogxTxBar.authorizePayload('tok-123', 3, true);")
    assert ctx.eval("a.token") == 'tok-123'
    assert ctx.eval("a.duree_max") == 3
    assert ctx.eval("a.armed") is True


def test_machine_etat_stop_reinitialise():
    ctx = _ctx()
    # idle -> prepared -> emitting ; STOP ramène TOUJOURS à 'idle' (arrêt d'urgence)
    assert ctx.eval("window.LogxTxBar.nextState('idle', 'PREPARE')") == 'prepared'
    assert ctx.eval("window.LogxTxBar.nextState('prepared', 'EMIT')") == 'emitting'
    assert ctx.eval("window.LogxTxBar.nextState('emitting', 'STOP')") == 'idle'
    assert ctx.eval("window.LogxTxBar.nextState('prepared', 'STOP')") == 'idle'
    # un refus serveur -> 'blocked' (l'humain doit re-préparer)
    assert ctx.eval("window.LogxTxBar.nextState('emitting', 'BLOCKED')") == 'blocked'
    assert ctx.eval("window.LogxTxBar.nextState('blocked', 'PREPARE')") == 'prepared'
