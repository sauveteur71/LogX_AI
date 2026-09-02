# -*- coding: utf-8 -*-
"""Moteur de score des Rencontres UFT (logx_uft_scoring) — barème officiel UFT
(sourcé F4GLD). Module pur : barème par QSO, dédoublonnage (indicatif, bande),
multiplicateur = membres UFT distincts PAR BANDE, score = points × multi."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_uft_scoring as U   # noqa: E402


def _q(call, band, dx, member, f8uft=False):
    return U.UftQso(call, band, dx, member, f8uft)


# ── Barème par QSO ───────────────────────────────────────────────────────────

def test_points_par_type_de_station():
    assert U.qso_points(_q('F8UFT', '7', False, True, f8uft=True)) == 20
    assert U.qso_points(_q('F5ABC', '7', False, True)) == 5     # membre même continent
    assert U.qso_points(_q('VK9XX', '7', True, True)) == 10     # membre DX
    assert U.qso_points(_q('F5NM', '7', False, False)) == 1     # non-membre même continent
    assert U.qso_points(_q('W1XX', '7', True, False)) == 2      # non-membre DX


# ── Statut depuis l'échange reçu ─────────────────────────────────────────────

def test_classifier_echange():
    assert U.classifier_echange('12') == 'membre'
    assert U.classifier_echange('300') == 'membre'
    assert U.classifier_echange('NM') == 'non_membre'
    assert U.classifier_echange('nm') == 'non_membre'
    assert U.classifier_echange('') == 'inconnu'
    assert U.classifier_echange('ABC') == 'inconnu'


# ── Multiplicateur par bande, dupe, score final ──────────────────────────────

def test_multiplicateur_compte_les_membres_par_bande():
    """Un même membre sur DEUX bandes = DEUX multis ; F8UFT compte aussi."""
    qsos = [
        _q('F5ABC', '3.5', False, True),   # 5 pts, multi (F5ABC,3.5)
        _q('F5ABC', '7',   False, True),   # 5 pts, multi (F5ABC,7)  -> autre bande
        _q('W1XYZ', '14',  True,  False),  # 2 pts, PAS multi (non-membre)
        _q('F8UFT', '3.5', False, True, f8uft=True),  # 20 pts, multi (F8UFT,3.5)
    ]
    r = U.calculer_score_uft(qsos)
    assert r['points_total'] == 32           # 5+5+2+20
    assert r['multiplier'] == 3              # (F5ABC,3.5),(F5ABC,7),(F8UFT,3.5)
    assert r['final_score'] == 96            # 32 × 3


def test_doublon_meme_indicatif_meme_bande_ignore():
    qsos = [
        _q('F5ABC', '3.5', False, True),   # compté
        _q('F5ABC', '3.5', False, True),   # DUPE -> ignoré
    ]
    r = U.calculer_score_uft(qsos)
    assert r['valid_qso_count'] == 1 and r['duplicate_count'] == 1
    assert r['points_total'] == 5 and r['multiplier'] == 1 and r['final_score'] == 5


def test_non_membres_ne_multiplient_pas():
    qsos = [_q('W1XYZ', '14', True, False), _q('K2ABC', '14', True, False)]
    r = U.calculer_score_uft(qsos)
    assert r['points_total'] == 4 and r['multiplier'] == 0
    assert r['final_score'] == 0             # aucun membre -> multi 0 -> score 0
