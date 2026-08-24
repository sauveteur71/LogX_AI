# -*- coding: utf-8 -*-
"""IA-1 — contrôles de cohérence déterministes (logx_controles). Fonctions
pures : chaque cas net doit rendre son finding, chaque cas sain/ambigu None."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_controles as ctrl   # noqa: E402


# ─── freq / bande ────────────────────────────────────────────────────────────

def test_freq_bande_incoherente_signale():
    r = ctrl.controle_freq_bande({'freq': '7.150', 'band': '14'})
    assert r is not None and r[0] == 'attention' and r[1] == 'freq_bande_incoherente'


def test_freq_bande_coherente_ok():
    assert ctrl.controle_freq_bande({'freq': '14.075', 'band': '14'}) is None


def test_freq_absente_ou_inconnue_silencieux():
    assert ctrl.controle_freq_bande({'band': '14'}) is None
    assert ctrl.controle_freq_bande({'freq': 'zzz', 'band': '14'}) is None


# ─── date future ─────────────────────────────────────────────────────────────

def test_date_future_signale():
    r = ctrl.controle_date_future({'date': '20260825'}, '20260824')
    assert r is not None and r[1] == 'date_future'


def test_date_passee_ou_jour_ok():
    assert ctrl.controle_date_future({'date': '20260824'}, '20260824') is None
    assert ctrl.controle_date_future({'date': '20200101'}, '20260824') is None


# ─── heure de fin ────────────────────────────────────────────────────────────

def test_heure_fin_avant_debut_signale():
    r = ctrl.controle_heure_fin({'date': '20260824', 'time': '1215', 'time_off': '1200'})
    assert r is not None and r[0] == 'info' and r[1] == 'heure_fin_avant_debut'


def test_heure_fin_normale_ok():
    assert ctrl.controle_heure_fin({'date': '20260824', 'time': '1215', 'time_off': '1230'}) is None
    assert ctrl.controle_heure_fin({'date': '20260824', 'time': '1215'}) is None
