# -*- coding: utf-8 -*-
"""Suppression distante (tombstones) BORNÉE — le carnet ne peut plus être vidé
par la synchro cloud (axe « carnet perdu »).

Avant : dès qu'un QSO local correspondait à un tombstone distant, la persistance
passait par save_log_to_disk(effacement_autorise=True), qui DÉSACTIVE intégrale-
ment le garde-fou anti-perte-massive de storage — et `removed` n'avait AUCUNE
borne. Un fichier de tombstones périmé, une copie de conflit Synology/Dropbox
(le glob matche aussi *_conflit.json), ou un fichier forgé (tombstones acceptés
NON signés sans secret d'équipe) pouvait donc propager une suppression de masse
par la seule porte où le garde-fou est éteint.

Correctif : _tombstone_removals() borne les suppressions distantes au même seuil
que _SEUIL_PERTE_MASSIVE — au-delà, AUCUNE n'est appliquée (et on alerte). En
deçà, la sauvegarde se fait garde-fou ARMÉ (plus d'effacement_autorise=True).
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_cloudsync as cs  # noqa: E402


def _log(n):
    return [{'id': 1000 + i, 'call': f'F{i}ABC', 'band': '14', 'mode': 'CW',
             'date': '20260801', 'time': '1203'} for i in range(n)]


def _pairs(qsos):
    return {(q['id'], cs._qso_key(q)) for q in qsos}


def test_suppression_distante_petite_est_appliquee():
    log = _log(10)
    removed, refus = cs._tombstone_removals(log, _pairs(log[:3]), 25)
    assert refus == 0
    assert {q['id'] for q in removed} == {1000, 1001, 1002}


def test_suppression_distante_de_masse_est_refusee():
    log = _log(40)
    # 30 tombstones distants (>= seuil 25) : suspect -> AUCUNE suppression
    removed, refus = cs._tombstone_removals(log, _pairs(log[:30]), 25)
    assert removed == [], "une suppression distante de masse doit être refusée en bloc"
    assert refus == 30


def test_pile_au_seuil_est_refusee():
    log = _log(30)
    removed, refus = cs._tombstone_removals(log, _pairs(log[:25]), 25)
    assert removed == [] and refus == 25   # >= seuil, comme le garde-fou storage
