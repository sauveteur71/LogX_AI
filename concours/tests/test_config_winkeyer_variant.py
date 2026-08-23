# -*- coding: utf-8 -*-
"""CONFIG : sélecteur de variante WinKeyer (WK3 / K3NG) — câblage HTML/save/load."""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(nom):
    with open(os.path.join(BASE, nom), encoding='utf-8') as f:
        return f.read()


def test_select_variante_dans_le_html_avec_les_deux_options():
    html = _lire('logx_configuration.html')
    bloc = html[html.index('id="winkeyer_variant"'):]
    bloc = bloc[:bloc.index('</select>')]
    assert 'value="WK3"' in bloc and 'value="K3NG"' in bloc


def test_collecte_a_la_sauvegarde():
    js = _lire('logx_configuration.js')
    assert re.search(r"winkeyer_variant:\s*document\.getElementById", js)


def test_repeuple_au_chargement():
    js = _lire('logx_configuration.js')
    m = re.search(r"\[([^\[\]]*?'winkeyer_enabled'.*?)\]\.forEach\(k\s*=>", js, re.S)
    assert m and "'winkeyer_variant'" in m.group(1)


def test_a_une_aide():
    js = _lire('logx_configuration.js')
    assert re.search(r'\bwinkeyer_variant:\s*"', js)
