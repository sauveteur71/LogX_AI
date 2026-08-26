# -*- coding: utf-8 -*-
"""RTTY — rttyEnvoyerTexte ne doit PAS être ré-entrant (audit STRATE-3).
Pendant un envoi en vol (await txAudioPtt), seul #rttySendBtn est désactivé ;
les boutons macro (F1-F12) appellent rttyEnvoyerTexte directement (l.428) et
ne sont PAS bloqués -> un clic macro pendant l'émission relance un txAudioPtt
concurrent = deux formes d'onde RTTY simultanées brouillées on-air. Un verrou
de ré-entrance doit faire échouer le second appel tant que le premier n'a pas
fini. Même classe de bug que le validateur CW (#313)."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(CONCOURS, 'logx_rtty.html')


def _fn(nom):
    src = open(HTML, encoding='utf-8').read()
    m = re.search(r'\n\s*(?:window\.\w+\s*=\s*)?(async\s+)?function ' + re.escape(nom) + r'\s*\(', src)
    assert m, 'fonction %s introuvable' % nom
    prefix = 'async ' if m.group(1) else ''
    i = src.index('function', m.start())
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return prefix + src[i:k + 1]
    raise AssertionError('accolade fermante introuvable')


_HARNESS = """
var _rttyTxArmed = true;
var _rttyTxBusy = false;
var txCalls = 0;
var _resolveTx = null;
function txAudioPtt(wave, sr, out){ txCalls++; return new Promise(function(r){ _resolveTx = r; }); }
function rttyTons(){ return {mark:2125, space:2295}; }
function rttyEncodeSamples(t, o){ return new Float32Array(8); }
function notify(m){}
function trF(s){ return s; }
var _stubEl = {value:'', disabled:false, textContent:'', style:{}};
var document = { getElementById:function(id){ return _stubEl; } };
"""


def _ctx():
    racer = pytest.importorskip('py_mini_racer')
    ctx = racer.MiniRacer()
    ctx.eval(_HARNESS)
    ctx.eval(_fn('rttyEnvoyerTexte'))
    return ctx


def test_second_envoi_pendant_le_premier_ne_relance_pas_txAudioPtt():
    ctx = _ctx()
    # Premier envoi : entre, arme le verrou, se suspend sur await txAudioPtt.
    ctx.eval("rttyEnvoyerTexte('CQ CQ DE F4GLD');")
    assert ctx.eval("txCalls") == 1
    # Second envoi (clic macro) PENDANT que le premier est en vol : doit sortir
    # sans rappeler txAudioPtt.
    ctx.eval("rttyEnvoyerTexte('TEST 599');")
    assert ctx.eval("txCalls") == 1, "ré-entrance : txAudioPtt appelé deux fois en concurrence"


def test_envoi_possible_de_nouveau_apres_fin_du_premier():
    ctx = _ctx()
    ctx.eval("rttyEnvoyerTexte('CQ');")
    assert ctx.eval("txCalls") == 1
    # Le premier envoi se termine.
    ctx.eval("_resolveTx({ok:true});")
    ctx.eval("0")  # laisse les microtâches se vider entre deux eval
    # Un nouvel envoi doit repartir normalement.
    ctx.eval("rttyEnvoyerTexte('CQ');")
    assert ctx.eval("txCalls") == 2, "le verrou ne s'est pas relâché après la fin de l'envoi"
