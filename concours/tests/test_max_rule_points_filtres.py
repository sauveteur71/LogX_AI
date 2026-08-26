# -*- coding: utf-8 -*-
"""Scoring — _max_rule_points doit appliquer les MÊMES filtres (bands/prefix_in/
modes/when) que _eval_points (audit STRATE-3 logx_scoring.py:194). Avant :
_max_rule_points prenait les points de TOUTES les règles sans filtrer -> pour un
barème à paliers de bande (ex. WPX : points doublés en bandes basses), il rendait
le palier haut même sur une bande basse, faussant les seuils de priorité qui s'en
servent."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_scoring as sc

# 6 pts UNIQUEMENT en 80 m (3.5), 1 pt partout ailleurs.
_RULES = [{'bands': ['3.5'], 'points': 6}, {'points': 1}]
_SCORING = {}


def _ctx(band):
    return {'band_norm': band, 'dx_base': 'K1ABC', 'mode': 'CW', 'dist_km': 0}


def test_max_ne_compte_pas_une_regle_hors_bande():
    # Sur 20 m, la règle « 6 pts en 80 m » ne s'applique pas : max = 1, PAS 6.
    assert sc._max_rule_points(_RULES, _ctx('14'), _SCORING) == 1


def test_max_compte_la_regle_quand_la_bande_correspond():
    assert sc._max_rule_points(_RULES, _ctx('3.5'), _SCORING) == 6


def test_max_coherent_avec_eval_points():
    # _max_rule_points et _eval_points doivent voir les MÊMES règles applicables.
    for band in ('14', '3.5', '7'):
        ctx = _ctx(band)
        assert sc._max_rule_points(_RULES, ctx, _SCORING) == sc._eval_points(_RULES, ctx, _SCORING)


def test_filtre_mode_aussi_respecte():
    rules = [{'modes': ['SSB'], 'points': 4}, {'points': 1}]
    # QSO en CW : la règle SSB ne s'applique pas -> max = 1.
    assert sc._max_rule_points(rules, _ctx('14'), _SCORING) == 1
    # QSO en SSB -> 4.
    ctx_ssb = _ctx('14'); ctx_ssb['mode'] = 'SSB'
    assert sc._max_rule_points(rules, ctx_ssb, _SCORING) == 4
