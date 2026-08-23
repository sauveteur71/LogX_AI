# -*- coding: utf-8 -*-
"""Un log importé SANS date exploitable était archivé sous la date du JOUR, et
best_for_contest en déduisait l'ANNÉE COURANTE : une édition de 2019 sans
QSO_DATE se faisait passer pour un record de l'année en cours (l'invariant que
la docstring d'archive_log dit vouloir empêcher).

Correctif : archive_log(date_reliable=False) trace le fait dans meta.json ;
best_for_contest ne revendique alors AUCUNE année. import_external_log passe
date_reliable=(when is not None) et signale res['date_missing'] (plus de silence).
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_archive as arch  # noqa: E402


def test_import_sans_date_ne_revendique_pas_l_annee(tmp_path, monkeypatch):
    monkeypatch.setattr(arch, 'ARCHIVE_DIR', str(tmp_path))
    qsos = [{'call': 'F5ABC', 'band': '20', 'mode': 'CW'}]   # aucune 'date'
    res = arch.archive_log(qsos, 'REF_HF', {'callsign': 'F4GLD'},
                           declared_score=100, date_reliable=False)
    assert res['ok'], res
    best = arch.best_for_contest('REF_HF')
    assert best and best['best_qso'] == 1, best
    assert best['best_qso_year'] is None, best
    assert best['best_points_year'] is None, best


def test_date_fiable_attribue_bien_l_annee(tmp_path, monkeypatch):
    monkeypatch.setattr(arch, 'ARCHIVE_DIR', str(tmp_path))
    qsos = [{'call': 'F5ABC', 'band': '20', 'mode': 'CW', 'date': '20190615'}]
    when = arch.datetime.datetime(2019, 6, 15)
    res = arch.archive_log(qsos, 'REF_HF', {'callsign': 'F4GLD'},
                           when=when, declared_score=50, date_reliable=True)
    assert res['ok'], res
    best = arch.best_for_contest('REF_HF')
    assert best['best_qso_year'] == '2019', best
