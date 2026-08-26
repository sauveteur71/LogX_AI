# -*- coding: utf-8 -*-
"""Alertes — un critère `status` de valeur inconnue ne doit PAS laisser passer
le spot (audit STRATE-3 logx_alerts.py:43). L'ancien code ne gérait que
'new_mult' et 'already_done' ; toute autre valeur (typo, ou futur enum ajouté à
l'UI mais pas ici) traversait les deux `if` → le critère ne filtrait plus, la
règle se déclenchait sur des spots qu'elle aurait dû exclure (fail-OPEN =
alertes parasites). Pour un système d'alerte, un critère qu'on ne sait pas
évaluer doit échouer FERMÉ."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_alerts as alerts  # noqa: E402

SPOT_JA = {'call': 'JA1ABC', 'band': '21', 'dx_continent': 'AS', 'dx_cq_zone': '25',
           'new_mult': True, 'already_done': False, 'info': 'POTA JA-1234 QRP'}
SPOT_F = {'call': 'F4GLD', 'band': '14', 'dx_continent': 'EU', 'dx_cq_zone': '14',
          'new_mult': False, 'already_done': True, 'info': ''}


def test_statut_inconnu_echoue_ferme():
    # 'needed' n'est pas géré : la règle ne doit matcher AUCUN spot.
    rule = {'name': 'x', 'status': 'needed'}
    assert not alerts.evaluate_rule(rule, SPOT_JA)
    assert not alerts.evaluate_rule(rule, SPOT_F)


def test_statut_any_ne_filtre_pas():
    rule = {'name': 'x', 'status': 'any'}
    assert alerts.evaluate_rule(rule, SPOT_JA)
    assert alerts.evaluate_rule(rule, SPOT_F)


def test_statut_absent_ne_filtre_pas():
    # Défaut = 'any' : pas de filtre statut.
    assert alerts.evaluate_rule({'name': 'x'}, SPOT_JA)


def test_statuts_connus_filtrent_correctement():
    assert alerts.evaluate_rule({'name': 'x', 'status': 'new_mult'}, SPOT_JA)
    assert not alerts.evaluate_rule({'name': 'x', 'status': 'new_mult'}, SPOT_F)
    assert alerts.evaluate_rule({'name': 'x', 'status': 'already_done'}, SPOT_F)
    assert not alerts.evaluate_rule({'name': 'x', 'status': 'already_done'}, SPOT_JA)
