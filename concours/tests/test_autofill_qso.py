# -*- coding: utf-8 -*-
"""Lot 5 — auto-remplissage éditable + persistance des calculs.

autoFillQso(q) : persiste l'AZIMUT (bearing, jusqu'ici affiché mais jamais
stocké) et remplit pays/continent/zone CQ depuis l'indicatif (lookupDXCC) SANS
écraser une saisie manuelle. Le numéro DXCC et la zone ITU viennent du serveur
(cty.dat) -> sous-chantier B, pas ici.
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
    # stubs des dépendances existantes
    c.eval("function bearing(loc){ return loc === 'JN18AQ' ? 92.4 : null; }")
    c.eval("function lookupDXCC(call){ return call && call.indexOf('F') === 0 "
           "? {c:'France', ct:'EU', cq:14} : null; }")
    c.eval(_fn('autoFillQso'))
    return c


def _run(q):
    c = _ctx()
    return json.loads(c.eval("JSON.stringify(autoFillQso(%s))" % json.dumps(q)))


def test_persiste_azimut_arrondi():
    q = _run({'call': 'F4ABC', 'locator': 'JN18AQ'})
    assert q['ant_az'] == 92          # 92.4 arrondi


def test_remplit_pays_continent_zone_depuis_indicatif():
    q = _run({'call': 'F4ABC', 'locator': 'JN18AQ'})
    assert q['country'] == 'France' and q['cont'] == 'EU' and q['cqz'] == '14'


def test_n_ecrase_pas_une_saisie_manuelle():
    q = _run({'call': 'F4ABC', 'locator': 'JN18AQ', 'country': 'CORSE', 'cqz': '33'})
    assert q['country'] == 'CORSE' and q['cqz'] == '33'   # préservés


def test_indicatif_inconnu_ne_remplit_rien():
    q = _run({'call': 'ZZ9ZZ', 'locator': ''})
    assert 'country' not in q and 'ant_az' not in q


def test_submitqso_appelle_autofill():
    assert 'autoFillQso(' in JS
