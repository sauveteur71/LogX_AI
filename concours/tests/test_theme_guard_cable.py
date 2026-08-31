# -*- coding: utf-8 -*-
"""Parité : toute page qui lie logx_theme.css charge AUSSI le garde-fou de thème.

Sinon le détecteur « feuille de style bloquée » ne protégerait qu'une partie des
pages — et l'opérateur retomberait sur des symptômes épars et inexpliqués sur les
autres (le défaut d'origine)."""
import glob
import os

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_toute_page_theme_charge_le_garde_fou():
    manquantes = []
    for f in glob.glob(os.path.join(CONCOURS, '*.html')):
        s = open(f, encoding='utf-8').read()
        if 'logx_theme.css' in s and 'logx_theme_guard.js' not in s:
            manquantes.append(os.path.basename(f))
    assert not manquantes, (
        'ces pages lient le thème sans charger le garde-fou : %s' % manquantes)


def test_le_garde_fou_existe():
    assert os.path.exists(os.path.join(CONCOURS, 'logx_theme_guard.js'))
