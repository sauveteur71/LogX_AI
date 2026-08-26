# -*- coding: utf-8 -*-
"""Activation POTA/WWFF — le seuil se juge sur les QSO UNIQUES (décision F4GLD
④). Clé d'éligibilité = (indicatif, bande, mode, jour UTC) : un même
correspondant recontacté même bande + même mode + même jour ne compte qu'une
fois. Les lignes brutes ne sont JAMAIS supprimées (qso_total conservé) ; seul le
compteur d'éligibilité exclut les doublons. Deux compteurs coexistent :
qso_total (brut) et qso_eligible (admissible)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_activation as act  # noqa: E402


def _q(call, band, mode, date, prog, ref):
    return {'call': call, 'band': band, 'mode': mode, 'date': date,
            'my_sig_info': ref, 'sig': prog}


# ── POTA (min 10, activation sur un seul jour UTC) ──────────────────────────
def test_pota_doublon_meme_bande_mode_jour_compte_une_fois():
    log = [_q('F4ABC', '20', 'FT8', '20260826', 'POTA', 'FR-0123'),
           _q('F4ABC', '20', 'FT8', '20260826', 'POTA', 'FR-0123')]
    st = act.activation_state(log, 'POTA', 'FR-0123')
    assert st['qso_total'] == 2
    assert st['qso_eligible'] == 1
    assert st['doublons'] == 1


def test_pota_bande_differente_compte_deux():
    log = [_q('F4ABC', '20', 'FT8', '20260826', 'POTA', 'FR-0123'),
           _q('F4ABC', '40', 'FT8', '20260826', 'POTA', 'FR-0123')]
    assert act.activation_state(log, 'POTA', 'FR-0123')['qso_eligible'] == 2


def test_pota_mode_different_compte_deux():
    log = [_q('F4ABC', '20', 'FT8', '20260826', 'POTA', 'FR-0123'),
           _q('F4ABC', '20', 'CW', '20260826', 'POTA', 'FR-0123')]
    assert act.activation_state(log, 'POTA', 'FR-0123')['qso_eligible'] == 2


def test_pota_seuil_juge_sur_eligible():
    base = [_q('F%dXY' % i, '20', 'FT8', '20260826', 'POTA', 'FR-0123')
            for i in range(10)]
    log = base + [dict(base[0])]   # un doublon exact du premier
    st = act.activation_state(log, 'POTA', 'FR-0123')
    assert st['qso_total'] == 11
    assert st['qso_eligible'] == 10
    assert st['doublons'] == 1
    assert st['valid'] is True     # 10 éligibles >= min 10
    assert st['needed'] == 0


# ── WWFF (min 44, cumul multi-dates) ────────────────────────────────────────
def test_wwff_date_differente_compte_deux():
    log = [_q('F4ABC', '20', 'FT8', '20260826', 'WWFF', 'FRFF-0001'),
           _q('F4ABC', '20', 'FT8', '20260827', 'WWFF', 'FRFF-0001')]
    assert act.activation_state(log, 'WWFF', 'FRFF-0001')['qso_eligible'] == 2


def test_wwff_meme_date_bande_mode_compte_une_fois():
    log = [_q('F4ABC', '20', 'FT8', '20260826', 'WWFF', 'FRFF-0001'),
           _q('F4ABC', '20', 'FT8', '20260826', 'WWFF', 'FRFF-0001')]
    st = act.activation_state(log, 'WWFF', 'FRFF-0001')
    assert st['qso_eligible'] == 1
    assert st['doublons'] == 1
