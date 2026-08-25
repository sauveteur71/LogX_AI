# -*- coding: utf-8 -*-
"""Copilote FT8 (concours/logx_ft8_copilote.js) — glue PURE et testable du
niveau « copilote » du séquenceur FT8. Le séquenceur existant (logx_ft8.html,
#179) reste la source de vérité : il calcule le message suivant + logue. Ce
module ne décide QUE (a) faut-il proposer plutôt qu'auto-émettre, (b) comment
emballer la proposition pour LogxTxBar.proposer(), (c) l'anti-spam (idempotence).

Exécute le VRAI logx_ft8_copilote.js dans un moteur JS réel (V8 via py_mini_racer).
"""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_ft8_copilote.js')

_PREAMBLE = "var window = {};\n"


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_PREAMBLE)
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_api_exposee():
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxFt8Copilote") == 'object'
    for fn in ('doitProposer', 'messagePropose', 'cle'):
        assert ctx.eval(f"typeof window.LogxFt8Copilote.{fn}") == 'function', fn


def test_doit_proposer_seulement_au_niveau_copilote():
    ctx = _ctx()
    assert ctx.eval("window.LogxFt8Copilote.doitProposer('copilote')") is True
    # les autres niveaux gardent leur comportement (auto/manuel/etc.) : PAS de proposition
    for niv in ('manuel', 'assiste', 'sequenceur', 'auto', ''):
        assert ctx.eval(f"window.LogxFt8Copilote.doitProposer('{niv}')") is False, niv


def test_message_propose_emballe_pour_la_barre():
    ctx = _ctx()
    ctx.eval("var p = window.LogxFt8Copilote.messagePropose('F4ABC F1XYZ -12', 'F4ABC', 14074000, 'F1XYZ');")
    assert ctx.eval("p.mode") == 'FT8'
    assert ctx.eval("p.message") == 'F4ABC F1XYZ -12'   # message calculé par le séquenceur, tel quel
    assert ctx.eval("p.frequency_hz") == 14074000
    assert ctx.eval("p.operator") == 'F1XYZ'            # MON indicatif
    # la voix ne concerne pas le FT8 : source neutre
    assert ctx.eval("p.voice_source") == 'auto'


def test_cle_anti_spam_idempotente():
    ctx = _ctx()
    # même DX + même message TX -> même clé (un seul push par cycle 15 s malgré re-décodes)
    a = ctx.eval("window.LogxFt8Copilote.cle('F4ABC', 'F4ABC F1XYZ -12')")
    b = ctx.eval("window.LogxFt8Copilote.cle('F4ABC', 'F4ABC F1XYZ -12')")
    c = ctx.eval("window.LogxFt8Copilote.cle('F4ABC', 'F4ABC F1XYZ RR73')")
    assert a == b
    assert a != c            # message différent (étape suivante) -> clé différente
