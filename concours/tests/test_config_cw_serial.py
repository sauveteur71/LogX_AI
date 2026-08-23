# -*- coding: utf-8 -*-
"""Réglages keyer série DTR/RTS côté CONFIG (Phase 3C) : câblage HTML/save/load.

Les 4 champs (enabled/port/line/wpm) doivent être dans le HTML, collectés à la
SAUVEGARDE et repeuplés au CHARGEMENT, chacun avec une aide. Test structurel :
la vérif du LOAD isole la vraie liste de population (pas une simple présence).
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CHAMPS = ['cw_serial_enabled', 'cw_serial_port', 'cw_serial_line', 'cw_serial_wpm']


def _lire(nom):
    with open(os.path.join(BASE, nom), encoding='utf-8') as f:
        return f.read()


def test_champs_presents_dans_le_html():
    html = _lire('logx_configuration.html')
    for c in _CHAMPS:
        assert ('id="%s"' % c) in html, c


def test_collecte_a_la_sauvegarde():
    js = _lire('logx_configuration.js')
    assert re.search(r"cw_serial_enabled:\s*document\.getElementById", js)
    assert re.search(r"cw_serial_port:\s*document\.getElementById", js)
    assert re.search(r"cw_serial_line:\s*document\.getElementById", js)
    assert re.search(r"cw_serial_wpm:\s*_numClamped\(", js)


def test_repeuples_au_chargement():
    js = _lire('logx_configuration.js')
    m = re.search(r"\[([^\[\]]*?'winkeyer_enabled'.*?)\]\.forEach\(k\s*=>", js, re.S)
    assert m, 'liste de population du LOAD introuvable'
    liste = m.group(1)
    for c in _CHAMPS:
        assert ("'%s'" % c) in liste, 'load manquant: ' + c


def test_chaque_champ_a_une_aide():
    js = _lire('logx_configuration.js')
    for c in _CHAMPS:
        assert re.search(r'\b%s:\s*"' % c, js), 'description manquante: ' + c


def test_ligne_propose_dtr_et_rts():
    html = _lire('logx_configuration.html')
    bloc = html[html.index('id="cw_serial_line"'):]
    bloc = bloc[:bloc.index('</select>')]
    assert 'value="DTR"' in bloc and 'value="RTS"' in bloc
