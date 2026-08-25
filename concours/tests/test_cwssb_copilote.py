# -*- coding: utf-8 -*-
"""Copilote CW/SSB (concours/logx_cwssb_copilote.js) — glue PURE et testable du
copilote hors FT8. Principe identique au copilote FT8 : l'IA PRÉPARE le message
d'échange (report + série/zone du concours actif), l'HUMAIN déclenche via ÉMETTRE
(barre de consentement). PROPOSE-ONLY, pas d'auto-émission (aucun flux décodé en
CW/SSB). Le message est CALCULÉ par le LOGBOOK (expandMacro/gabarit voix, mûrs) ;
ce module ne fait que décider s'il faut proposer et emballer la proposition.

Exécute le VRAI logx_cwssb_copilote.js dans un moteur JS réel (V8).
"""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_cwssb_copilote.js')

_PREAMBLE = "var window = {};\n"


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_PREAMBLE)
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_api_exposee():
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxCwSsbCopilote") == 'object'
    for fn in ('familleMode', 'doitProposer', 'messagePropose', 'cle'):
        assert ctx.eval(f"typeof window.LogxCwSsbCopilote.{fn}") == 'function', fn


def test_famille_mode_cw_phonie_data():
    ctx = _ctx()
    F = "window.LogxCwSsbCopilote.familleMode"
    for m in ('CW', 'CW-R', 'cw'):
        assert ctx.eval(f"{F}('{m}')") == 'cw', m
    for m in ('SSB', 'USB', 'LSB', 'FM', 'AM'):
        assert ctx.eval(f"{F}('{m}')") == 'phonie', m
    # modes DATA : PAS ce copilote (le FT8 a le sien) -> null
    for m in ('FT8', 'FT4', 'RTTY', 'PSK31', ''):
        assert ctx.eval(f"{F}('{m}')") is None, m


def test_doit_proposer_seulement_actif_call_et_mode_cw_ssb():
    ctx = _ctx()
    D = "window.LogxCwSsbCopilote.doitProposer"
    assert ctx.eval(f"{D}(true, 'F4ABC', 'CW')") is True
    assert ctx.eval(f"{D}(true, 'F4ABC', 'SSB')") is True
    # copilote éteint -> jamais
    assert ctx.eval(f"{D}(false, 'F4ABC', 'CW')") is False
    # pas d'indicatif -> jamais
    assert ctx.eval(f"{D}(true, '', 'CW')") is False
    assert ctx.eval(f"{D}(true, '   ', 'CW')") is False
    # mode data -> jamais (hors périmètre CW/SSB)
    assert ctx.eval(f"{D}(true, 'F4ABC', 'FT8')") is False


def test_message_propose_emballe_pour_la_barre():
    ctx = _ctx()
    ctx.eval("var p = window.LogxCwSsbCopilote.messagePropose("
             "'F4ABC 599 042', 'F4ABC', 'CW', 14030000, 'F1XYZ', 'auto');")
    assert ctx.eval("p.mode") == 'CW'
    assert ctx.eval("p.message") == 'F4ABC 599 042'
    assert ctx.eval("p.frequency_hz") == 14030000
    assert ctx.eval("p.operator") == 'F1XYZ'
    assert ctx.eval("p.radio_id") == 'F4ABC'          # correspondant visé, jamais l'humain
    assert ctx.eval("p.voice_source") == 'auto'
    # phonie : la source voix demandée est transmise (WAV/TTS/auto)
    ctx.eval("var q = window.LogxCwSsbCopilote.messagePropose("
             "'F4ABC 59 042', 'F4ABC', 'USB', 14200000, 'F1XYZ', 'wav');")
    assert ctx.eval("q.voice_source") == 'wav'


def test_cle_anti_spam_idempotente():
    ctx = _ctx()
    C = "window.LogxCwSsbCopilote.cle"
    assert ctx.eval(f"{C}('F4ABC','F4ABC 599 042')") == ctx.eval(f"{C}('f4abc','f4abc 599 042')")
    assert ctx.eval(f"{C}('F4ABC','F4ABC 599 042')") != ctx.eval(f"{C}('F4ABC','F4ABC 599 043')")
