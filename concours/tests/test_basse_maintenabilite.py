# -*- coding: utf-8 -*-
"""Items BASSE (audit) — deux petits vrais correctifs.

1) logx_busted_call.js : verifierIndicatifApres incrementait le jeton _bcGen
   AVANT de valider l'entree. Un appel invalide (qso/call absent) bumpait donc
   _bcGen et annulait une verification legitime deja en vol (garde _gen!==_bcGen).
2) logx_calendrier.html : forceUpdate passait `currentYear` a loadYear() qui ne
   prend AUCUN argument (code mort trompeur) — retire.
"""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUSTED = os.path.join(CONCOURS, 'logx_busted_call.js')
CAL = os.path.join(CONCOURS, 'logx_calendrier.html')


def _fn(src, nom):
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


def _ctx():
    racer = pytest.importorskip('py_mini_racer')
    c = racer.MiniRacer()
    c.eval("var _bcGen = 0;"
           " function fetch(){ return new Promise(function(){}); }"  # jamais résolu
           " var document = { getElementById:function(){ return null; } };"
           " function encodeURIComponent(s){ return s; }")
    c.eval(_fn(open(BUSTED, encoding='utf-8').read(), 'verifierIndicatifApres'))
    return c


def test_appel_invalide_ne_bumpe_pas_le_jeton():
    c = _ctx()
    c.eval("verifierIndicatifApres(null);")
    c.eval("verifierIndicatifApres({});")            # pas de .call
    assert c.eval("_bcGen") == 0, "un appel invalide a incrementé _bcGen (annulerait une vérif en vol)"


def test_appel_valide_bumpe_le_jeton():
    c = _ctx()
    c.eval("verifierIndicatifApres({call:'F4GLD'});")
    assert c.eval("_bcGen") == 1


def test_calendrier_forceUpdate_n_appelle_plus_loadYear_avec_argument():
    src = open(CAL, encoding='utf-8').read()
    corps = _fn(src, 'forceUpdate')
    assert 'loadYear(' in corps
    assert not re.search(r'loadYear\(\s*[^)\s]', corps), \
        'forceUpdate passe encore un argument à loadYear() (qui n\'en prend aucun)'
