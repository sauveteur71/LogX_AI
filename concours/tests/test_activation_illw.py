# -*- coding: utf-8 -*-
"""ILLW (International Lighthouse & Lightship Weekend) ajouté aux programmes
d'activation. Événement week-end PUR : pas de seuil d'activation (min_qso=1).
Référence « XX-nnnn » (code pays 2 lettres + 4 chiffres, ex. IT-0005) —
numérotation officielle illw.net. Pas de tag ADIF dédié -> générique SIG."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_activation as act   # noqa: E402


def test_illw_present_dans_program_specs():
    assert 'ILLW' in act.PROGRAM_SPECS
    spec = act.PROGRAM_SPECS['ILLW']
    assert spec['min_qso'] == 1             # événement sans seuil d'activation
    assert 'adif_tag' not in spec           # pas de tag ADIF dédié -> SIG


def test_illw_reference_valide():
    assert act.validate_ref('ILLW', 'IT-0005')
    assert act.validate_ref('ILLW', 'FR-0001')
    assert act.validate_ref('ILLW', 'AU-0123')


def test_illw_reference_invalide():
    assert not act.validate_ref('ILLW', 'F-0005')       # code pays 1 lettre
    assert not act.validate_ref('ILLW', 'IT-05')        # numéro trop court
    assert not act.validate_ref('ILLW', 'ITALY-0005')   # code trop long
