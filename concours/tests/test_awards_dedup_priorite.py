# -*- coding: utf-8 -*-
"""Awards — la déduplication de collect_all_qsos doit garder la source la PLUS
prioritaire (audit STRATE-3 logx_awards.py:96). Le code étendait
_read_qso_archive() (commenté « moins prioritaires ») AVANT _read_archives(),
et la déduplication garde la PREMIÈRE occurrence — donc la source la moins
prioritaire gagnait, à l'inverse de l'intention déclarée. Quand le même QSO
existe dans les deux sources avec des données différentes (ex. statut QSL), la
version prioritaire doit l'emporter."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_awards as awards


def _qso(origine):
    return {'call': 'DL1AA', 'band': '144', 'mode': 'SSB',
            'date': '20260101', 'time': '10:00', 'origine': origine}


def test_la_source_prioritaire_gagne_a_la_deduplication(monkeypatch):
    # Même QSO (même clé de dédup) dans les deux sources, données divergentes.
    monkeypatch.setattr(awards, '_read_qso_archive', lambda: [_qso('ANCIEN')])   # moins prioritaire
    monkeypatch.setattr(awards, '_read_archives', lambda: [_qso('ARCHIVES')])    # plus prioritaire
    awards.invalidate()
    qsos = awards.collect_all_qsos()
    match = [q for q in qsos if q.get('call') == 'DL1AA']
    assert len(match) == 1, "déduplication cassée : le QSO apparaît en double"
    assert match[0].get('origine') == 'ARCHIVES', \
        "la source MOINS prioritaire a gagné la déduplication"


def test_pas_de_regression_sur_les_qso_uniques(monkeypatch):
    # Deux QSO distincts, un par source : les deux doivent survivre.
    monkeypatch.setattr(awards, '_read_qso_archive',
                        lambda: [{'call': 'G3XYZ', 'band': '144', 'mode': 'CW',
                                  'date': '20260102', 'time': '11:00'}])
    monkeypatch.setattr(awards, '_read_archives', lambda: [_qso('ARCHIVES')])
    awards.invalidate()
    calls = {q.get('call') for q in awards.collect_all_qsos()}
    assert {'DL1AA', 'G3XYZ'} <= calls
