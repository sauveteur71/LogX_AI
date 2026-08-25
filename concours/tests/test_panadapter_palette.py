# -*- coding: utf-8 -*-
"""Panadapter : choix de palette du waterfall (colormap). couleurNiveau + PALETTES
extraits du fichier LIVRÉ et exécutés en V8. La palette « cuivre » (identité)
reste le DÉFAUT ; « gris » et « thermique » sont opt-in. Source-agnostique
(opère sur le 0-255 commun aux trois sources, après remap de contraste)."""
import json
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANADAPTER = os.path.join(CONCOURS, 'logx_panadapter.html')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _lire():
    with open(PANADAPTER, encoding='utf-8') as f:
        return f.read()


def _ctx(palette):
    src = _lire()
    pals = re.search(r'const PALETTES = \{.*?\n  \};', src, re.S)
    fn = re.search(r'  function couleurNiveau\(.*?\n  \}', src, re.S)
    assert pals and fn, 'PALETTES/couleurNiveau introuvables'
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("var paletteMode = '%s';" % palette)
    ctx.eval(pals.group(0))
    ctx.eval(fn.group(0))
    return ctx


def _rgb(ctx, v):
    return json.loads(ctx.eval("JSON.stringify(couleurNiveau(%d))" % v))


def test_gris_est_un_niveau_de_gris_lineaire():
    ctx = _ctx('gris')
    assert _rgb(ctx, 0) == [0, 0, 0]
    assert _rgb(ctx, 255) == [255, 255, 255]
    r, g, b = _rgb(ctx, 128)
    assert r == g == b and 120 <= r <= 136          # milieu gris neutre


def test_cuivre_conserve_l_identite():
    ctx = _ctx('cuivre')
    # bas de l'échelle = le fond HUD graphite (identité), pas du noir pur
    assert _rgb(ctx, 0) == [23, 24, 26]


def test_thermique_monte_du_sombre_vers_le_vif():
    ctx = _ctx('thermique')
    bas = _rgb(ctx, 0)
    haut = _rgb(ctx, 255)
    assert sum(bas) < sum(haut)                      # le haut de l'échelle est plus lumineux
    assert haut[0] >= 200                            # sommet chaud (rouge/blanc dominant)


def test_palette_inconnue_retombe_sur_cuivre():
    ctx = _ctx('nexistepas')
    assert _rgb(ctx, 0) == [23, 24, 26]              # repli sûr = identité


def test_cable_selecteur_et_persistance():
    src = _lire()
    assert 'id="paPalette"' in src
    assert "setItem('rc_pa_palette'" in src
    # couleurNiveau dispatche sur paletteMode via PALETTES
    fn = re.search(r'function couleurNiveau\(.*?\n  \}', src, re.S).group(0)
    assert 'PALETTES[' in fn and 'paletteMode' in fn
