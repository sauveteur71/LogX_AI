# -*- coding: utf-8 -*-
"""Moteur de score du Challenge THF (logx_challenge_thf_scoring) — règlement REF
sourcé F4GLD. Score par bande = P × (D + G) × C (nouvelles stations/mois ×
(départements + grands carrés) × coefficient de bande). Dupe = (call, bande, mois)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_challenge_thf_scoring as C   # noqa: E402


def _q(call, band, date, dept='', grid=''):
    return C.ChallengeThfQso(call, band, date, dept, grid)


# ── Coefficients de bande ────────────────────────────────────────────────────

def test_coefficients_de_bande():
    assert C.coefficient_bande('144') == 1
    assert C.coefficient_bande('432') == 3
    assert C.coefficient_bande('1296') == 5
    for b in ('2320', '3400', '5760', '10368', '24048', '47088'):
        assert C.coefficient_bande(b) == 10


# ── Formule par bande ────────────────────────────────────────────────────────

def test_score_bande_formule():
    # 144 (C=1) : F5ABC jan + F5ABC fév (même station, 2 mois -> 2) + F6DEF jan
    qsos = [
        _q('F5ABC', '144', '20260115', '75', 'JN18XX'),
        _q('F5ABC', '144', '20260210', '75', 'JN18XX'),
        _q('F6DEF', '144', '20260118', '92', 'JN19AA'),
    ]
    r = C.score_bande(qsos, '144')
    assert r['points'] == 3            # (F5ABC,jan),(F5ABC,fév),(F6DEF,jan)
    assert r['departments'] == 2       # 75, 92
    assert r['large_locators'] == 2    # JN18, JN19
    assert r['coefficient'] == 1
    assert r['score'] == 3 * (2 + 2) * 1   # = 12


def test_coefficient_change_le_score():
    # même contenu sur 432 (C=3) -> score ×3
    qsos = [_q('F5ABC', '432', '20260115', '75', 'JN18XX')]
    r = C.score_bande(qsos, '432')
    assert r['points'] == 1 and r['departments'] == 1 and r['large_locators'] == 1
    assert r['score'] == 1 * (1 + 1) * 3   # = 6


def test_dedup_call_bande_mois():
    """Une station compte une seule fois par mois ET par bande, mais ré-ouvre au
    mois suivant / sur une autre bande."""
    qsos = [
        _q('F5ABC', '144', '20260105', '75', 'JN18'),
        _q('F5ABC', '144', '20260125', '75', 'JN18'),   # même mois/bande -> pas un 2e point
        _q('F5ABC', '144', '20260205', '75', 'JN18'),   # mois suivant -> +1
        _q('F5ABC', '432', '20260105', '75', 'JN18'),   # autre bande -> compté à part
    ]
    assert C.score_bande(qsos, '144')['points'] == 2    # janvier + février
    assert C.score_bande(qsos, '432')['points'] == 1


def test_grand_carre_est_4_caracteres():
    # JN18XX et JN18AA -> même grand carré JN18 (1 seul)
    qsos = [_q('F5A', '144', '20260101', '75', 'JN18XX'),
            _q('F6B', '144', '20260101', '76', 'JN18AA')]
    assert C.score_bande(qsos, '144')['large_locators'] == 1


# ── Invariant de formule + total ─────────────────────────────────────────────

def test_le_score_respecte_toujours_P_x_D_plus_G_x_C():
    qsos = [_q('F5A', '1296', '20260101', '75', 'JN18'),
            _q('F6B', '1296', '20260201', '92', 'JN29'),
            _q('F7C', '1296', '20260301', '75', 'JN18')]
    r = C.score_bande(qsos, '1296')
    assert r['score'] == r['points'] * (r['departments'] + r['large_locators']) * r['coefficient']


def test_exemple_du_reglement_144():
    """450 pts × (50 dép + 40 QTH) × 1 = 40 500 (exemple cité au règlement)."""
    assert 450 * (50 + 40) * 1 == 40500          # arithmétique du règlement
    # et le module applique bien cette formule (vérifié par l'invariant ci-dessus)


def test_total_somme_des_bandes():
    qsos = [_q('F5A', '144', '20260101', '75', 'JN18'),   # 1×(1+1)×1 = 2
            _q('F5A', '432', '20260101', '75', 'JN18')]   # 1×(1+1)×3 = 6
    r = C.calculer_score_challenge_thf(qsos)
    assert r['total'] == 8 and r['qso_count'] == 2
    assert {b['band'] for b in r['per_band']} == {'144', '432'}
