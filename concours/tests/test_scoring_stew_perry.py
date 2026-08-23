# -*- coding: utf-8 -*-
"""Barème Stew Perry TBDC faux d'un facteur ~500 (logx_definitions/scoring) — Strate 2, haute.

La brique de points de STEW_PERRY était {'points':'per_km'}, qui rend la distance
BRUTE en km : calc_total_score sommait donc les km comme des points et exposait
un score claimed ~500× trop grand. Le barème réel (source
https://www.kkn.net/stew/stew_rules.html) est : « minimum one point per QSO and
an additional point for every 500 kilometers distance » — soit 1 + km//500
(ex. 1750 km -> 4 pts), sans multiplicateur de grille.

per_km reste CORRECT pour les concours VHF/THF (km = points) : on ajoute un type
dédié per_km_stew et on ne change que STEW_PERRY.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_scoring as sc        # noqa: E402
import logx_definitions as d     # noqa: E402


def test_points_stew_1pt_plus_1_par_500km():
    f = sc._points_value
    assert f({'points': 'per_km_stew'}, {'dist_km': 1750}, {}) == 4   # 1 + 3
    assert f({'points': 'per_km_stew'}, {'dist_km': 499}, {}) == 1    # 1 + 0
    assert f({'points': 'per_km_stew'}, {'dist_km': 1000}, {}) == 3   # 1 + 2
    assert f({'points': 'per_km_stew'}, {'dist_km': 3000}, {}) == 7   # 1 + 6


def test_per_km_inchange_pour_vhf_thf():
    # per_km (REF RPH/THF, IARU VHF) doit toujours rendre les km bruts.
    assert sc._points_value({'points': 'per_km'}, {'dist_km': 1750}, {}) == 1750


def test_definition_stew_perry_utilise_le_bon_type():
    bricks = d.CONTEST_DEFINITIONS['STEW_PERRY']['scoring']['bricks']
    assert bricks['points'][0]['points'] == 'per_km_stew', (
        "STEW_PERRY doit utiliser per_km_stew (1 + km//500), pas per_km (km bruts)"
    )
