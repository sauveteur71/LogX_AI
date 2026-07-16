# -*- coding: utf-8 -*-
"""Tests de la base DXCC hors ligne et de sa mise à jour automatique."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import radiocontest_dxcc as dxcc


def test_lookup_pays_et_zones():
    r = dxcc.lookup('F6KQJ')
    assert r['country'] == 'France' and r['continent'] == 'EU' and r['cq_zone'] == 14
    assert dxcc.lookup('W1AW')['prefix'] == 'K'
    assert dxcc.lookup('UA0ABC')['continent'] == 'AS'      # Russie asiatique
    assert dxcc.lookup('UA9XYZ')['continent'] == 'EU'      # Komi : piège cty.dat


def test_lookup_barres_et_suffixes():
    assert dxcc.lookup('F6KQJ/P')['country'] == 'France'
    assert dxcc.lookup('F/ON4ABC')['country'] == 'France'  # préfixe hôte


def test_country_key_repli():
    """Indicatif inconnu → repli 2 caractères (ancien comportement)."""
    assert dxcc.country_key('QQ9ZZZ') == 'QQ'


def test_validation_cty():
    assert not dxcc._looks_valid_cty('')
    assert not dxcc._looks_valid_cty('<html>404 Not Found</html>')
    assert not dxcc._looks_valid_cty('France:14:27:EU:46:-2:-1:F:\n F;' * 10)  # trop court
    real = open('cty.dat', encoding='utf-8', errors='replace').read()
    assert dxcc._looks_valid_cty(real)


def test_pas_de_maj_si_fichier_recent():
    """cty.dat vient d'être téléchargé : aucune requête réseau ne doit partir."""
    assert dxcc._cty_age_days() < 1
    assert dxcc.update_cty_if_stale(max_age_days=30) is False
