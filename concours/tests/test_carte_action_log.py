# -*- coding: utf-8 -*-
"""Copilote NL — handler client de l'action 'log' (loguer une station). L'agent
propose {type:'log', call, band, mode, rst, freq_khz?} ; logx_carte.html doit le
DÉCRIRE et, à la validation, l'ajouter via /log/add (jamais confondu avec un QSY
ou un filtre). Test STRUCTUREL + contrôle de syntaxe JS."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(CONCOURS, 'logx_carte.html')


def _fn(nom):
    src = open(HTML, encoding='utf-8').read()
    m = re.search(r'\n(async\s+)?function ' + re.escape(nom) + r'\s*\(', src)
    assert m, 'fonction %s introuvable' % nom
    i = m.start() + 1
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return src[i:k + 1]
    raise AssertionError('accolade fermante introuvable')


def test_execAction_route_le_log_vers_log_add():
    corps = _fn('execAction')
    assert "action.type==='log'" in corps
    m = re.search(r"action\.type==='log'\)\{(.*?)\}else", corps, re.S)
    assert m, "branche 'log' introuvable"
    bloc = m.group(1)
    assert '/log/add' in bloc
    assert 'rst_sent' in bloc and 'rst_rcvd' in bloc
    assert '/rig/qsy' not in bloc and '/spots/filter' not in bloc


def test_renderActionCard_decrit_le_log():
    corps = _fn('renderActionCard')
    assert "action.type==='log'" in corps
    assert 'Loguer' in corps


def test_syntaxe_js():
    racer = pytest.importorskip('py_mini_racer')
    ctx = racer.MiniRacer()
    ctx.eval("var rcT=function(s){return s;}, rcTf=function(s){return s;}, "
             "document={getElementById:function(){return {};},createElement:function(){return {style:{},appendChild:function(){}};}}, "
             "fetch=function(){return Promise.resolve({json:function(){return {};}});};")
    ctx.eval(_fn('renderActionCard'))
    ctx.eval(_fn('execAction'))
