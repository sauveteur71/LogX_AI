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


def test_dept_seul_production():
    """Cas de PRODUCTION : le champ DEPT RCU contient le département SEUL, y
    compris ceux dont le n° ressemble à un RST (13, 33, 44, 59...)."""
    for d in ['33', '59', '13', '44', '31', '35', '43', '54', '57', '75', '06', '90']:
        assert dept_from_exchange(d) == d, f"dept seul {d} perdu"
    assert dept_from_exchange('971') == '971'       # DOM
    assert dept_from_exchange('2A') == '2A'


def test_dept_format_combine():
    """Format combiné « RST dept » (plusieurs tokens) : le RST de tête est retiré."""
    assert dept_from_exchange('59 04') == '04'      # RST 59 + dept 04
    assert dept_from_exchange('599 04') == '04'     # RST CW 599 + dept 04
    assert dept_from_exchange('59 33') == '33'      # RST 59 + Gironde
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
    # Format de production : département seul dans num_rcvd
    log = [
        {'contest': 'REF_160M', 'num_rcvd': '33'},   # Gironde
        {'contest': 'REF_160M', 'num_rcvd': '33'},   # doublon
        {'contest': 'REF_160M', 'num_rcvd': '59'},   # Nord
        {'contest': 'REF_160M', 'num_rcvd': '2A'},   # Corse-du-Sud
        {'contest': 'AUTRE', 'num_rcvd': '13'},      # autre concours : ignoré
    ]
    depts = department_mult_count(log, 'REF_160M')
    assert depts == {'33', '59', '2A'}
