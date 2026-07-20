# -*- coding: utf-8 -*-
"""Tests des fonctions pures de logx_utils — cas vérifiés à la main."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logx_utils import (locator_to_latlon, haversine, bearing,
                                cardinal, is_digital_mode)


# ─── locator_to_latlon ───────────────────────────────────────────────────────
# Référence : centre de carré Maidenhead calculé à la main.
# JN15XC : J=9 → lon 9×20−180=0 ; '1' → +2 ; X=23 → +23×(2/24) ; +1/24 (centre)
#          N=13 → lat 13×10−90=40 ; '5' → +5 ; C=2 → +2/24 ; +0.5/24 (centre)

def test_locator_jn15xc():
    lat, lon = locator_to_latlon('JN15XC')
    assert abs(lat - 45.1042) < 0.001
    assert abs(lon - 3.9583) < 0.001


def test_locator_minuscules_acceptees():
    assert locator_to_latlon('jn15xc') == locator_to_latlon('JN15XC')


def test_locator_invalide():
    assert locator_to_latlon('') == (None, None)
    assert locator_to_latlon('JN15') == (None, None)     # trop court
    assert locator_to_latlon(None) == (None, None)


# ─── haversine ───────────────────────────────────────────────────────────────

def test_haversine_meme_point():
    assert haversine(45.0, 3.0, 45.0, 3.0) == 0


def test_haversine_jn15xc_jn18du():
    """Chaspinhac → région parisienne : ~435 km (vérifié par calcul manuel :
    Δlat 3.75°≈417 km, Δlon 1.67°×cos(47°)≈126 km → √(417²+126²)≈436 km)."""
    d = haversine(45.1042, 3.9583, 48.8542, 2.2917)
    assert 425 <= d <= 445


def test_haversine_un_degre_latitude():
    """1° de latitude ≈ 111 km partout sur le globe."""
    d = haversine(45.0, 3.0, 46.0, 3.0)
    assert 110 <= d <= 112


# ─── bearing / cardinal ──────────────────────────────────────────────────────

def test_bearing_nord():
    assert bearing(45.0, 3.0, 46.0, 3.0) == 0


def test_bearing_est_sur_equateur():
    assert bearing(0.0, 0.0, 0.0, 1.0) == 90


def test_bearing_sud():
    assert bearing(46.0, 3.0, 45.0, 3.0) == 180


def test_cardinal_points_principaux():
    assert cardinal(0) == 'N'
    assert cardinal(90) == 'E'
    assert cardinal(180) == 'S'
    assert cardinal(270) == 'O'      # convention française (Ouest)
    assert cardinal(225) == 'SO'
    assert cardinal(360) == 'N'      # bouclage


# ─── is_digital_mode ─────────────────────────────────────────────────────────

def test_modes_numeriques_detectes():
    assert is_digital_mode('FT8')
    assert is_digital_mode('ft4')                      # insensible à la casse
    assert is_digital_mode('gros pileup RTTY 20m')     # détection en contexte


def test_modes_analogiques_ignores():
    assert not is_digital_mode('SSB')
    assert not is_digital_mode('CW')
    assert not is_digital_mode('FM 145.500')
