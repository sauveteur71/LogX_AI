# -*- coding: utf-8 -*-
"""IA-2 lot 1 — enrichissement DÉTERMINISTE : dérive du PAYS/CONTINENT/ZONES
depuis le seul indicatif (via logx_dxcc, cty.dat). Fonction PURE, ne remplit
QUE les cases vides, ne renvoie que ce qu'elle dérive. Décision-free : les
valeurs viennent de cty.dat, aucune table inventée, aucune décision produit."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_enrichissement as enr   # noqa: E402


def test_derive_pays_continent_zones_depuis_indicatif():
    d = enr.enrichir({'call': 'W1AW'})
    # États-Unis, Amérique du Nord ; les zones sont renseignées (valeurs cty.dat).
    assert 'United States' in str(d.get('dxcc_country', '')) or 'USA' in str(d.get('dxcc_country', ''))
    assert d.get('continent') == 'NA'
    assert str(d.get('cqz', '')) != ''
    assert str(d.get('ituz', '')) != ''


def test_ne_remplit_que_les_cases_vides():
    # cqz déjà saisi -> intouché ; les autres dérivés.
    d = enr.enrichir({'call': 'W1AW', 'cqz': '99'})
    assert 'cqz' not in d, d      # ne propose PAS d'écraser une saisie
    assert 'continent' in d       # les vides restent proposés


def test_indicatif_inconnu_ne_derive_rien():
    # QQ n'est attribué à aucune entité dans cty.dat -> lookup None -> {}.
    d = enr.enrichir({'call': 'QQ1XYZ'})
    assert d == {}, d


def test_sans_indicatif_rien():
    assert enr.enrichir({}) == {}


def test_portable_lieu_prime():
    # F/DL1ABC = DL1ABC opérant depuis la France -> pays France (préfixe de lieu).
    d = enr.enrichir({'call': 'F/DL1ABC'})
    assert 'France' in str(d.get('dxcc_country', '')), d
