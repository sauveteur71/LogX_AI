# -*- coding: utf-8 -*-
"""validate_definition ne doit pas PLANTER sur un 'when' malformé.

Un 'when' non-chaîne (dict, liste imbriquée…) — typique d'une définition de
concours extraite par l'IA ou importée avec une faute — faisait exécuter
`w not in PREDICATES` avec w=dict, où PREDICATES est un dict : TypeError
« unhashable type: 'dict' » NON rattrapée, faisant planter la validation au
lieu de refuser la définition proprement. Correctif : tout prédicat non-str
est « inconnu » (erreur propre), jamais une exception.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_validate as v


def test_when_malforme_refuse_proprement_sans_planter():
    cdef = {'scoring': {'bricks': {'points': [{'when': {'bad': 1}, 'points': 1}]}}}
    errs = v.validate_definition(cdef, 'TEST')   # ne doit PAS lever
    assert isinstance(errs, list) and errs, "un when malformé doit produire une erreur"
    assert any('when' in e for e in errs), errs


def test_when_liste_de_dict_ne_plante_pas():
    cdef = {'scoring': {'bricks': {'points': [{'when': [{'x': 1}], 'points': 1}]}}}
    errs = v.validate_definition(cdef, 'TEST')
    assert isinstance(errs, list) and any('when' in e for e in errs)


def test_when_valide_pas_derreur_when():
    cdef = {'scoring': {'bricks': {'points': [{'when': 'always', 'points': 1}]}}}
    errs = v.validate_definition(cdef, 'TEST')
    assert not any('when' in e for e in errs), errs
