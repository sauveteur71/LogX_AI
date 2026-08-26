# -*- coding: utf-8 -*-
"""Audit BASSE 705 : latLonToMaidenhead produit une lettre de champ HORS de la
plage valide A-R aux bornes exactes lon=+180 / lat=+90.

lon+=180 -> 360 ; Math.floor(360/20)=18 ; L[18]='S' (A-R = index 0..17). Le
locator 'SS..' est invalide. Un point GPS exactement à l'antiméridien ou au pôle
Nord (ou un arrondi qui y tombe) fabriquait donc un locator faux."""
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(BASE, 'logx_outils_autonomes.js')


def _extract(src, nom):
    m = re.search(r'\n\s*function ' + re.escape(nom) + r'\s*\(', src)
    assert m, 'fonction %s introuvable' % nom
    i = src.index('function', m.start())
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return src[i:k + 1]
    raise AssertionError('accolade fermante introuvable')


def _ctx():
    c = py_mini_racer.MiniRacer()
    c.eval(_extract(open(JS, encoding='utf-8').read(), 'latLonToMaidenhead'))
    return c


CHAMP_VALIDE = set('ABCDEFGHIJKLMNOPQR')   # A..R uniquement


def test_maidenhead_borne_lon_180_lat_90_reste_dans_A_R():
    c = _ctx()
    loc = c.eval("latLonToMaidenhead(90, 180)")
    assert loc[0] in CHAMP_VALIDE and loc[1] in CHAMP_VALIDE, \
        "champ hors A-R aux bornes (lon=180/lat=90) : locator=%r" % loc


def test_maidenhead_valeur_nominale_inchangee():
    # JN18 (Paris ~48.85N, 2.35E) : témoin que le correctif ne casse pas le cas courant.
    c = _ctx()
    loc = c.eval("latLonToMaidenhead(48.85, 2.35)")
    assert loc.startswith('JN18'), "valeur nominale altérée : %r" % loc
