# -*- coding: utf-8 -*-
"""FT Roundup ajouté aux définitions de concours (item « FT8 Roundup », F4GLD).
Valeurs SOURCÉES sur rttycontesting.com/ft-roundup/rules : 5 bandes HF, modes
FT4/FT8, échange RST + état/province (W/VE) ou RST + n° de série (DX), 1 pt/QSO,
multiplicateur = états + provinces + DXCC (hors US/Canada, KH6/KL7 en DXCC),
compté UNE FOIS toutes bandes. Barème IDENTIQUE à l'ARRL RTTY Roundup (kind
rtty_ru) — d'où la réutilisation du preset 'rtty_roundup'.

NB : concours DISCONTINUÉ (remplacé par le FT Challenge, barème différent) —
conservé pour les logs historiques.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

from logx_definitions import CONTEST_DEFINITIONS   # noqa: E402
import logx_scoring as scoring                       # noqa: E402
import logx_validate as validate                     # noqa: E402


def test_ft_roundup_present_et_conforme():
    assert 'FT_ROUNDUP' in CONTEST_DEFINITIONS
    d = CONTEST_DEFINITIONS['FT_ROUNDUP']
    assert d['bands'] == ['3.5', '7', '14', '21', '28']
    assert d['modes'] == ['FT4', 'FT8']            # numérique, PAS RTTY
    assert d['cabrillo_name'] == 'FT-ROUNDUP'
    assert d['date_rule'] == 'first_full_weekend_december'


def test_ft_roundup_definition_valide():
    erreurs = validate.validate_definition(CONTEST_DEFINITIONS['FT_ROUNDUP'], 'FT_ROUNDUP')
    assert erreurs == [], erreurs


def test_ft_roundup_reutilise_le_bareme_rtty_roundup():
    d = CONTEST_DEFINITIONS['FT_ROUNDUP']
    assert d['scoring']['type'] == 'rtty_roundup'   # 1 pt + mult all-band rtty_ru
    preset = scoring.LEGACY_SCORING_PRESETS['rtty_roundup']
    assert preset['points'] == [{'when': 'always', 'points': 1}]
    assert preset['multiplier'] == {'kind': 'rtty_ru'}


def test_ft_roundup_score_multiplicateur_all_band():
    """Preuve que le score autoritaire applique bien le mult all-band en FT4/FT8
    (états/provinces reçus dans l'échange, DXCC déduit de l'indicatif)."""
    cdef = CONTEST_DEFINITIONS['FT_ROUNDUP']
    qsos = [
        {'call': 'W1AW',  'band': '14', 'mode': 'FT8', 'num_rcvd': 'CT',  'points': 1},
        {'call': 'W1AW',  'band': '7',  'mode': 'FT4', 'num_rcvd': 'CT',  'points': 1},  # même état, autre bande
        {'call': 'VE3XX', 'band': '14', 'mode': 'FT8', 'num_rcvd': 'ON',  'points': 1},
        {'call': 'F6ABC', 'band': '14', 'mode': 'FT8', 'num_rcvd': '123', 'points': 1},  # DX -> DXCC F
    ]
    # mults all-band uniques : état CT, province ON, dxcc F = 3 ; points = 4 ;
    # score = 4 * 3 = 12 (CT compté une seule fois malgré 2 bandes)
    assert scoring.calc_total_score(qsos, cdef) == 12
