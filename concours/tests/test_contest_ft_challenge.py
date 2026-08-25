# -*- coding: utf-8 -*-
"""International FT Challenge (successeur du FT Roundup), SOURCE
rttycontesting.com/ft-challenge/rules : 5 bandes HF, modes FT4/FT8, échange =
locator 4 caractères + SNR. Barème DIFFÉRENT du FT Roundup :
  - points : 1 + 1 par tranche de 3000 km entre centres de locators (ZZ00 = 1) ;
  - multiplicateur : 1 par CHAMP de grille (2 caractères, ex. 'FN') PAR BANDE.
Deux briques neuves : points 'per_grid_3000' et kind de mult 'grid_field'.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

from logx_definitions import CONTEST_DEFINITIONS   # noqa: E402
import logx_scoring as scoring                       # noqa: E402
import logx_validate as validate                     # noqa: E402


def test_ft_challenge_present_et_conforme():
    assert 'FT_CHALLENGE' in CONTEST_DEFINITIONS
    d = CONTEST_DEFINITIONS['FT_CHALLENGE']
    assert d['bands'] == ['3.5', '7', '14', '21', '28']
    assert d['modes'] == ['FT4', 'FT8']
    assert d['scoring']['type'] == 'grid_field_distance'


def test_ft_challenge_definition_valide():
    erreurs = validate.validate_definition(CONTEST_DEFINITIONS['FT_CHALLENGE'], 'FT_CHALLENGE')
    assert erreurs == [], erreurs


def test_points_par_tranche_de_3000km():
    # 1 pt + 1 pt / 3000 km (SOURCE ft-challenge §points)
    assert scoring._points_value({'points': 'per_grid_3000'}, {'dist_km': 6000}, {}) == 3
    assert scoring._points_value({'points': 'per_grid_3000'}, {'dist_km': 2999}, {}) == 1
    # locator manquant (ZZ00) -> distance nulle -> 1 pt seulement
    assert scoring._points_value({'points': 'per_grid_3000'}, {'dist_km': 0}, {}) == 1


def test_multiplicateur_champ_de_grille_par_bande():
    cdef = CONTEST_DEFINITIONS['FT_CHALLENGE']
    qsos = [
        {'call': 'W1AW',  'band': '14', 'locator': 'FN31', 'points': 2},
        {'call': 'K9CT',  'band': '14', 'locator': 'EN52', 'points': 1},
        {'call': 'W1XX',  'band': '14', 'locator': 'FN44', 'points': 1},  # champ FN déjà vu (même bande)
        {'call': 'DL1XX', 'band': '7',  'locator': 'JO31', 'points': 1},  # champ JO, autre bande
    ]
    # bande 14 : champs {FN, EN} = 2 ; bande 7 : {JO} = 1 -> 3 mults
    # points = 2+1+1+1 = 5 ; score = 5 * 3 = 15
    assert scoring.calc_total_score(qsos, cdef) == 15


def test_champ_zz_ne_compte_pas():
    cdef = CONTEST_DEFINITIONS['FT_CHALLENGE']
    qsos = [
        {'call': 'W1AW', 'band': '14', 'locator': 'FN31', 'points': 1},
        {'call': 'DX0X', 'band': '14', 'locator': 'ZZ00', 'points': 1},   # grille manquante -> pas de mult
    ]
    # mults : {FN} = 1 (ZZ ignoré) ; points = 2 ; score = 2 * 1 = 2
    assert scoring.calc_total_score(qsos, cdef) == 2
