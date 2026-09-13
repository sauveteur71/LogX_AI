# -*- coding: utf-8 -*-
"""Rencontres UFT (Union Française des Télégraphistes, CW, permanent) --
moteur de scoring dédié.

SOURCE : page HTML officielle lue intégralement le 13/09/2026
(https://www.uft.net/activites-et-concours/rencontres-uft/) :
  - Bandes : 3.520-3.560 / 7.013-7.035 / 14.030-14.060 / 21.030-21.060 /
    28.030-28.060 MHz, CW uniquement.
  - Échange : RST + numéro de membre UFT (ou 'NM' pour un non-membre).
  - Barème : F8UFT (station officielle) = 20 pts ; membre UFT même
    continent = 5, DX = 10 ; non-membre même continent = 1, DX = 2.
  - Multiplicateur : chaque membre UFT distinct compte 1 multi PAR BANDE,
    ainsi que les QSO avec F8UFT.

DÉCOUVERTE qui motive ce fichier : l'ancienne CONTEST_SCORING affichait
'type':'dept', 'mult':'depts' -- AUCUNE notion de département dans le vrai
barème. Et surtout : la note antérieure ("barème dépend du statut de
membre UFT, donnée d'adhésion absente, pas modélisable") était INCOMPLÈTE
-- le statut est auto-déclaré DANS L'ÉCHANGE reçu (comme un numéro de
série REF classique), donc calculable à 100% sans aucune base externe.

Moteur délibérément SÉPARÉ du moteur générique bricks (comme Challenge
THF) : les points dépendent de l'échange REÇU (num_rcvd), une donnée hors
du contexte pré-QSO de calc_qso_value/score_new_qso.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

from logx_definitions import CONTEST_DEFINITIONS   # noqa: E402
import logx_scoring as scoring                       # noqa: E402
import logx_validate as validate                     # noqa: E402

MY_CALL = 'F4GLD'   # France -> continent EU


def _qso(call, band='14', num_rcvd=''):
    return {'call': call, 'band': band, 'num_rcvd': num_rcvd}


def test_la_definition_est_presente_et_valide():
    assert 'UFT_RENCONTRES' in CONTEST_DEFINITIONS
    erreurs = validate.validate_definition(
        CONTEST_DEFINITIONS['UFT_RENCONTRES'], 'UFT_RENCONTRES')
    assert erreurs == []


def test_bandes_cw_du_reglement():
    assert CONTEST_DEFINITIONS['UFT_RENCONTRES']['bands'] == ['3.5', '7', '14', '21', '28']
    assert CONTEST_DEFINITIONS['UFT_RENCONTRES']['modes'] == ['CW']


# ─── Barème points (art. sourcé uft.net) ────────────────────────────────────

def test_f8uft_vaut_20_points_quel_que_soit_le_continent():
    pts, statut = scoring.calc_uft_points(_qso('F8UFT', num_rcvd='NM'), MY_CALL)
    assert (pts, statut) == (20, 'ok')
    # Même un DX qui contacterait F8UFT (peu probable mais le règlement ne
    # distingue pas de continent pour la station officielle) :
    pts_dx, _ = scoring.calc_uft_points(_qso('F8UFT', num_rcvd='123'), 'W1AW')
    assert pts_dx == 20


def test_membre_meme_continent_vaut_5():
    pts, statut = scoring.calc_uft_points(_qso('F1ABC', num_rcvd='042'), MY_CALL)
    assert (pts, statut) == (5, 'ok')


def test_membre_dx_vaut_10():
    pts, statut = scoring.calc_uft_points(_qso('W1AW', num_rcvd='042'), MY_CALL)
    assert (pts, statut) == (10, 'ok')


def test_non_membre_meme_continent_vaut_1():
    pts, statut = scoring.calc_uft_points(_qso('F1ABC', num_rcvd='NM'), MY_CALL)
    assert (pts, statut) == (1, 'ok')


def test_non_membre_dx_vaut_2():
    pts, statut = scoring.calc_uft_points(_qso('W1AW', num_rcvd='NM'), MY_CALL)
    assert (pts, statut) == (2, 'ok')


def test_nm_insensible_a_la_casse_et_aux_espaces():
    pts, statut = scoring.calc_uft_points(_qso('F1ABC', num_rcvd=' nm '), MY_CALL)
    assert (pts, statut) == (1, 'ok')


def test_echange_manquant_est_incomplete_jamais_un_point_invente():
    pts, statut = scoring.calc_uft_points(_qso('F1ABC', num_rcvd=''), MY_CALL)
    assert (pts, statut) == (0, 'incomplete')


# ─── Multiplicateur (membres distincts + F8UFT, par bande) ──────────────────

def test_bilan_multiplicateur_compte_membres_distincts_et_f8uft():
    qsos = [
        _qso('F1ABC', '14', '042'),    # membre 042
        _qso('F2DEF', '14', '042'),    # même membre, même bande -- pas de nouveau multi
        _qso('F3GHI', '14', '099'),    # membre 099 -- nouveau multi
        _qso('F8UFT', '14', 'NM'),     # F8UFT -- multi distinct, quel que soit l'échange
        _qso('W1XYZ', '14', 'NM'),     # non-membre -- ne compte jamais comme multi
    ]
    r = scoring.calc_uft_rencontres_score(qsos, MY_CALL)
    assert r['multiplier'] == 3    # membre 042 + membre 099 + F8UFT
    assert r['status'] == 'official_candidate'


def test_meme_membre_deux_bandes_compte_deux_multiplicateurs():
    qsos = [_qso('F1ABC', '14', '042'), _qso('F1ABC', '21', '042')]
    r = scoring.calc_uft_rencontres_score(qsos, MY_CALL)
    assert r['multiplier'] == 2


def test_score_est_points_fois_multiplicateur():
    qsos = [
        _qso('F1ABC', '14', '042'),   # membre même continent : 5 pts
        _qso('W1AW', '14', '099'),    # membre DX : 10 pts
    ]
    r = scoring.calc_uft_rencontres_score(qsos, MY_CALL)
    assert r['raw_points'] == 15
    assert r['multiplier'] == 2
    assert r['score'] == 30


def test_qso_incomplet_marque_le_bilan_non_officiel():
    qsos = [_qso('F1ABC', '14', '042'), _qso('F2DEF', '14', '')]
    r = scoring.calc_uft_rencontres_score(qsos, MY_CALL)
    assert r['status'] == 'incomplete'
    assert r['qsos_incomplets'] == 1
    # Le QSO classable est quand même compté (jamais tout ou rien) :
    assert r['raw_points'] == 5


def test_journal_vide_est_officiel_zero():
    r = scoring.calc_uft_rencontres_score([], MY_CALL)
    assert r == {'status': 'official_candidate', 'raw_points': 0,
                 'multiplier': 0, 'score': 0, 'qsos_incomplets': 0}


# ─── Preset de coaching (LEGACY_SCORING_PRESETS) ────────────────────────────

def test_preset_coaching_est_une_estimation_plancher():
    """Le vrai barème (jusqu'à 20 pts) dépend de l'échange, inconnu avant le
    QSO -- le preset de coaching donne la valeur PLANCHER (non-membre DX),
    jamais une estimation optimiste non garantie."""
    bricks = scoring.LEGACY_SCORING_PRESETS['uft_rencontres']
    assert bricks['multiplier'] is None
    assert bricks['points'][0]['points'] == 2
