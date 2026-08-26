# -*- coding: utf-8 -*-
"""Lot robustesse 2 — deux cas-bords de l'audit.

1. logx_flags.flag_emoji : le garde-fou isalpha() accepte des lettres NON-ASCII
   (É, Ñ, cyrillique…), produisant un codepoint hors de la plage des indicateurs
   régionaux (drapeau parasite) au lieu de ''.
2. logx_sat_passes.passages : float(heures or 24) transforme un heures=0
   EXPLICITE en fenêtre de 24 h (0 traité comme falsy)."""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_flags as flags


def test_flag_emoji_valide():
    assert flags.flag_emoji('FR') == '🇫🇷'


def test_flag_emoji_rejette_non_ascii():
    assert flags.flag_emoji('ÉÀ') == '', "lettres non-ASCII -> pas de drapeau parasite"


def test_flag_emoji_rejette_chiffres_et_longueur():
    assert flags.flag_emoji('F1') == ''
    assert flags.flag_emoji('FRA') == ''


def test_sat_passes_heures_zero_ne_devient_pas_24():
    import logx_sat_passes as sp
    # _fenetre_heures est le calcul isolé de la fenêtre : 0 doit rester 0.
    assert sp._fenetre_heures(0) == 0.0
    assert sp._fenetre_heures(None) == 24.0
    assert sp._fenetre_heures('') == 24.0
    assert sp._fenetre_heures(72) == 72.0
