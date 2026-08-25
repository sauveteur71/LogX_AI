# -*- coding: utf-8 -*-
"""WWBOTA (World Wide Bunkers on the Air) ajouté aux programmes d'activation.
Format de référence et seuil d'activation SOURCÉS sur wwbota.net :
réf « B/<code pays>-nnnn » (ex. B/G-0001, B/US-0001), activation HF valide à
25 QSO. Pas de tag ADIF dédié (comme ARLHS/WCA) -> générique SIG."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_activation as act   # noqa: E402


def test_wwbota_present_dans_program_specs():
    assert 'WWBOTA' in act.PROGRAM_SPECS
    spec = act.PROGRAM_SPECS['WWBOTA']
    assert spec['min_qso'] == 25            # activation HF valide (wwbota.net)
    assert 'adif_tag' not in spec           # pas de tag ADIF dédié -> SIG générique


def test_wwbota_reference_valide():
    assert act.validate_ref('WWBOTA', 'B/G-0001')
    assert act.validate_ref('WWBOTA', 'B/US-0001')
    assert act.validate_ref('WWBOTA', 'B/E7-0123')


def test_wwbota_reference_invalide():
    assert not act.validate_ref('WWBOTA', 'FR-0123')    # sans préfixe B/
    assert not act.validate_ref('WWBOTA', 'B/G-01')     # numéro trop court
    assert not act.validate_ref('WWBOTA', 'G-0001')     # B/ manquant
