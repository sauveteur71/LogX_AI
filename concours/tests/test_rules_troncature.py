# -*- coding: utf-8 -*-
"""Audit : le règlement de concours était tronqué EN SILENCE à MAX_RULES_CHARS ;
la fin (souvent les tableaux de points/multiplicateurs) était perdue pour l'IA
sans que personne ne soit averti. Désormais : note explicite dans le prompt +
drapeau de troncature remonté."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_rules_ai as ra


def test_texte_long_est_tronque_avec_note():
    txt = 'A' * (ra.MAX_RULES_CHARS + 500)
    bloc, tronque = ra._doc_pour_prompt(txt, None)
    assert tronque is True
    assert 'TRONQU' in bloc.upper(), "la note de troncature doit prévenir l'IA"
    assert len(bloc) < len(txt) + 400   # le corps est bien coupé


def test_texte_court_pas_de_troncature():
    bloc, tronque = ra._doc_pour_prompt('B' * 1000, None)
    assert tronque is False
    assert 'TRONQU' not in bloc.upper()


def test_pdf_natif_pas_de_bloc_texte():
    bloc, tronque = ra._doc_pour_prompt('ignoré', b'%PDF-1.7...')
    assert bloc == '' and tronque is False
