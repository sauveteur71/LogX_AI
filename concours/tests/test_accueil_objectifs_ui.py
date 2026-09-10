# -*- coding: utf-8 -*-
"""Panneau « Mes objectifs de chasse » dans l'activité activation portable
(fusion D2, incr. 4e — port de logx_chasse.html, cf. test_chasse_objectifs_ui.py
pour l'équivalent CHASSE). Propriété CRITIQUE : les clés proposées à
l'opérateur doivent correspondre EXACTEMENT à celles du profil serveur
(logx_operator_goals.CLES) — sinon cocher/décocher ne piloterait aucun crédit.
Exécute le VRAI logx_accueil.js en V8 (py_mini_racer).
"""
import json
import os
import sys

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(CONCOURS, 'logx_accueil.js')

from test_accueil_activite import _make_ctx  # noqa: E402


def test_cles_ui_alignees_sur_le_serveur():
    ctx = _make_ctx()
    cles = json.loads(ctx.eval("JSON.stringify(OBJECTIFS_DEF.map(function(o){return o.cle}))"))
    if CONCOURS not in sys.path:
        sys.path.insert(0, CONCOURS)
    import logx_operator_goals as og
    assert set(cles) == set(og.CLES), 'les clés UI ne correspondent pas au profil serveur'
    assert len(cles) == len(og.CLES)             # pas de doublon


def test_expose_les_fonctions_objectifs():
    ctx = _make_ctx()
    for fn in ('construireObjectifs', 'lireObjectifs', 'enregistrerObjectifs', 'chargerObjectifs'):
        assert ctx.eval('typeof ' + fn) == 'function', fn


def test_construire_objectifs_tout_coche_par_defaut():
    ctx = _make_ctx()
    html = ctx.eval("construireObjectifs({}); document.getElementById('objectifsList').innerHTML")
    assert html.count('checked') == 5            # les 5 objectifs, défaut = actif


def test_construire_objectifs_respecte_un_objectif_decoche():
    ctx = _make_ctx()
    html = ctx.eval("construireObjectifs({dxcc:false}); document.getElementById('objectifsList').innerHTML")
    assert html.count('checked') == 4            # 1 des 5 décoché
