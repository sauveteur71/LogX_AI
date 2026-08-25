# -*- coding: utf-8 -*-
"""Enrichissement de la base interne (calldb) depuis le JOURNAL : les QSO déjà
loggués portent souvent un prénom/locator (annuaire, saisie passée). On en
alimente la base interne pour que l'auto-remplissage du prénom (#268) marche
IMMÉDIATEMENT pour tout correspondant déjà contacté, hors-ligne. Fonction PURE.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_departments as dep   # noqa: E402


def test_enrich_alimente_nom_et_locator():
    log = [
        {'call': 'F4ABC', 'name': 'Camille', 'locator': 'JN18DT'},
        {'call': 'DL1XYZ', 'name': 'Hans', 'locator': 'JO31'},
    ]
    calls, n = dep.enrich_calldb_from_log(log, {})
    assert n == 2
    assert calls['F4ABC'] == {'name': 'Camille', 'locator': 'JN18DT'}
    assert calls['DL1XYZ']['name'] == 'Hans'


def test_enrich_ne_compte_pas_les_qso_sans_apport():
    # un QSO sans nom ni locator n'apporte rien -> non compté
    calls, n = dep.enrich_calldb_from_log([{'call': 'F4ABC'}], {})
    assert n == 0 and 'F4ABC' not in calls


def test_enrich_ne_ecrase_pas_une_valeur_existante_par_du_vide():
    calls, n = dep.enrich_calldb_from_log(
        [{'call': 'F4ABC', 'name': ''}], {'F4ABC': {'name': 'Léa', 'locator': 'JN18'}})
    assert n == 0
    assert calls['F4ABC']['name'] == 'Léa'


def test_enrich_normalise_l_indicatif_portable():
    # F4ABC/P et F4ABC = la même station -> base indexée sur la racine
    calls, n = dep.enrich_calldb_from_log([{'call': 'f4abc/p', 'name': 'Jo'}], {})
    assert 'F4ABC' in calls and calls['F4ABC']['name'] == 'Jo'


def test_enrich_le_qso_le_plus_recent_prime():
    # deux QSO du même correspondant : le dernier (fin de liste) corrige le nom
    log = [{'call': 'F4ABC', 'name': 'Jean'}, {'call': 'F4ABC', 'name': 'Jean-Marc'}]
    calls, n = dep.enrich_calldb_from_log(log, {})
    assert calls['F4ABC']['name'] == 'Jean-Marc'


def test_enrich_ignore_les_entrees_sans_indicatif():
    calls, n = dep.enrich_calldb_from_log([{'name': 'X'}, {'call': '', 'name': 'Y'}], {})
    assert n == 0 and calls == {}


def test_enrich_ne_mute_pas_la_base_source():
    src = {'F4ABC': {'locator': 'JN18'}}
    calls, _ = dep.enrich_calldb_from_log([{'call': 'F4ABC', 'name': 'Zoé'}], src)
    assert 'name' not in src['F4ABC']        # source intacte
    assert calls['F4ABC']['name'] == 'Zoé'
