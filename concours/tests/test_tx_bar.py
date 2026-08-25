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
