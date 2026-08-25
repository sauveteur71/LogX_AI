# -*- coding: utf-8 -*-
"""Grille départements (concours/logx_dept_grid.js) — pavé 00–99 à clic direct
pour la saisie (demande F4GLD 25/08). On teste la glue PURE : la liste
métropolitaine (INSEE, miroir de la liste serveur) et la règle d'affichage
(uniquement quand l'échange reçu EST un département). Exécuté en V8.
"""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_dept_grid.js')

_PREAMBLE = "var window = {};\n"


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_PREAMBLE)
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_api_exposee():
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxDeptGrid") == 'object'
    for fn in ('codesMetro', 'doitAfficher', 'render', 'surligner'):
        assert ctx.eval(f"typeof window.LogxDeptGrid.{fn}") == 'function', fn


def test_codes_metro_liste_insee():
    ctx = _ctx()
    ctx.eval("var C = window.LogxDeptGrid.codesMetro();")
    # 95 numéros métropolitains, mais le 20 est scindé en 2A/2B -> 96 cases
    assert ctx.eval("C.length") == 96
    for code in ('01', '19', '2A', '2B', '21', '75', '95'):
        assert ctx.eval(f"C.indexOf('{code}') !== -1") is True, code
    # jamais de 20 (Corse = 2A/2B), ni 00, ni au-delà de 95, ni DOM 3 chiffres
    for absent in ('20', '00', '96', '99', '971'):
        assert ctx.eval(f"C.indexOf('{absent}') !== -1") is False, absent
    # 2A/2B insérés À LA PLACE du 20 (entre 19 et 21)
    assert ctx.eval("C.indexOf('2A') === C.indexOf('19') + 1") is True
    assert ctx.eval("C.indexOf('21') === C.indexOf('2B') + 1") is True


def test_doit_afficher_seulement_pour_echange_departement():
    ctx = _ctx()
    D = "window.LogxDeptGrid.doitAfficher"
    assert ctx.eval(f"{D}('DEPT RCU')") is True
    assert ctx.eval(f"{D}('Dept rcu')") is True
    # série VHF/UHF, zone, état… -> cachée (ne jamais écrire un dept dans une série)
    for labr in ('N° REÇU', 'ZONE RCU', 'ÉTAT/PROV', 'CLASSE RCU', ''):
        assert ctx.eval(f"{D}({labr!r})") is False, labr
