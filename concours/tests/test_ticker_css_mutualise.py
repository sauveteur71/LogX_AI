# -*- coding: utf-8 -*-
"""Composant ticker (.rcb-*) MUTUALISÉ dans le thème partagé, pas dupliqué.

Le composant de bandeau défilant (défilement rcb-defile + pause au survol +
repli prefers-reduced-motion) vivait inline dans logx_accueil.html. Pour qu'une
2e page (CHASSE) puisse l'utiliser, il est déplacé dans logx_theme.css (partagé,
chargé par les 20 pages via <link>, doctrine mutualisation CSS). Ce test
verrouille : le composant EST dans le thème, avec son repli reduced-motion, et
n'est PLUS re-déclaré inline dans accueil (sinon dérive silencieuse).
"""
import os
import re

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(nom):
    with open(os.path.join(CONCOURS, nom), encoding='utf-8') as f:
        return f.read()


def test_composant_ticker_dans_le_theme_partage():
    css = _lire('logx_theme.css')
    assert '@keyframes rcb-defile' in css, \
        "l'animation de défilement doit être mutualisée dans le thème"
    assert re.search(r'\.rcb-move\{[^}]*animation:[^}]*rcb-defile', css), \
        ".rcb-move doit porter l'animation rcb-defile dans le thème"


def test_repli_reduced_motion_dans_le_theme():
    css = _lire('logx_theme.css')
    assert re.search(
        r'prefers-reduced-motion:reduce\)\s*\{\s*\.rcb-move\{animation:none\}',
        css, re.S), "le thème doit couper rcb-move sous prefers-reduced-motion"


def test_accueil_ne_reduplique_plus_le_composant():
    h = _lire('logx_accueil.html')
    assert '@keyframes rcb-defile' not in h, \
        "accueil ne doit plus redéclarer le composant inline (mutualisé dans le thème)"
