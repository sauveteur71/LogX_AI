# -*- coding: utf-8 -*-
"""GMA (Global Mountain Activity) ajouté aux programmes d'activation.
Seuil et format SOURCÉS sur cqgma.org / gma.rocks : activation de sommet valide
à 4 QSO avec des stations DIFFÉRENTES ; « SOTA references are generally also
valid for GMA » -> même schéma de référence association/région-numéro que SOTA
(ex. DL/BE-055). Pas de tag ADIF dédié -> mécanisme générique SIG (comme
WWBOTA/ILLW). Programme hiérarchique (association > région > sommet)."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_activation as act   # noqa: E402


def test_gma_present_dans_program_specs():
    assert 'GMA' in act.PROGRAM_SPECS
    spec = act.PROGRAM_SPECS['GMA']
    assert spec['name'] == 'Global Mountain Activity'
    assert spec['min_qso'] == 4              # 4 QSO distincts (cqgma.org/gma.rocks)
    assert 'adif_tag' not in spec            # pas de tag ADIF dédié -> SIG générique


def test_gma_reference_valide():
    # SOTA refs valides pour GMA -> même format association/région-numéro
    assert act.validate_ref('GMA', 'DL/BE-055')
    assert act.validate_ref('GMA', 'F/AB-001')
    assert act.validate_ref('GMA', 'W4G/CE-001')      # association avec chiffre


def test_gma_reference_invalide():
    assert not act.validate_ref('GMA', 'DL-055')      # région /XX manquante
    assert not act.validate_ref('GMA', 'FR-0123')     # format POTA
    assert not act.validate_ref('GMA', 'DL/BE-01')    # numéro trop court
