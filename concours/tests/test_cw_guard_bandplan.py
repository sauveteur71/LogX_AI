# -*- coding: utf-8 -*-
"""Garde-fou d'émission CW — vérification HORS PLAN DE BANDE (F4GLD).

en_bande_amateur() (logx_frequences, inventaire IARU R1) + son intégration dans
cw_tx_autorise : on refuse de keyer si la fréquence est CONNUE et hors bande ;
fréquence inconnue (pas de CAT) -> on ne bloque pas dessus.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_frequences as fr
from logx_cw_guard import cw_tx_autorise


def test_en_bande_hf_vhf_uhf():
    assert fr.en_bande_amateur(14030) is True     # 20 m CW
    assert fr.en_bande_amateur(7010) is True       # 40 m
    assert fr.en_bande_amateur(50100) is True       # 6 m
    assert fr.en_bande_amateur(145500) is True      # 2 m
    assert fr.en_bande_amateur(432100) is True      # 70 cm
    assert fr.en_bande_amateur(1296000) is True     # 23 cm


def test_hors_bande():
    assert fr.en_bande_amateur(100000) is False     # 100 MHz : entre 6 m et 2 m
    assert fr.en_bande_amateur(30000) is False      # 30 MHz : entre 10 m et 6 m
    assert fr.en_bande_amateur(500) is False        # 500 kHz : hors 630/2200 m


def test_freq_indeterminee_ne_bloque_pas():
    assert fr.en_bande_amateur(None) is None
    assert fr.en_bande_amateur('') is None
    assert fr.en_bande_amateur('abc') is None


def test_guard_refuse_hors_bande():
    ok, raison = cw_tx_autorise({'armed': True, 'mode': 'CW', 'freq_khz': 100000})
    assert ok is False and 'hors des bandes' in raison


def test_guard_autorise_en_bande():
    ok, raison = cw_tx_autorise({'armed': True, 'mode': 'CW', 'freq_khz': 14030})
    assert ok is True and raison == ''


def test_guard_freq_absente_ou_illisible_ne_bloque_pas():
    assert cw_tx_autorise({'armed': True, 'mode': 'CW'})[0] is True
    assert cw_tx_autorise({'armed': True, 'mode': 'CW', 'freq_khz': ''})[0] is True
    assert cw_tx_autorise({'armed': True, 'mode': 'CW', 'freq_khz': 'xyz'})[0] is True


def test_le_hors_bande_ne_court_circuite_pas_les_autres_gardes():
    # TX non armé prime, même avec une fréquence en bande
    assert cw_tx_autorise({'armed': False, 'mode': 'CW', 'freq_khz': 14030})[0] is False
    # mode non-CW prime aussi
    assert cw_tx_autorise({'armed': True, 'mode': 'USB', 'freq_khz': 14030})[0] is False
