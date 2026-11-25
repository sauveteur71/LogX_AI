# -*- coding: utf-8 -*-
"""PROPAG s'ouvre sur la bande RECOMMANDÉE, pas sur la première de la liste
(audit 25/11/2026 : le classement est trié par fréquence, la page s'ouvrait
sur le 160 m et mémorisait ce choix automatique pour toujours).

focusCharger() est EXTRAITE de logx_propagation.html, pas réimplémentée.
"""
import json
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
py_mini_racer = pytest.importorskip('py_mini_racer')


def _page():
    with open(os.path.join(CONCOURS, 'logx_propagation.html'), encoding='utf-8') as f:
        return f.read()


def _fn(src, nom):
    m = re.search(r'\n\s*async function ' + nom + r'\s*\(', src)
    assert m
    i = src.index('async', m.start())
    j, prof = src.index('{', i), 0
    for k in range(j, len(src)):
        prof += {'{': 1, '}': -1}.get(src[k], 0)
        if prof == 0:
            return src[i:k + 1]


def _charger(classement, bande_initiale=''):
    c = py_mini_racer.MiniRacer()
    c.eval("""
      var __st = {}, __el = {};
      var localStorage = {getItem: function(k){ return k in __st ? __st[k] : null; },
                          setItem: function(k, v){ __st[k] = String(v); }};
      var document = {getElementById: function(id){ return __el[id] || (__el[id] = {textContent:'', innerHTML:''}); }, title:''};
      var __rep = %s;
      function fetch(u){ return Promise.resolve({ok:true, json: function(){ return Promise.resolve(__rep); }}); }
      function T(s){ return s; } function Tf(s){ return s; }
      ['rendreClassement','rendreSpots','rendreConcours','rendreRegions','rendreCarres',
       'rendreSuggestions','rendreRegle'].forEach(function(n){ this[n] = function(){}; }, this);
      var bande = %s, mode = '', bandes = [], enCours = false, focusChargeReussie = false;
    """ % (json.dumps({'classement': classement}), json.dumps(bande_initiale)))
    c.eval(_fn(_page(), 'focusCharger'))
    c.eval('focusCharger()')
    for _ in range(10):
        c.eval('0')
    return c


def test_ouvre_sur_la_bande_recommandee():
    c = _charger([{'band': '1.8', 'score': 5}, {'band': '7', 'score': 40},
                  {'band': '14', 'score': 30, 'recommandee': True}])
    assert c.eval('bande') == '14'


def test_sans_recommandation_meilleur_score():
    c = _charger([{'band': '1.8', 'score': 0}, {'band': '7', 'score': 12}, {'band': '14', 'score': 3}])
    assert c.eval('bande') == '7'


def test_choix_automatique_non_memorise():
    c = _charger([{'band': '14', 'score': 30, 'recommandee': True}])
    assert c.eval('JSON.stringify(__st)') == '{}'


def test_bande_deja_choisie_respectee():
    c = _charger([{'band': '14', 'score': 30, 'recommandee': True}], bande_initiale='21')
    assert c.eval('bande') == '21'


def test_seule_la_cle_choisie_est_lue_et_ecrite():
    s = re.sub(r'(?m)//.*$', '', _page())
    assert "localStorage.getItem('rc_focus_band')" not in s
    assert "localStorage.setItem('rc_focus_band'," not in s
    assert re.search(r"bande = el\.dataset\.b;\s*localStorage\.setItem\('rc_focus_band_choisie', bande\);", s)
