# -*- coding: utf-8 -*-
"""DFCF (Forts et Châteaux de France) et DMF (Moulins de France) ajoutés aux
programmes d'activation (patrimoine FR, hébergés REF).

DFCF SOURCÉ sur dfcf.fr/reglement.html (31/08/2026) : réf. « DFCF-<dept 2 ch>
<n° 3 ch> » (ex. DFCF-01001), 100 liaisons HF pour une activation valide.
DMF : format « DMF<dept 2 ch>.<n° 3 ch> » (ex. DMF01.001), 100 QSO HF —
FORMAT À RECONFIRMER (dmf.r-e-f.org en 503 au moment du code). Aucun des deux
n'a de champ ADIF dédié -> mécanisme générique SIG/SIG_INFO (comme ARLHS/WCA)."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_activation as act   # noqa: E402


def test_dfcf_present_et_seuil():
    assert 'DFCF' in act.PROGRAM_SPECS
    spec = act.PROGRAM_SPECS['DFCF']
    assert spec['name'] == 'Diplôme des Forts et Châteaux de France'
    assert spec['min_qso'] == 100            # 100 liaisons HF (dfcf.fr)
    assert 'adif_tag' not in spec            # pas de tag ADIF dédié -> SIG


def test_dfcf_reference_valide():
    assert act.validate_ref('DFCF', 'DFCF-01001')     # dépt 01, n° 001
    assert act.validate_ref('DFCF', 'DFCF-75012')
    assert act.validate_ref('DFCF', 'DFCF-2A001')     # Corse 2A
    assert act.validate_ref('DFCF', 'dfcf-33005')     # normalisé en majuscules


def test_dfcf_reference_invalide():
    assert not act.validate_ref('DFCF', 'DFCF-1001')   # dépt sur 1 chiffre
    assert not act.validate_ref('DFCF', 'DFCF01001')   # tiret manquant
    assert not act.validate_ref('DFCF', 'F-0123')      # format POTA
    assert not act.validate_ref('DFCF', 'DFCF-01')     # n° manquant


def test_dmf_present_et_seuil():
    assert 'DMF' in act.PROGRAM_SPECS
    spec = act.PROGRAM_SPECS['DMF']
    assert spec['name'] == 'Diplôme des Moulins de France'
    assert spec['min_qso'] == 100
    assert 'adif_tag' not in spec


def test_dmf_reference_valide():
    assert act.validate_ref('DMF', 'DMF01.001')       # dépt 01, n° 001
    assert act.validate_ref('DMF', 'DMF89.060')
    assert act.validate_ref('DMF', 'dmf2b.012')       # Corse 2B, normalisé


def test_dmf_reference_invalide():
    assert not act.validate_ref('DMF', 'DMF01-001')   # tiret au lieu du point
    assert not act.validate_ref('DMF', 'DMF1.001')    # dépt sur 1 chiffre
    assert not act.validate_ref('DMF', 'DMF01.01')    # n° trop court
