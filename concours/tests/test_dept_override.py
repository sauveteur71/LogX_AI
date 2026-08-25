# -*- coding: utf-8 -*-
"""Override « département correspondant » (grille VHF/UHF, feu vert F4GLD 25/08) :
un département SAISI à la main (entendu en direct audio/CW) fait FOI et prime sur
le locator/calldb dans dept_for_qso — pour ne pas être bloqué par un locator
manquant/erroné. ADDITIF : champ vide -> comportement STRICTEMENT inchangé.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_departments as dep   # noqa: E402


def test_dept_manuel_prime_sur_le_locator():
    # JN18 = région parisienne (≠ 42 Loire) : le dept saisi '42' doit primer
    q = {'call': 'F4ABC', 'dept': '42', 'locator': 'JN18DT'}
    assert dep.dept_for_qso(q) == '42'
    assert dep.dept_for_qso(q) != dep.dept_from_locator('JN18DT')


def test_dept_manuel_corse_2a_2b():
    assert dep.dept_for_qso({'call': 'F4ABC', 'dept': '2A', 'locator': 'JN18DT'}) == '2A'
    assert dep.dept_for_qso({'call': 'F4ABC', 'dept': '2b'}) == '2B'   # casse normalisée


def test_dept_manuel_invalide_ignore_retombe_sur_locator():
    q = {'call': 'F4ABC', 'dept': '999', 'locator': 'JN18DT'}
    assert dep.dept_for_qso(q) == dep.dept_from_locator('JN18DT')


def test_dept_vide_comportement_inchange():
    # échange-département : le dept vient de l'échange (manuel vide) -> inchangé
    assert dep.dept_for_qso({'call': 'F4ABC', 'num_rcvd': '43'}) == '43'
    # VHF sans dept saisi : retombe sur le locator, comme avant
    q = {'call': 'F4ABC', 'locator': 'JN18DT'}
    assert dep.dept_for_qso(q) == dep.dept_from_locator('JN18DT')


def test_dept_manuel_prime_meme_sur_une_serie_mal_lue():
    # VHF : num_rcvd = série '42' (que dept_from_exchange prendrait pour la Loire).
    # Le dept SAISI '35' doit primer (l'opérateur a entendu le vrai département).
    q = {'call': 'F4ABC', 'dept': '35', 'num_rcvd': '42', 'locator': 'JN18DT'}
    assert dep.dept_for_qso(q) == '35'
