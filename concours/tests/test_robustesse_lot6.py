# -*- coding: utf-8 -*-
"""Lot robustesse 6 (audit) — deux cas de données.

1. logx_export._qso_datetime : une date PARTIELLE non vide ('2026') passait
   telle quelle -> QSO_DATE ADIF invalide. Défaut si longueur != 8.
2. logx_focus.ouverture_par_bande : un region_name VIDE était ajouté à la liste
   des noms (la garde ne couvrait qu'un des deux chemins)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_export as export
import logx_focus as focus


def test_qso_datetime_date_complete_preservee():
    d, t = export._qso_datetime({'date': '20260705', 'time': '14:32'})
    assert d == '20260705' and t == '1432'


def test_qso_datetime_date_partielle_retombe_sur_sentinel():
    d, _ = export._qso_datetime({'date': '2026', 'time': '14:32'})
    assert d == '19000101', "une date partielle non vide n'est pas une date ADIF valide"


def test_qso_datetime_date_vide_sentinel():
    d, _ = export._qso_datetime({'date': '', 'time': ''})
    assert d == '19000101'


def test_focus_region_sans_nom_pas_ajoutee():
    res = focus.ouverture_par_bande([
        {'region_name': '', 'best_band': '50', 'best_score': 10, 'open_bands': ['50', '144']}])
    for _score, noms in res.values():
        assert '' not in noms, "un nom de région vide ne doit pas être ajouté aux régions ouvertes"
