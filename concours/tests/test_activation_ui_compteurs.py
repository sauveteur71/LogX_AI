# -*- coding: utf-8 -*-
"""Activation UI — refreshActivation affiche le compteur d'ÉLIGIBILITÉ (uniques
admissibles) et détaille brut + doublons (décision F4GLD ④). La barre de
progression suit l'éligible, pas le brut : sinon elle afficherait « 10/10 »
alors que le serveur juge l'activation non valide (9 uniques)."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_logbook.js')


def _fn(nom):
    src = open(JS, encoding='utf-8').read()
    m = re.search(r'\n\s*(async\s+)?function ' + re.escape(nom) + r'\s*\(', src)
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
var activationProgram = 'POTA', myActivationRef = 'FR-0123', lastActQsoTotal = 0;
var _els = { actProgress:{textContent:''}, actFill:{style:{width:''}},
  actValid:{innerHTML:''}, actP2P:{textContent:''}, actRef:{style:{color:''}} };
var document = { getElementById:function(id){ return _els[id] || null; } };
var _state = {};
function fetch(){ return Promise.resolve({ ok:true, json:function(){ return Promise.resolve(_state); } }); }
"""


def _run(state_js):
    racer = pytest.importorskip('py_mini_racer')
    c = racer.MiniRacer()
    c.eval(_HARNESS)
    c.eval("_state = %s;" % state_js)
    c.eval(_fn('refreshActivation'))
    c.eval("refreshActivation();")
    for _ in range(6):
        c.eval("0")
    return c


def test_progression_suit_l_eligible_et_montre_les_doublons():
    c = _run("{active:true, qso_total:11, qso_eligible:10, doublons:1, "
             "min_qso:10, valid:true, needed:0}")
    txt = c.eval("_els.actProgress.textContent")
    assert '10/10' in txt                     # éligible/seuil, pas 11/10
    assert 'doublon' in txt and '11 loggés' in txt


def test_sans_doublon_affiche_juste_le_ratio():
    c = _run("{active:true, qso_total:8, qso_eligible:8, doublons:0, "
             "min_qso:10, valid:false, needed:2}")
    txt = c.eval("_els.actProgress.textContent")
    assert txt == '8/10'                       # pas de mention de doublons
    assert c.eval("_els.actFill.style.width") == '80%'


def test_repli_serveur_ancien_sans_qso_eligible():
    c = _run("{active:true, qso_total:5, min_qso:10, valid:false, needed:5}")
    assert c.eval("_els.actProgress.textContent") == '5/10'
