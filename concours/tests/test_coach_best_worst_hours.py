# -*- coding: utf-8 -*-
"""build_debrief : best_hours (hours_sorted[:3]) et worst_hours
(hours_sorted[-3:]) se CHEVAUCHAIENT quand le log couvre exactement 4 ou 5
heures distinctes — une même heure listée à la fois 'meilleure' et 'creuse'
dans le prompt de débrief. La logique est extraite dans _best_worst_hours()
pour être testable et garantir des tranches TOUJOURS disjointes.
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_coach as coach  # noqa: E402


def _fake_hours(n):
    # (heure, count) triés par -count comme dans build_debrief
    return [(f"01/01 {h:02d}h", n - h) for h in range(n)]


def test_best_worst_disjoints_pour_4_et_5_heures():
    for n in (4, 5):
        best, worst = coach._best_worst_hours(_fake_hours(n))
        inter = set(best) & set(worst)
        assert not inter, f"chevauchement à {n} heures : {inter}"


def test_best_worst_valeurs_attendues():
    # 6 heures : best = 3 premières, worst = 3 dernières, disjoints
    hs = _fake_hours(6)
    best, worst = coach._best_worst_hours(hs)
    assert best == hs[:3]
    assert worst == hs[3:]
    assert not (set(best) & set(worst))


def test_moins_de_4_heures_worst_vide_ou_disjoint():
    best, worst = coach._best_worst_hours(_fake_hours(3))
    assert best == _fake_hours(3)
    assert worst == []          # rien après les 3 premières
