# -*- coding: utf-8 -*-
"""Audit BASSE 644 : ajouter un groupe (vide) au filtre avancé faisait matcher
TOUS les QSO, annulant en silence les autres groupes.

matchesAdvancedFilter : `groups.some(g => !g.length || g.every(...))`. Un groupe
VIDE (`!g.length`) vaut TRUE, et comme les groupes sont en OU (`some`), un seul
groupe vide force le match de tout le log — les conditions des autres groupes
sont ignorées. fltAddGroup() pousse justement `[]`. Correctif : un groupe vide
est IGNORÉ (pas match-tout) ; si plus aucun groupe peuplé ne reste, pas de
filtre (match tout, état par défaut {groups:[[]]})."""
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(BASE, 'logx_logbook.js')


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
    src = open(JS, encoding='utf-8').read()
    c = py_mini_racer.MiniRacer()
    c.eval("function fltFieldDef(){ return {type:'text'}; }")   # tout champ = texte
    c.eval(_extract(src, 'matchesFilterCondition'))
    c.eval(_extract(src, 'matchesAdvancedFilter'))
    return c


def test_groupe_vide_n_annule_pas_un_groupe_peuple():
    c = _ctx()
    # q échoue à la condition du groupe peuplé ; un groupe vide est aussi présent.
    r = c.eval("matchesAdvancedFilter({call:'F4ABC'}, "
               "{groups:[[{field:'call',op:'eq',value:'ZZZZ'}], []]})")
    assert r is False, "un groupe vide a annulé le filtre (tout matché à tort)"


def test_filtre_par_defaut_un_seul_groupe_vide_matche_tout():
    c = _ctx()
    # État par défaut {groups:[[]]} = aucun critère = pas de filtre = tout matche.
    assert c.eval("matchesAdvancedFilter({call:'F4ABC'}, {groups:[[]]})") is True


def test_groupe_peuple_reussi_matche():
    c = _ctx()
    assert c.eval("matchesAdvancedFilter({call:'F4ABC'}, "
                  "{groups:[[{field:'call',op:'eq',value:'F4ABC'}]]})") is True
