# -*- coding: utf-8 -*-
"""ADIF — non-régression de la frontière 6m/5m (audit STRATE-3 ③ classé faux
positif par F4GLD). Les intervalles restent FERMÉS ; le seuil 54.000001 MHz
évite le double classement à 54,000000 MHz sans casser les bornes hautes des
autres bandes. Ce test verrouille le comportement intentionnel."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_adif_enums as ae  # noqa: E402


def test_frontiere_6m_5m():
    assert ae.band_from_freq(54.000000) == '6m'
    assert ae.band_from_freq(54.000001) == '5m'


def test_bornes_hautes_non_contigues_restent_classees():
    # 14,35 = borne haute 20m (aucune bande contiguë juste après) : doit rester
    # « 20m ». C'est ce qu'un passage global en semi-ouvert casserait.
    assert ae.band_from_freq(14.35) == '20m'
    assert ae.band_from_freq(29.7) == '10m'
    assert ae.band_from_freq(148.0) == '2m'


def test_milieu_de_bande_toujours_correct():
    assert ae.band_from_freq(52.0) == '6m'
    assert ae.band_from_freq(60.0) == '5m'
