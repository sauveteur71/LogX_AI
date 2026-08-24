# -*- coding: utf-8 -*-
"""Lot 3 — références multiples (my_refs/refs) + rétro-compat my_sig.

Une même activation peut être SOTA ET POTA (« two-fer ») : on stocke une LISTE
`{program, ref}`. Rétro-compat : la 1re ref = my_sig/my_sig_info (l'export ADIF
actuel, mono-valué, continue de marcher tant que B ne généralise pas le mapping).
"""
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(BASE, 'logx_logbook.js'), encoding='utf-8').read()


def _fn(name):
    m = re.search(r'function %s\(' % re.escape(name), JS)
    assert m, name
    d = 0
    i = JS.index('{', m.start())
    while True:
        if JS[i] == '{':
            d += 1
        elif JS[i] == '}':
            d -= 1
            if d == 0:
                return JS[m.start():i + 1]
        i += 1


def _ctx():
    c = py_mini_racer.MiniRacer()
    c.eval(_fn('refsToMySig'))
    c.eval(_fn('mySigToRefs'))
    return c


def test_my_sig_vers_refs_synthetise_la_liste():
    c = _ctx()
    q = json.loads(c.eval("(function(){var q={my_sig:'POTA',my_sig_info:'FR-1234'};"
                          "mySigToRefs(q);return JSON.stringify(q);})()"))
    assert q['my_refs'] == [{'program': 'POTA', 'ref': 'FR-1234'}]


def test_my_sig_vers_refs_correspondant():
    c = _ctx()
    q = json.loads(c.eval("(function(){var q={sig:'SOTA',sig_info:'F/AB-1'};"
                          "mySigToRefs(q);return JSON.stringify(q);})()"))
    assert q['refs'] == [{'program': 'SOTA', 'ref': 'F/AB-1'}]


def test_refs_vers_my_sig_prend_le_premier():
    c = _ctx()
    q = json.loads(c.eval("(function(){var q={my_refs:[{program:'SOTA',ref:'F/AB-1'},"
                          "{program:'POTA',ref:'FR-2'}]};refsToMySig(q);return JSON.stringify(q);})()"))
    assert q['my_sig'] == 'SOTA' and q['my_sig_info'] == 'F/AB-1'


def test_rien_a_faire_si_aucune_reference():
    c = _ctx()
    q = json.loads(c.eval("(function(){var q={call:'F4ABC'};mySigToRefs(q);refsToMySig(q);"
                          "return JSON.stringify(q);})()"))
    assert 'my_refs' not in q and 'my_sig' not in q


def test_submitqso_et_edit_utilisent_les_helpers():
    assert 'refsToMySig(' in JS   # submitQSO recopie my_refs[0] -> my_sig avant envoi
    edit = open(os.path.join(BASE, 'logx_edit_qso.js'), encoding='utf-8').read()
    assert 'mySigToRefs(' in edit  # la modale reconstitue la liste à l'ouverture
