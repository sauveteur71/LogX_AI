# -*- coding: utf-8 -*-
"""Copilote NL — handler client de l'action 'filtre' (suite de #318). L'agent
peut proposer un pending {type:'filtre', dx_continents, spotter_continents} ;
logx_carte.html doit le DÉCRIRE et, à la validation, l'appliquer via
/spots/filter (PAS le confondre avec un QSY, l'ancien `else` par défaut).
Test STRUCTUREL : on extrait les fonctions et on vérifie que la branche 'filtre'
route bien vers /spots/filter, plus un contrôle de syntaxe JS via py_mini_racer."""
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


def test_execAction_route_le_filtre_vers_spots_filter():
    corps = _fn('execAction')
    # La branche 'filtre' doit exister ET poster /spots/filter (jamais /rig/qsy).
    assert "action.type==='filtre'" in corps
    m = re.search(r"action\.type===''?filtre''?\)\{(.*?)\}else", corps, re.S)
    assert m, "branche 'filtre' introuvable"
    bloc = m.group(1)
    assert '/spots/filter' in bloc
    assert 'dx_continents' in bloc and 'spotter_continents' in bloc
    assert '/rig/qsy' not in bloc          # ne confond pas filtre et QSY


def test_renderActionCard_decrit_le_filtre():
    corps = _fn('renderActionCard')
    assert "action.type==='filtre'" in corps
    assert 'Filtrer les spots' in corps


def test_syntaxe_js_des_fonctions_editees():
    racer = pytest.importorskip('py_mini_racer')
    ctx = racer.MiniRacer()
    # stubs minimaux pour que la définition (pas l'exécution) soit valide
    ctx.eval("var rcT=function(s){return s;}, rcTf=function(s){return s;}, "
             "document={getElementById:function(){return {};},createElement:function(){return {style:{},appendChild:function(){}};}}, "
             "fetch=function(){return Promise.resolve({json:function(){return {};}});};")
    # définir les 2 fonctions ne doit pas lever (syntaxe correcte)
    ctx.eval(_fn('renderActionCard'))
    ctx.eval(_fn('execAction'))
