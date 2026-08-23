# -*- coding: utf-8 -*-
"""run_annual_update() utilise CURRENT_YEAR figé à l'import (logx_rules.py) — Strate 2, haute.

CURRENT_YEAR est figé au chargement du module. Sur un process long qui franchit
le 1er janvier, schedule_annual_check détecte le changement d'année via
datetime.now().year (frais) mais run_annual_update réécrit results['year'] =
CURRENT_YEAR (périmé) et calcule les dates pour l'année ÉCOULÉE : rules_db['year']
reste sur l'ancienne année, la condition de rollover reste vraie, et la mise à
jour reboucle chaque 24 h sans jamais converger — avec des dates de l'an passé
servies jusqu'au redémarrage.

Ce test fige CURRENT_YEAR sur une valeur différente de l'année réelle (simulant
le rollover) et exige que run_annual_update utilise l'année COURANTE.
"""
import datetime
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_rules as rules   # noqa: E402
import logx_storage          # noqa: E402


def test_run_annual_update_utilise_l_annee_courante(monkeypatch):
    monkeypatch.setattr(rules, 'CURRENT_YEAR', 1999)          # import figé (rollover simulé)
    monkeypatch.setattr(rules, 'check_rules_update', lambda cid: {})
    monkeypatch.setattr(rules.time, 'sleep', lambda s: None)
    monkeypatch.setattr(logx_storage, 'save_json_atomic', lambda *a, **k: None)
    annees = []
    monkeypatch.setattr(rules, 'calc_all_dates', lambda y=None: (annees.append(y) or {}))

    res = rules.run_annual_update()

    annee_reelle = datetime.datetime.now().year
    assert res['year'] == annee_reelle, (
        "run_annual_update doit utiliser l'année COURANTE, pas CURRENT_YEAR figé"
    )
    assert annee_reelle in annees, "calc_all_dates doit être appelé pour l'année courante"
