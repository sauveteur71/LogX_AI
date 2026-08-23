# -*- coding: utf-8 -*-
"""Plancher anti-perte-massive sur la sauvegarde (logx_backup.py) — Strate 2, haute.

run_backup() écrivait un instantané SANS vérifier que le carnet n'était pas
(quasi) vide, puis _prune() supprimait les jeux les plus anciens de façon
inconditionnelle. Sur un carnet vidé (exactement l'incident du 19/08 :
DELETE FROM qso + shared_log à 0), chaque cycle automatique écrivait une
sauvegarde vide et, au bout de KEEP cycles, effaçait les 20 bonnes — le filet
de sécurité détruisait lui-même les données qu'il devait protéger.

Ce test place une bonne sauvegarde (100 QSO), vide le carnet, lance run_backup
et exige qu'AUCUNE sauvegarde rétrécie ne soit écrite et que la bonne survive.
"""
import glob
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_backup as bk  # noqa: E402


def _bonne_sauvegarde(folder, n=100):
    p = os.path.join(folder, 'logx_F4GLD_20260101-000000.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump([{'call': 'STA%03d' % i, 'band': '40m'} for i in range(n)], f)
    return p


def test_run_backup_refuse_une_perte_massive(tmp_path, monkeypatch):
    folder = str(tmp_path)
    monkeypatch.setattr(bk, 'backup_settings', lambda cfg: {'folder': folder})
    good = _bonne_sauvegarde(folder, 100)

    r = bk.run_backup({'callsign': 'F4GLD'}, shared_log=[])   # carnet vidé

    jsons = glob.glob(os.path.join(folder, 'logx_*.json'))
    assert jsons == [good], (
        "une sauvegarde vide/rétrécie a été écrite malgré la perte massive : %r" % jsons
    )
    assert os.path.isfile(good), "la bonne sauvegarde a été supprimée"
    assert r.get('ok') is False, "la sauvegarde aurait dû être refusée (perte massive)"


def test_run_backup_normal_ecrit_bien(tmp_path, monkeypatch):
    """Cas nominal : un carnet plein s'enregistre normalement (non-régression)."""
    folder = str(tmp_path)
    monkeypatch.setattr(bk, 'backup_settings', lambda cfg: {'folder': folder})
    _bonne_sauvegarde(folder, 100)

    r = bk.run_backup({'callsign': 'F4GLD'},
                      shared_log=[{'call': 'Z%03d' % i, 'band': '20m'} for i in range(120)])

    assert r.get('ok') is True
    jsons = sorted(glob.glob(os.path.join(folder, 'logx_*.json')))
    assert len(jsons) == 2, "la nouvelle sauvegarde (carnet plein) aurait dû être écrite : %r" % jsons
