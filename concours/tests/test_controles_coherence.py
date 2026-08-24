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


# ─── RST / mode ──────────────────────────────────────────────────────────────

def test_rst_59_sur_ft8_signale():
    r = ctrl.controle_rst_mode({'mode': 'FT8', 'rst_sent': '599', 'rst_rcvd': '-12'})
    assert r is not None and r[1] == 'rst_incoherent_mode'


def test_rst_db_sur_ft8_ok():
    assert ctrl.controle_rst_mode({'mode': 'FT8', 'rst_sent': '-08', 'rst_rcvd': '-12'}) is None


def test_rst_599_sur_cw_ok():
    assert ctrl.controle_rst_mode({'mode': 'CW', 'rst_sent': '599', 'rst_rcvd': '599'}) is None


# ─── références d'activation ─────────────────────────────────────────────────

def test_activation_sans_ref_signale():
    rs = ctrl.controle_activation_ref({'my_sig': 'SOTA', 'my_sig_info': ''})
    assert any(c == 'activation_sans_ref' for _, c, _ in rs)


def test_activation_ref_mal_formee_signale():
    rs = ctrl.controle_activation_ref({'my_sig': 'SOTA', 'my_sig_info': 'PAS-BON'})
    assert any(c == 'ref_format_invalide' for _, c, _ in rs)


def test_activation_ref_valide_ok():
    rs = ctrl.controle_activation_ref({'my_sig': 'SOTA', 'my_sig_info': 'F/AB-123'})
    assert rs == []


def test_activation_programme_inconnu_ignore():
    # un my_sig qui n'est pas un programme connu (ex. un club) n'est pas contrôlé
    rs = ctrl.controle_activation_ref({'my_sig': 'MON-CLUB', 'my_sig_info': ''})
    assert rs == []


# ─── agrégateur ──────────────────────────────────────────────────────────────

def test_aggregateur_reunit_les_findings():
    q = {'freq': '7.0', 'band': '14', 'mode': 'FT8', 'rst_sent': '599',
         'rst_rcvd': '599', 'date': '20260824'}
    codes = {c for _, c, _ in ctrl.controles_coherence(q, '20260824')}
    assert 'freq_bande_incoherente' in codes and 'rst_incoherent_mode' in codes
