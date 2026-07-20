# -*- coding: utf-8 -*-
"""Tests du constructeur de règles d'alerte (logx_alerts)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_alerts as alerts

SPOT_JA = {'call': 'JA1ABC', 'band': '21', 'dx_continent': 'AS', 'dx_cq_zone': '25',
           'new_mult': True, 'already_done': False, 'info': 'POTA JA-1234 QRP'}
SPOT_F = {'call': 'F4GLD', 'band': '14', 'dx_continent': 'EU', 'dx_cq_zone': '14',
          'new_mult': False, 'already_done': True, 'info': ''}


def test_regle_vide_matche_tout():
    assert alerts.evaluate_rule({'name': 'x'}, SPOT_JA)
    assert alerts.evaluate_rule({'name': 'x'}, SPOT_F)


def test_regle_desactivee_ne_matche_jamais():
    rule = {'name': 'x', 'enabled': False}
    assert not alerts.evaluate_rule(rule, SPOT_JA)


def test_prefixe_indicatif():
    rule = {'name': 'x', 'call_prefix': 'JA,HL'}
    assert alerts.evaluate_rule(rule, SPOT_JA)
    assert not alerts.evaluate_rule(rule, SPOT_F)


def test_continent():
    rule = {'name': 'x', 'continent': 'as'}
    assert alerts.evaluate_rule(rule, SPOT_JA)
    assert not alerts.evaluate_rule(rule, SPOT_F)


def test_zone_cq_liste():
    rule = {'name': 'x', 'cq_zone': '25, 26'}
    assert alerts.evaluate_rule(rule, SPOT_JA)
    assert not alerts.evaluate_rule(rule, SPOT_F)


def test_bande():
    rule = {'name': 'x', 'band': '21,28'}
    assert alerts.evaluate_rule(rule, SPOT_JA)
    assert not alerts.evaluate_rule(rule, SPOT_F)


def test_statut_nouveau_mult():
    rule = {'name': 'x', 'status': 'new_mult'}
    assert alerts.evaluate_rule(rule, SPOT_JA)
    assert not alerts.evaluate_rule(rule, SPOT_F)


def test_statut_deja_travaille():
    rule = {'name': 'x', 'status': 'already_done'}
    assert not alerts.evaluate_rule(rule, SPOT_JA)
    assert alerts.evaluate_rule(rule, SPOT_F)


def test_commentaire_contient_insensible_a_la_casse():
    rule = {'name': 'x', 'comment_contains': 'pota'}
    assert alerts.evaluate_rule(rule, SPOT_JA)
    assert not alerts.evaluate_rule(rule, SPOT_F)


def test_combinaison_et_logique():
    """Tous les critères doivent matcher — un seul en désaccord invalide la règle."""
    rule = {'name': 'DX Asie neuf', 'continent': 'AS', 'status': 'new_mult', 'band': '21'}
    assert alerts.evaluate_rule(rule, SPOT_JA)
    rule_bande_fausse = dict(rule, band='14')
    assert not alerts.evaluate_rule(rule_bande_fausse, SPOT_JA)


def test_spot_incomplet_ne_leve_jamais():
    rule = {'name': 'x', 'continent': 'EU', 'band': '14', 'status': 'new_mult',
           'comment_contains': 'test'}
    assert alerts.evaluate_rule(rule, {}) is False  # aucun champ -> aucun match, pas de crash


def test_check_alerts_ignore_les_regles_sans_nom():
    matches = alerts.check_alerts([{'call_prefix': 'JA'}], [SPOT_JA])
    assert matches == []


def test_check_alerts_remonte_regle_et_spot():
    matches = alerts.check_alerts(
        [{'id': 'r1', 'name': 'Asie neuf', 'continent': 'AS', 'status': 'new_mult'}],
        [SPOT_JA, SPOT_F])
    assert len(matches) == 1
    assert matches[0]['rule_id'] == 'r1' and matches[0]['rule_name'] == 'Asie neuf'
    assert matches[0]['spot']['call'] == 'JA1ABC'


def test_check_alerts_une_regle_desactivee_est_ignoree():
    matches = alerts.check_alerts([{'id': 'r1', 'name': 'x', 'enabled': False}], [SPOT_JA])
    assert matches == []


def test_check_alerts_plusieurs_regles_meme_spot():
    rules = [{'id': 'r1', 'name': 'Asie', 'continent': 'AS'},
            {'id': 'r2', 'name': 'Nouveau', 'status': 'new_mult'}]
    matches = alerts.check_alerts(rules, [SPOT_JA])
    assert len(matches) == 2
    assert {m['rule_id'] for m in matches} == {'r1', 'r2'}
