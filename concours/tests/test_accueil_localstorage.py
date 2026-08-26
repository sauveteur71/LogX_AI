# -*- coding: utf-8 -*-
"""Page d'accueil (logx_accueil.js) — robustesse au localStorage (audit 26/08).
init() lisait localStorage.getItem('logx_activity') HORS try/catch : si l'accès
jette (navigation privée, stockage désactivé, quota), toute l'init plantait et
la page restait bloquée sur « Chargement… ». Les autres accès (l.41/46) sont
déjà protégés. Test : avec un localStorage qui JETTE, évaluer le fichier ne
doit PAS lever (init doit dégrader et rendre la grille)."""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_accueil.js')
py_mini_racer = pytest.importorskip('py_mini_racer')

_STUBS = """
  var __el = function(){ return {innerHTML:'', appendChild:function(){}, style:{}, classList:{add:function(){},remove:function(){}}}; };
  var document = { getElementById:__el, querySelector:__el, querySelectorAll:function(){return [];}, createElement:__el };
  var window = { location:{search:'', href:''} };
  function URLSearchParams(s){ return { get:function(){ return null; } }; }
  var localStorage = { getItem:function(){ throw new Error('storage disabled'); },
                       setItem:function(){ throw new Error('storage disabled'); } };
"""


def test_init_survit_a_un_localStorage_qui_jette():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_STUBS)
    with open(JS, encoding='utf-8') as f:
        src = f.read()
    # L'IIFE init() s'exécute à l'évaluation. Sans le try/catch, getItem jette
    # et l'évaluation LÈVE (JSEvalException) -> le test échoue. Avec le fix,
    # init attrape l'erreur, retombe sur la grille, et l'évaluation aboutit.
    ctx.eval(src)   # ne doit pas lever
    # Preuve que l'init est allée au bout (a rendu la grille, pas juste avorté) :
    # après eval, un appel témoin ne doit pas planter non plus.
    assert ctx.eval("typeof ACTIVITIES") == 'object'
