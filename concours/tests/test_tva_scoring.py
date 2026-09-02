# -*- coding: utf-8 -*-
"""Moteur de score TVA (logx_tva_scoring) — barème des règlements REF (sourcé
par F4GLD). Module PUR : on vérifie le barème exact (coefficients par bande ×
section, ÷2 unilatéral en section 1), l'agrégation, et la validation du code
vidéo (4 chiffres différents, non-consécutifs pour l'IARU, unique par bande)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_tva_scoring as T   # noqa: E402

S = T.TvaSection
L = T.TvaLinkType


def _q(band, section, link, dist):
    return T.TvaQso(band, section, link, dist)


# ── Barème par bande × section ───────────────────────────────────────────────

def test_bareme_section_1_bilateral():
    # 70 cm = 2 pts/km, 23 cm = 4, au-dessus = 10 (section 1, bilatéral)
    assert T.tva_qso_points(_q('432', S.SECTION_1, L.BILATERAL, 100)) == 200
    assert T.tva_qso_points(_q('1296', S.SECTION_1, L.BILATERAL, 100)) == 400
    assert T.tva_qso_points(_q('2320', S.SECTION_1, L.BILATERAL, 100)) == 1000


def test_bareme_section_2_moitie():
    # Section 2 (réception seule) = moitié des coefficients
    assert T.tva_qso_points(_q('432', S.SECTION_2, L.RECEIVE_ONLY, 100)) == 100
    assert T.tva_qso_points(_q('1296', S.SECTION_2, L.RECEIVE_ONLY, 100)) == 200
    assert T.tva_qso_points(_q('10368', S.SECTION_2, L.RECEIVE_ONLY, 100)) == 500


def test_unilaterale_section_1_divise_par_deux():
    """Section 1 + liaison unilatérale -> points ÷ 2."""
    bilat = T.tva_qso_points(_q('432', S.SECTION_1, L.BILATERAL, 100))
    uni = T.tva_qso_points(_q('432', S.SECTION_1, L.UNILATERAL, 100))
    assert uni == bilat / 2 == 100


def test_unilaterale_ne_touche_pas_la_section_2():
    """Le ÷2 unilatéral est une règle de SECTION 1 : pas de double peine en s2."""
    s2_uni = T.tva_qso_points(_q('432', S.SECTION_2, L.UNILATERAL, 100))
    assert s2_uni == 100   # 1 pt/km, pas 50


def test_classes_de_bande():
    assert T.tva_band_class('432') == '70CM'
    assert T.tva_band_class('1296') == '23CM'
    for b in ('2320', '3400', '5760', '10368', '24048'):
        assert T.tva_band_class(b) == 'ABOVE_23CM'
    # tolère les libellés
    assert T.tva_band_class('70cm') == '70CM' and T.tva_band_class('23 cm') == '23CM'


# ── Agrégation ───────────────────────────────────────────────────────────────

def test_score_total_et_par_bande():
    qsos = [_q('432', S.SECTION_1, L.BILATERAL, 100),      # 200
            _q('432', S.SECTION_1, L.BILATERAL, 50),       # 100
            _q('1296', S.SECTION_1, L.BILATERAL, 25)]      # 100
    r = T.score_tva(qsos)
    assert r['total'] == 400
    assert r['per_band'] == {'432': 300.0, '1296': 100.0}
    assert r['qso_count'] == 3


# ── Code vidéo ───────────────────────────────────────────────────────────────

def test_code_video_quatre_chiffres_differents():
    assert T.validate_video_code('1357') == []
    assert 'quatre chiffres' in ' '.join(T.validate_video_code('123'))     # trop court
    assert 'différents' in ' '.join(T.validate_video_code('1123'))         # doublon


def test_code_video_non_consecutif_iaru():
    # IARU : chiffres non consécutifs
    assert T.validate_video_code('1234', non_consecutive=True)             # 1,2,3,4 -> refusé
    assert T.validate_video_code('1357', non_consecutive=True) == []       # ok
    # National TVA : la non-consécutivité n'est PAS imposée
    assert T.validate_video_code('1234') == []


def test_code_video_unique_par_bande():
    assert T.validate_video_code('1357', previous_codes={'1357'})          # déjà utilisé -> refusé
    assert T.validate_video_code('1357', previous_codes={'2468'}) == []


# ── Distance depuis les locators échangés ────────────────────────────────────

def test_distance_depuis_locators():
    d = T.distance_km_depuis_locators('JN18', 'JN03')
    assert d and 500 < d < 650          # ordre de grandeur connu
    assert T.distance_km_depuis_locators('JN18', 'XXXX') is None  # locator illisible
