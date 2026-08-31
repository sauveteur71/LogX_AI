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
    # Forme COURTE officielle (dfcf.fr/valide.html) : DD-NNN.
    assert act.validate_ref('DFCF', '11-104')          # Gléon Berty (dépt 11)
    assert act.validate_ref('DFCF', '34-002')
    assert act.validate_ref('DFCF', '49-0010')         # n° sur 4 chiffres
    # Préfixe DFCF optionnel (forme ARML).
    assert act.validate_ref('DFCF', 'DFCF49-0010')
    assert act.validate_ref('DFCF', 'dfcf-11-104')     # normalisé en majuscules
    assert act.validate_ref('DFCF', '971-001')         # DOM (dépt 3 chiffres)


def test_dfcf_reference_invalide():
    assert not act.validate_ref('DFCF', 'F-0123')      # format POTA
    assert not act.validate_ref('DFCF', '1-104')       # dépt sur 1 chiffre
    assert not act.validate_ref('DFCF', '11-10')       # n° trop court
    assert not act.validate_ref('DFCF', 'DFCF')        # référence absente


def test_dmf_present_seuil_et_provisoire():
    assert 'DMF' in act.PROGRAM_SPECS
    spec = act.PROGRAM_SPECS['DMF']
    assert spec['name'] == 'Diplôme des Moulins de France'
    assert spec['min_qso'] == 100
    assert 'adif_tag' not in spec
    assert spec.get('format_provisoire') is True     # marqué à reconfirmer


def test_dmf_reference_tolerante():
    # Regex TOLÉRANT (F4GLD) : on ne rejette pas une référence réelle qui ne
    # suit pas exactement DMF01.001 -> variantes de séparateur/espace acceptées.
    for ref in ['DMF01.001', 'DMF89.060', 'dmf2b.012', 'DMF-01-001',
                'DMF01-001', 'DMF 01.001', 'DMF1.001']:
        assert act.validate_ref('DMF', ref), ref


def test_dmf_reference_clairement_invalide():
    # Seul le clairement non-DMF est rejeté (pas de faux rejet d'une vraie réf).
    assert not act.validate_ref('DMF', 'FR-0123')     # format POTA
    assert not act.validate_ref('DMF', 'DMFABC')      # ni chiffres ni séparateur
    assert not act.validate_ref('DMF', 'POTA01.001')  # autre programme
