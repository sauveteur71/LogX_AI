# -*- coding: utf-8 -*-
"""Nudges du coach → fil IA (logx_coach_fil.js) — testé en V8.

Le coach (déterministe, testé ailleurs) renvoie un nudge {level, text} ou None
via /coach/state?nudges=1. Ici on teste la traduction en entrée de fil :
un nudge 'action' devient une proposition, 'attention' une attention, et
l'absence de nudge ne pousse rien.
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_coach_fil.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("var window = {};")   # pas de fetch -> pas de démarrage auto
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_nudge_action_devient_proposition():
    ctx = _ctx()
    ctx.eval("window.__e = window.LogxCoachFil._entree({level:'action', text:'ZL nouveau DXCC sur 20 m — 14074'});")
    assert ctx.eval("window.__e.length") == 1
    assert ctx.eval("window.__e[0].type") == 'proposition'
    assert 'ZL' in ctx.eval("window.__e[0].texte")


def test_nudge_attention_devient_attention():
    ctx = _ctx()
    ctx.eval("window.__e = window.LogxCoachFil._entree({level:'attention', text:'Rythme en baisse'});")
    assert ctx.eval("window.__e[0].type") == 'attention'


def test_pas_de_nudge_ne_pousse_rien():
    ctx = _ctx()
    assert ctx.eval("window.LogxCoachFil._entree(null).length") == 0
    assert ctx.eval("window.LogxCoachFil._entree({level:'action'}).length") == 0   # sans texte


def test_cablage_logbook():
    with open(os.path.join(CONCOURS, 'logx_logbook.html'), encoding='utf-8') as f:
        h = f.read()
    assert 'src="logx_coach_fil.js"' in h
