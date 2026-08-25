# -*- coding: utf-8 -*-
"""Câblage du tri du panneau « départements À FAIRE » : bouton bascule fréq/rareté,
tri appliqué au rendu, mode persisté. La logique pure est couverte par
test_dept_todo ; ici, assertions structurelles.
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(nom):
    with open(os.path.join(BASE, nom), encoding='utf-8') as f:
        return f.read()


def test_bouton_bascule_present():
    html = _lire('logx_logbook.html')
    assert 'logx_dept_todo.js' in html                        # module inclus
    assert 'id="deptTodoTri"' in html and 'toggleDeptTodoTri()' in html


def test_tri_applique_au_rendu():
    js = _lire('logx_filtre_spots.js')
    m = re.search(r'function _rendreDeptTodo\(.*?\n\}', js, re.S)
    assert m, '_rendreDeptTodo introuvable'
    corps = m.group(0)
    assert 'LogxDeptTodo.trier(avecSpot, mode, freqMhz)' in corps
    # fréquence courante du poste pour la proximité (kHz -> MHz)
    assert 'rig.freq_khz / 1000' in corps


def test_toggle_persiste_et_re_rend():
    js = _lire('logx_filtre_spots.js')
    m = re.search(r'function toggleDeptTodoTri\(.*?\n\}', js, re.S)
    assert m, 'toggleDeptTodoTri introuvable'
    corps = m.group(0)
    assert "setItem('rc_dept_todo_tri', m)" in corps          # mode persisté
    assert '_rendreDeptTodo(_deptTodoDerniers)' in corps       # re-rend sans refetch
