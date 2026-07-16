# -*- coding: utf-8 -*-
"""Tests du multiplicateur département (concours REF)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radiocontest_departments import (dept_from_exchange, department_mult_count,
                                      DEPARTMENTS)


def test_table_complete():
    assert len(DEPARTMENTS) == 102        # 96 métropole + Corse (2A/2B) + 6 DOM
    assert DEPARTMENTS['43'] == 'Haute-Loire'
    assert DEPARTMENTS['974'] == 'La Réunion'


def test_dept_apres_rst():
    """Le RST de tête est retiré ; le département suit."""
    assert dept_from_exchange('59 042') == '04'     # RST 59 + dept 04
    assert dept_from_exchange('599 042') == '04'    # RST CW 599 + dept 04
    assert dept_from_exchange('59 75') == '75'      # RST 59 + Paris
    assert dept_from_exchange('75') == '75'         # dept seul (Paris, non-RST)
    assert dept_from_exchange('599 999') == ''      # 999 invalide, pas de dept


def test_corse_et_dom():
    assert dept_from_exchange('2A 015') == '2A'
    assert dept_from_exchange('58 2B') == '2B'
    assert dept_from_exchange('5NN 971') == '971'   # Guadeloupe (DOM)


def test_echange_sans_dept():
    assert dept_from_exchange('abc') == ''
    assert dept_from_exchange('') == ''
    assert dept_from_exchange('599 999') == ''      # 99 n'est pas un département


def test_comptage_distinct():
    log = [
        {'contest': 'REF_160M', 'num_rcvd': '59 04'},    # 04
        {'contest': 'REF_160M', 'num_rcvd': '599 04'},   # 04 (doublon)
        {'contest': 'REF_160M', 'num_rcvd': '59 75'},    # Paris
        {'contest': 'REF_160M', 'num_rcvd': '5NN 2A'},   # 2A
        {'contest': 'AUTRE', 'num_rcvd': '59 13'},       # autre concours : ignoré
    ]
    depts = department_mult_count(log, 'REF_160M')
    assert depts == {'04', '75', '2A'}
