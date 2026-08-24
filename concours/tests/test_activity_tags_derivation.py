# -*- coding: utf-8 -*-
"""Lot 4 — tags multi-activité cumulés (activity_tags).

Un QSO = FT8 + SOTA + QRP + DX… en une dimension cherchable, ORTHOGONALE au
concours (`contest`). Beaucoup sont AUTO-dérivés (mode, puissance, références,
lieu, propagation) ; l'opérateur ajoute/retire des tags MANUELS que le recalcul
auto ne doit jamais effacer.
"""
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(BASE, 'logx_entry_tabs.js'), encoding='utf-8').read()


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


def _tags(qjson):
    c = py_mini_racer.MiniRacer()
    c.eval(_fn('deriveActivityTags'))
    return json.loads(c.eval("JSON.stringify(deriveActivityTags(%s))" % qjson))


def test_mode_devient_tag():
    assert 'FT8' in _tags('{"mode":"FT8"}')


def test_qrp_depuis_puissance():
    assert 'QRP' in _tags('{"mode":"CW","tx_pwr":5}')
    assert 'QRP' not in _tags('{"mode":"CW","tx_pwr":100}')


def test_sota_depuis_reference():
    assert 'SOTA' in _tags('{"mode":"SSB","my_refs":[{"program":"SOTA","ref":"F/AB-1"}]}')


def test_pota_depuis_reference_correspondant():
    assert 'POTA' in _tags('{"mode":"SSB","refs":[{"program":"POTA","ref":"FR-1"}]}')


def test_portable_depuis_lieu():
    assert 'PORTABLE' in _tags('{"mode":"SSB","operating_location":"PORTABLE"}')


def test_prop_mode_devient_tag():
    assert 'EME' in _tags('{"mode":"CW","prop_mode":"EME"}')


def test_pas_de_doublon():
    t = _tags('{"mode":"SSB","prop_mode":"SAT","sat_name":"IO-117"}')
    assert t.count('SAT') <= 1


def test_merge_preserve_les_manuels():
    c = py_mini_racer.MiniRacer()
    c.eval(_fn('mergeTags'))
    out = json.loads(c.eval("JSON.stringify(mergeTags(['FT8','DX'], ['SOTA']))"))
    assert 'SOTA' in out and 'FT8' in out and 'DX' in out


def test_ui_et_recherche_cables():
    html = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()
    assert 'id="activityTags"' in html
    assert 'activity_tags' in JS or 'activity_tags' in open(
        os.path.join(BASE, 'logx_logbook.js'), encoding='utf-8').read()
