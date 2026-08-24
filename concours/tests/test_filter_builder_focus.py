# -*- coding: utf-8 -*-
"""Perte de focus dans le constructeur de filtres (logx_filter_builder.js).

Le champ « valeur » d'une condition déclenche
`oninput="fltUpdateCond(gi,ci,'value',this.value)"`. fltUpdateCond se terminait
INCONDITIONNELLEMENT par fltRenderGroups(), qui fait `wrap.innerHTML = h` :
tout l'arbre DOM (donc l'<input> en cours de saisie) est détruit et recréé à
CHAQUE caractère → le focus est perdu, la frappe s'interrompt.

Correctif : sur key==='value', ne PAS reconstruire le DOM (la valeur est déjà
dans le modèle) — seul le compteur #fltCount doit se rafraîchir. field/op
gardent le re-rendu (changement de type/opérateur, événement unique de select).

Test comportemental sur la VRAIE fonction extraite : value -> pas de re-rendu +
compteur mis à jour ; field -> re-rendu.
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(BASE, 'logx_filter_builder.js'), encoding='utf-8').read()


def _extraire_fn(src, nom):
    i = src.find('async function ' + nom)
    if i == -1:
        i = src.index('function ' + nom)
    j = src.index('{', i)
    prof, k = 0, j
    while k < len(src):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return src[i:k + 1]
        k += 1
    raise AssertionError('fonction %s introuvable' % nom)


def _ctx():
    from py_mini_racer import py_mini_racer as m
    c = m.MiniRacer()
    c.eval('var fltBuilder = {groups: [[{field:"call", op:"eq", value:""}]]};')
    c.eval('var _renderCalls = 0; function fltRenderGroups(){ _renderCalls++; }')
    c.eval('var _countCalls = 0; function fltUpdateCount(){ _countCalls++; }')
    c.eval('var FILTER_OPS = {text:[["eq","="]], number:[["eq","="]], bool:[["t","vrai"]]};')
    c.eval('function fltFieldDef(f){ return {type:"text"}; }')
    c.eval(_extraire_fn(JS, 'fltUpdateCond'))
    return c


def test_saisie_valeur_ne_reconstruit_pas_le_dom():
    c = _ctx()
    c.eval('fltUpdateCond(0,0,"value","F4GLD")')
    assert c.eval('_renderCalls') == 0, "la saisie d'une valeur ne doit PAS reconstruire le DOM (perte de focus)"
    assert c.eval('_countCalls') == 1, "le compteur doit être rafraîchi sur saisie de valeur"
    # le modèle est bien mis à jour
    assert c.eval('fltBuilder.groups[0][0].value') == 'F4GLD'


def test_changement_de_champ_reconstruit_le_dom():
    c = _ctx()
    c.eval('fltUpdateCond(0,0,"field","rst")')
    assert c.eval('_renderCalls') == 1, "changer de champ doit re-rendre (type/opérateur peut changer)"
