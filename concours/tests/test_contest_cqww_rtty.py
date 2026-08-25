# -*- coding: utf-8 -*-
"""CQ WW RTTY DX ajouté aux définitions de concours (audit couverture : grand
vide RTTY). Valeurs SOURCÉES sur cqwwrtty.com : 5 bandes HF (pas 160m), mode
RTTY, échange RST + zone CQ (+ état/province W/VE), barème 1/2/3 (§IV.B).
Multiplicateur états/provinces W/VE (§IV.C.3) : refinement noté, pas encore
compté (multiplicateur combiné à ajouter)."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

from logx_definitions import CONTEST_DEFINITIONS   # noqa: E402
import logx_scoring as scoring                       # noqa: E402
import logx_validate as validate                     # noqa: E402


def test_cqww_rtty_present_et_conforme():
    assert 'CQ_WW_RTTY' in CONTEST_DEFINITIONS
    d = CONTEST_DEFINITIONS['CQ_WW_RTTY']
    assert d['bands'] == ['3.5', '7', '14', '21', '28']   # 5 bandes HF, PAS 160m
    assert d['modes'] == ['RTTY']
    assert d['cabrillo_name'] == 'CQ-WW-RTTY'


def test_cqww_rtty_definition_valide():
    erreurs = validate.validate_definition(CONTEST_DEFINITIONS['CQ_WW_RTTY'],
                                           'CQ_WW_RTTY')
    assert erreurs == [], erreurs                         # liste vide = conforme


def test_bareme_rtty_1_2_3_sans_regle_wve():
    # barème RTTY : 1 (même pays) / 2 (même continent) / 3 (DX), PAS la règle
    # na_w_ve du CQ WW SSB/CW.
    preset = scoring.LEGACY_SCORING_PRESETS['zone_country_per_band_rtty']
    pts = {r['when']: r['points'] for r in preset['points']}
    assert pts.get('same_country') == 1
    assert pts.get('same_continent') == 2
    assert pts.get('always') == 3
    assert 'na_w_ve' not in pts                            # pas de bonus W/VE


# ─── ARRL RTTY Roundup ───────────────────────────────────────────────────────

def test_rtty_roundup_present_et_valide():
    assert 'ARRL_RTTY_ROUNDUP' in CONTEST_DEFINITIONS
    d = CONTEST_DEFINITIONS['ARRL_RTTY_ROUNDUP']
    assert d['bands'] == ['3.5', '7', '14', '21', '28'] and d['modes'] == ['RTTY']
    assert d['cabrillo_name'] == 'ARRL-RTTY'
    erreurs = validate.validate_definition(d, 'ARRL_RTTY_ROUNDUP')
    assert erreurs == [], erreurs


def test_rtty_roundup_bareme_1_point():
    preset = scoring.LEGACY_SCORING_PRESETS['rtty_roundup']
    assert preset['points'] == [{'when': 'always', 'points': 1}]
    assert preset['multiplier'] is None                   # mult all-band non auto
