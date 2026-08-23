# -*- coding: utf-8 -*-
"""WinKeyer WK3 — helpers de réglage PURS (Phase 2 keyer CW).

Trames octet par octet vérifiées contre les exemples officiels K1EL WK3.1
fournis par F4GLD (23/08). Fonctions pures (aucun port, aucune émission).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_winkeyer as wk


def test_opcode_ratio_est_0x17_pas_0x0c():
    # piège classique : 0x0C = HSCW, le ratio dit/dah est 0x17.
    assert wk.CMD_SET_DIT_DAH_RATIO == 0x17
    assert wk.CMD_SET_DIT_DAH_RATIO != 0x0C


def test_weighting():
    assert wk.wk_set_weighting(50) == bytes([0x03, 0x32])
    assert wk.wk_set_weighting(45) == bytes([0x03, 0x2D])
    assert wk.wk_set_weighting(55) == bytes([0x03, 0x37])
    for bad in (9, 91, 0, 100):
        with pytest.raises(ValueError):
            wk.wk_set_weighting(bad)


def test_ratio_dit_dah():
    assert wk.wk_set_dit_dah_ratio(50) == bytes([0x17, 0x32])   # 1:3 standard
    assert wk.wk_set_dit_dah_ratio(33) == bytes([0x17, 0x21])
    assert wk.wk_set_dit_dah_ratio(66) == bytes([0x17, 0x42])
    for bad in (32, 67):
        with pytest.raises(ValueError):
            wk.wk_set_dit_dah_ratio(bad)


def test_farnsworth():
    assert wk.wk_set_farnsworth(25) == bytes([0x0D, 0x19])
    assert wk.wk_set_farnsworth(20) == bytes([0x0D, 0x14])
    for bad in (9, 100):
        with pytest.raises(ValueError):
            wk.wk_set_farnsworth(bad)


def test_sidetone_formule_62500():
    assert wk.wk_set_sidetone(800) == bytes([0x01, 78])    # 62500/800≈78 (0x4E)
    assert wk.wk_set_sidetone(1000) == bytes([0x01, 62])   # 62500/1000≈62 (0x3E)
    assert wk.wk_set_sidetone(700) == bytes([0x01, 89])    # 62500/700≈89 (0x59)
    for bad in (499, 4001):
        with pytest.raises(ValueError):
            wk.wk_set_sidetone(bad)


def test_ptt_lead_tail_pas_de_10ms():
    assert wk.wk_set_ptt_lead_tail(100, 300) == bytes([0x04, 10, 30])   # 04 0A 1E
    assert wk.wk_set_ptt_lead_tail(0, 0) == bytes([0x04, 0, 0])
    with pytest.raises(ValueError):
        wk.wk_set_ptt_lead_tail(15, 0)      # pas multiple de 10 ms
    with pytest.raises(ValueError):
        wk.wk_set_ptt_lead_tail(0, 3000)    # > 2500 ms


def test_pin_config_key1_ptt_sidetone():
    val = wk.PINCFG_KEY_1 | wk.PINCFG_PTT | wk.PINCFG_SIDETONE
    assert val == 0x0B
    assert wk.wk_set_pin_config(val) == bytes([0x09, 0x0B])


def test_mode_profil_logx_par_defaut():
    assert wk.MODE_LOGX_DEFAUT == 0x16           # IambicA|echo série|autospace
    assert wk.wk_set_mode(wk.MODE_LOGX_DEFAUT) == bytes([0x0E, 0x16])
    # le watchdog paddle reste ACTIF : le profil par défaut ne pose PAS son bit
    assert not (wk.MODE_LOGX_DEFAUT & wk.MODE_DISABLE_PADDLE_WATCHDOG)
