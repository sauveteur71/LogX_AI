# -*- coding: utf-8 -*-
"""HEURE DE FIN auto (demande F4GLD) : le champ manuel « HEURE DE FIN (UTC) »
disparaît de la saisie ; `time_off` est renseigné AUTOMATIQUEMENT à
l'enregistrement, égal à l'heure du QSO (mêmes chiffres, sans « : »).

`time_off` reste une clé interne de plein droit (symétrie import/export ADIF,
contrôle de cohérence) — seule la SAISIE MANUELLE est retirée.
"""
import json
import os
import re

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()
JS = open(os.path.join(BASE, 'logx_logbook.js'), encoding='utf-8').read()


def _fn(src, header_re):
    """Extrait le corps { ... } de la fonction dont l'en-tête matche header_re."""
    m = re.search(header_re, src)
    assert m, header_re
    d = 0
    i = src.index('{', m.start())
    start = m.start()
    while True:
        if src[i] == '{':
            d += 1
        elif src[i] == '}':
            d -= 1
            if d == 0:
                return src[start:i + 1]
        i += 1


def test_champ_manuel_supprime_du_html():
    # Plus aucun input ni libellé « heure de fin » : la saisie manuelle disparaît.
    assert 'id="inputTimeOff"' not in HTML
    assert 'HEURE DE FIN' not in HTML


def test_collect_ne_lit_plus_le_champ_time_off():
    # Comportemental sur la VRAIE fonction : même si un inputTimeOff existait,
    # collectExtraFields ne le lit plus (clé retirée de la table).
    pytest.importorskip('py_mini_racer')
    from py_mini_racer import py_mini_racer as m
    c = m.MiniRacer()
    c.eval('var __v = %s;' % json.dumps({'inputTimeOff': '121545'}))
    c.eval("var document = { getElementById: function(id){ "
           "return (id in __v) ? {value: String(__v[id])} : null; } };")
    c.eval(_fn(JS, r'function collectExtraFields\('))
    q = json.loads(c.eval('JSON.stringify(collectExtraFields())'))
    assert 'time_off' not in q


def test_time_off_auto_derive_de_l_heure_du_qso():
    # Structurel sur submitQSO : time_off est dérivé de l'heure du QSO en
    # retirant le « : » (mêmes chiffres que TIME_ON) — pas une valeur saisie.
    corps = _fn(JS, r'(?:async\s+)?function submitQSO\(')
    assert re.search(r"\.time_off\s*=\s*[A-Za-z0-9_.]*time[A-Za-z0-9_.]*\.replace\(\s*/:/g?\s*,|"
                     r"\.time_off\s*=\s*[A-Za-z0-9_.]*time[A-Za-z0-9_.]*\.replace\(\s*['\"]:['\"]",
                     corps), corps[-400:]


def test_clearform_ne_reference_plus_input_time_off():
    corps = _fn(JS, r'function clearForm\(')
    assert 'inputTimeOff' not in corps
