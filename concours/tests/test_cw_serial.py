# -*- coding: utf-8 -*-
"""Keyer CW série DTR/RTS — cœur Morse/timing PUR (Phase 3A).

Vérifie les durées standard (PARIS), la table Morse, les prosignes et le rejet
propre des caractères non manipulables. Aucune émission (fonctions pures).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_cw_serial as cw


def test_dit_ms_reference_paris():
    assert cw.dit_ms(20) == 60.0          # 1200/20
    assert cw.dit_ms(24) == 50.0
    assert cw.dit_ms(0) == cw.dit_ms(1)   # borné à >=1, jamais division par 0


def test_lettre_simple_E():
    # E = '.' -> un seul point manipulé
    assert cw.keying_sequence('E', 20) == [(True, 60.0)]


def test_lettre_A_point_trait_avec_gap_intra():
    # A = '.-' : point (1 dit) + gap intra (1 dit) + trait (3 dit)
    assert cw.keying_sequence('A', 20) == [(True, 60.0), (False, 60.0), (True, 180.0)]


def test_gap_inter_caractere_3_dits():
    seq = cw.keying_sequence('EE', 20)      # E, gap inter-car, E
    assert seq == [(True, 60.0), (False, 180.0), (True, 60.0)]


def test_gap_inter_mot_7_dits():
    seq = cw.keying_sequence('E E', 20)
    assert seq == [(True, 60.0), (False, 420.0), (True, 60.0)]


def test_caractere_inconnu_ignore_sans_keying():
    # '§' absent de la table : émission identique à 'E' seul, jamais un parasite
    assert cw.keying_sequence('E§', 20) == cw.keying_sequence('E', 20)
    assert cw.keying_sequence('§', 20) == []


def test_prosigne_emis_colle_sans_gap_inter_caractere():
    # <AR> = '.-.-.' émis comme UN symbole (pas de gap 3-dit interne)
    ar = cw.keying_sequence('<AR>', 20)
    downs = [d for d in ar if d[0]]
    assert [d[1] for d in downs] == [60.0, 180.0, 60.0, 180.0, 60.0]   # . - . - .
    assert all(g[1] == 60.0 for g in ar if not g[0])                   # gaps intra = 1 dit


def test_table_morse_quelques_valeurs_uit():
    assert cw.MORSE['S'] == '...' and cw.MORSE['O'] == '---'
    assert cw.MORSE['5'] == '.....' and cw.MORSE['/'] == '-..-.'

