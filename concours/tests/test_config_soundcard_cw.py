# -*- coding: utf-8 -*-
"""CONFIG : réglages soundcard CW (enabled/hz/wpm) — câblage HTML/save/load."""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CHAMPS = ['soundcard_cw_enabled', 'soundcard_cw_hz', 'soundcard_cw_wpm']


def _lire(nom):
    with open(os.path.join(BASE, nom), encoding='utf-8') as f:
        return f.read()


def test_champs_dans_le_html():
    html = _lire('logx_configuration.html')
    for c in _CHAMPS:
        assert ('id="%s"' % c) in html, c


def test_collecte_a_la_sauvegarde():
    js = _lire('logx_configuration.js')
    assert re.search(r"soundcard_cw_enabled:\s*document\.getElementById", js)
    assert re.search(r"soundcard_cw_hz:\s*_numClamped\(", js)
    assert re.search(r"soundcard_cw_wpm:\s*_numClamped\(", js)


def test_repeuples_au_chargement():
    js = _lire('logx_configuration.js')
    m = re.search(r"\[([^\[\]]*?'winkeyer_enabled'.*?)\]\.forEach\(k\s*=>", js, re.S)
    assert m, 'liste LOAD introuvable'
    for c in _CHAMPS:
        assert ("'%s'" % c) in m.group(1), 'load manquant: ' + c


def test_chaque_champ_a_une_aide():
    js = _lire('logx_configuration.js')
    for c in _CHAMPS:
        assert re.search(r'\b%s:\s*"' % c, js), 'aide manquante: ' + c


def test_script_soundcard_inclus_dans_logbook():
    html = _lire('logx_logbook.html')
    assert 'logx_cw_soundcard.js' in html
