# -*- coding: utf-8 -*-
"""RTTY / PSK31 / SSTV ajoutés au bouton QSY — centres d'activité IARU R1.

Données fournies par F4GLD le 23/08/2026 (mêmes tables que les fréquences WSJT).
Décisions actées :
- RTTY = FSK VRAI par défaut sur le bouton (radio_mode 'RTTY') ; une variante
  AFSK 'USB' (même fréquence) est conservée dans les données pour l'audio pur
  (LogX a aussi un décodeur RTTY carte-son, logx_rttydecoder.js).
- PSK31 et SSTV HF/6m/2m = 'USB' (AFSK carte son) ; SSTV 70 cm = 'FM' (note
  F4GLD « SSTV FM/AFSK »).
- 145.800 MHz N'EST PAS enregistrée comme SSTV (satellite/ISS, consigne F4GLD).
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_frequences as fr   # noqa: E402


def test_psk31_centres():
    assert fr.dial_freq('80m', 'PSK31') == 3.580
    assert fr.dial_freq('40m', 'PSK31') == 7.070
    assert fr.dial_freq('30m', 'PSK31') == 10.142
    assert fr.dial_freq('20m', 'PSK31') == 14.070
    assert fr.dial_freq('15m', 'PSK31') == 21.070
    assert fr.dial_freq('10m', 'PSK31') == 28.120


def test_rtty_centres_fsk():
    assert fr.dial_freq('80m', 'RTTY') == 3.590
    assert fr.dial_freq('40m', 'RTTY') == 7.043
    assert fr.dial_freq('30m', 'RTTY') == 10.143
    assert fr.dial_freq('20m', 'RTTY') == 14.083
    assert fr.dial_freq('15m', 'RTTY') == 21.080
    assert fr.dial_freq('10m', 'RTTY') == 28.080


def test_sstv_centres():
    for band, f in [('80m', 3.735), ('40m', 7.165), ('20m', 14.230),
                    ('15m', 21.340), ('10m', 28.680), ('6m', 50.510),
                    ('2m', 144.500), ('70cm', 433.400)]:
        assert fr.dial_freq(band, 'SSTV') == f, band


def test_rtty_fsk_par_defaut_variante_usb_conservee():
    t = fr.digital_table()
    # le bouton QSY (table principale, sans variante) commande le poste en FSK vrai
    assert t['table']['20m']['RTTY']['radio_mode'] == 'RTTY'
    assert t['table']['80m']['RTTY']['radio_mode'] == 'RTTY'
    # la variante AFSK (USB, même fréquence) reste accessible dans les données
    assert fr.dial_freq('20m', 'RTTY', variant='AFSK_USB') == 14.083
    assert fr.dial_freq('40m', 'RTTY', variant='AFSK_USB') == 7.043


def test_radio_modes_psk_sstv():
    t = fr.digital_table()
    assert t['table']['80m']['PSK31']['radio_mode'] == 'USB'
    assert t['table']['20m']['SSTV']['radio_mode'] == 'USB'
    assert t['table']['6m']['SSTV']['radio_mode'] == 'USB'
    assert t['table']['2m']['SSTV']['radio_mode'] == 'USB'
    assert t['table']['70cm']['SSTV']['radio_mode'] == 'FM'   # note F4GLD


def test_145800_absente_des_sstv():
    for e in fr._load():
        if e.get('mode') == 'SSTV':
            assert abs(float(e['dial_mhz']) - 145.800) > 1e-6, e


def test_modes_texte_image_dans_digital_table():
    t = fr.digital_table()
    for m in ('PSK31', 'RTTY', 'SSTV'):
        assert m in t['modes'], m
