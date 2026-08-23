# -*- coding: utf-8 -*-
"""Indice d'ouverture ES mélangeait les bandes (logx_es_opening.py) — Strate 2, haute.

opening_index(band) suppose que tous les spots appartiennent à `band`, mais
_fusionner() ne vérifiait jamais la fréquence du spot : dxsummit/dxwatch/hamqth
renvoient TOUT le trafic VHF/UHF, si bien que des spots 144/432/1296 entraient
dans l'historique '50' et déclenchaient un faux indice d'ouverture 50 MHz (et
inversement).

Bornes IARU R1 (source F4GLD) : 50 MHz = 50.000–52.000 ; 144 MHz = 144.000–146.000.
Le champ 'freq' est d'unité MIXTE selon la source (kHz ou MHz) : on réutilise
freq_en_khz(freq, band) du dépôt (déjà testé) pour trancher par la bande, sans
inventer d'heuristique.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_es_opening as es   # noqa: E402


def test_fusionner_ne_garde_que_les_spots_de_la_bande():
    es.reset_history()
    now = 100000.0
    spots = [
        {'call': 'A50KHZ', 'spotter': 'S1', 'freq': 50313, 'lat': 45.0, 'lon': 5.0},   # 50 MHz en kHz
        {'call': 'B50MHZ', 'spotter': 'S2', 'freq': 50.313, 'lat': 45.0, 'lon': 5.0},  # 50 MHz en MHz
        {'call': 'C144', 'spotter': 'S3', 'freq': 144480, 'lat': 45.0, 'lon': 5.0},    # 144 -> exclu de 50
        {'call': 'D432', 'spotter': 'S4', 'freq': 432100, 'lat': 45.0, 'lon': 5.0},    # 432 -> exclu
    ]
    es._fusionner('50', 46.0, 2.0, now, spots)
    calls = {e['call'] for e in es._history['50']}
    assert calls == {'A50KHZ', 'B50MHZ'}, (
        "l'historique '50' ne doit contenir QUE des spots 50 MHz : %r" % calls
    )


def test_fusionner_144_exclut_le_50():
    es.reset_history()
    now = 100000.0
    spots = [
        {'call': 'E50', 'spotter': 'S1', 'freq': 50313, 'lat': 45.0, 'lon': 5.0},
        {'call': 'F144', 'spotter': 'S2', 'freq': 144480, 'lat': 45.0, 'lon': 5.0},
    ]
    es._fusionner('144', 46.0, 2.0, now, spots)
    calls = {e['call'] for e in es._history['144']}
    assert calls == {'F144'}, calls
