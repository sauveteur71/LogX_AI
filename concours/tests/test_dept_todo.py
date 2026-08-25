# -*- coding: utf-8 -*-
"""Tri du panneau « départements À FAIRE » (logx_dept_todo.js) — décisions F4GLD :
fréquence par défaut (minimise le QSY), bascule rareté. Glue PURE, testée en V8.
"""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_dept_todo.js')

_PREAMBLE = "var window = {};\n"


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_PREAMBLE)
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


# cibles : dept 35 (donneur à 144.310), dept 29 (donneur à 144.290), dept 22
# (donneur à 144.500). known: 35 rare (1), 29 courant (5), 22 (3).
_TARGETS = ("[{dept:'35',name:'I-et-V',known:['A'],spotted:[{call:'F1A',freq:144310}]},"
            "{dept:'29',name:'Fin',known:['A','B','C','D','E'],spotted:[{call:'F1B',freq:144290}]},"
            "{dept:'22',name:'C-A',known:['A','B','C'],spotted:[{call:'F1C',freq:144500}]}]")


def test_tri_frequence_minimise_le_qsy():
    ctx = _ctx()
    # poste à 144.295 : le plus proche est 29 (144.290), puis 35 (144.310), puis 22 (144.500)
    ctx.eval(f"var r = window.LogxDeptTodo.trier({_TARGETS}, 'freq', 144.295);")
    assert ctx.eval("r.map(function(t){return t.dept;}).join(',')") == '29,35,22'


def test_tri_rarete_moins_de_stations_connues_dabord():
    ctx = _ctx()
    ctx.eval(f"var r = window.LogxDeptTodo.trier({_TARGETS}, 'rarete', 144.295);")
    # known: 35=1, 22=3, 29=5 -> le plus rare (35) d'abord
    assert ctx.eval("r.map(function(t){return t.dept;}).join(',')") == '35,22,29'


def test_donneurs_tries_par_proximite_dans_un_dept():
    ctx = _ctx()
    cibles = ("[{dept:'35',name:'x',known:[],spotted:["
              "{call:'LOIN',freq:144500},{call:'PRES',freq:144300}]}]")
    ctx.eval(f"var r = window.LogxDeptTodo.trier({cibles}, 'freq', 144.295);")
    # PRES (144.300) plus proche de 144.295 que LOIN (144.500) -> en tête
    assert ctx.eval("r[0].spotted.map(function(s){return s.call;}).join(',')") == 'PRES,LOIN'


def test_pur_ne_mute_pas_l_entree():
    ctx = _ctx()
    cibles = "[{dept:'35',name:'x',known:[],spotted:[{call:'B',freq:144500},{call:'A',freq:144300}]}]"
    ctx.eval(f"globalThis.src = {cibles};")
    ctx.eval("window.LogxDeptTodo.trier(globalThis.src, 'freq', 144.295);")
    # la liste source (et ses donneurs) n'est pas réordonnée
    assert ctx.eval("globalThis.src[0].spotted.map(function(s){return s.call;}).join(',')") == 'B,A'


def test_sans_rig_ordre_stable():
    ctx = _ctx()
    # freqMhz absent -> tri par fréquence absolue croissante (déterministe)
    ctx.eval(f"var r = window.LogxDeptTodo.trier({_TARGETS}, 'freq', 0);")
    assert ctx.eval("r.map(function(t){return t.dept;}).join(',')") == '29,35,22'
