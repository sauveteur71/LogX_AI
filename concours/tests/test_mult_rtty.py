# -*- coding: utf-8 -*-
"""Multiplicateurs des concours RTTY dans le score AUTORITAIRE (calc_total_score).

Valeurs SOURCÉES :
  - CQ WW RTTY, cqwwrtty.com §IV.C : mult = zones CQ + pays DXCC + états US(48)
    /DC/aires canadiennes(14) des stations W/VE, comptés PAR BANDE. Alaska (KL7)
    et Hawaii (KH6) comptent comme PAYS seulement, jamais comme état.
  - ARRL RTTY Roundup, contests.arrl.org PDF §5.3 : 1 pt/QSO × (états US +
    provinces VE + entités DXCC hors US/Canada), chaque mult compté UNE FOIS
    (ALL-BAND, « once, not once per band »). KH6/KL7 comptent comme DXCC.

Le score autoritaire lit la vraie valeur REÇUE du QSO loggué (num_rcvd) et
l'entité DXCC/zone déduite de l'indicatif — jamais un proxy d'estimation.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_scoring as scoring                       # noqa: E402
from logx_definitions import CONTEST_DEFINITIONS     # noqa: E402


# ─── CQ WW RTTY : zones + DXCC + états/provinces W/VE, PAR BANDE ──────────────

def test_cqww_rtty_etat_wve_compte_par_bande():
    cdef = CONTEST_DEFINITIONS['CQ_WW_RTTY']
    qsos = [
        # 14 MHz : W1AW (K, zone 5, état MA), K9CT (K, zone 5, état IL),
        #          F6ABC (F, zone 14, DX sans état)
        {'call': 'W1AW',  'band': '14', 'num_rcvd': '05 MA', 'points': 3},
        {'call': 'K9CT',  'band': '14', 'num_rcvd': '04 IL', 'points': 3},
        {'call': 'F6ABC', 'band': '14', 'num_rcvd': '14',    'points': 1},
        # 7 MHz : W1AW à nouveau — mult neuf sur cette bande (décompte par bande)
        {'call': 'W1AW',  'band': '7',  'num_rcvd': '05 MA', 'points': 3},
    ]
    # 14 MHz : zones {5,14}=2, dxcc {K,F}=2, états {MA,IL}=2 -> 6 mults
    #  7 MHz : zones {5}=1,    dxcc {K}=1,   états {MA}=1     -> 3 mults
    # total mults = 9 ; points = 3+3+1+3 = 10 ; score = 10 * 9 = 90
    assert scoring.calc_total_score(qsos, cdef) == 90


def test_cqww_rtty_alaska_hawaii_jamais_etat():
    """KL7/KH6 : pays seulement (§IV.C), l'échange 'AK'/'HI' ne doit PAS créer
    de multiplicateur d'état."""
    cdef = CONTEST_DEFINITIONS['CQ_WW_RTTY']
    qsos = [
        {'call': 'KL7RA', 'band': '14', 'num_rcvd': '01 AK', 'points': 3},
        {'call': 'KH6XX', 'band': '14', 'num_rcvd': '31 HI', 'points': 3},
    ]
    # KL7RA : zone 1 + dxcc KL (pas d'état AK). KH6XX : zone 31 + dxcc KH6.
    # mults 14 MHz : zones {1,31}=2 + dxcc {KL,KH6}=2 = 4 ; PAS d'état.
    # points = 6 ; score = 6 * 4 = 24.
    assert scoring.calc_total_score(qsos, cdef) == 24


# ─── ARRL RTTY Roundup : états + provinces + DXCC hors US/VE, ALL-BAND ────────

def test_rtty_roundup_multiplicateur_all_band():
    cdef = CONTEST_DEFINITIONS['ARRL_RTTY_ROUNDUP']
    qsos = [
        {'call': 'W1AW',  'band': '14', 'num_rcvd': 'CT',  'points': 1},
        # même état CT sur une AUTRE bande -> PAS un multiplicateur neuf (all-band)
        {'call': 'W1AW',  'band': '7',  'num_rcvd': 'CT',  'points': 1},
        {'call': 'VE3XX', 'band': '14', 'num_rcvd': 'ON',  'points': 1},
        # DX : n° de série -> multiplicateur = entité DXCC (F)
        {'call': 'F6ABC', 'band': '14', 'num_rcvd': '123', 'points': 1},
        # Alaska : compte comme DXCC (KL), pas comme état
        {'call': 'KL7RA', 'band': '14', 'num_rcvd': '55',  'points': 1},
    ]
    # mults ALL-BAND uniques : état CT, province ON, dxcc F, dxcc KL = 4
    #   (CT compté UNE fois malgré 2 bandes) ; points = 5 ; score = 5 * 4 = 20
    assert scoring.calc_total_score(qsos, cdef) == 20


def test_rtty_roundup_dxcc_exclut_pas_ak_hi_du_compte():
    """Un log 100 % DX : le multiplicateur est le nombre d'entités DXCC
    distinctes (all-band), KL7/KH6 inclus comme entités."""
    cdef = CONTEST_DEFINITIONS['ARRL_RTTY_ROUNDUP']
    qsos = [
        {'call': 'F6ABC',  'band': '14', 'num_rcvd': '1', 'points': 1},
        {'call': 'DL1XX',  'band': '14', 'num_rcvd': '2', 'points': 1},
        {'call': 'DL2YY',  'band': '7',  'num_rcvd': '3', 'points': 1},  # DL déjà vu (all-band)
    ]
    # entités DXCC uniques all-band : F, DL = 2 ; points = 3 ; score = 3 * 2 = 6
    assert scoring.calc_total_score(qsos, cdef) == 6
