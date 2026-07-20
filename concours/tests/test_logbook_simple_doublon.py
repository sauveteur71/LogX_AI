# -*- coding: utf-8 -*-
"""Logbook simple : recontacter la même station sur la même bande au fil des
années est normal (pas de règle concours "1 QSO/station/bande"). Avant ce
correctif, `add_qso_to_log` refusait l'enregistrement (409 « doublon »,
nécessite force=true) même hors concours, sur la seule base de
call+bande+mode+contest — sans notion de date."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as http


def _qso(**kw):
    base = {'call': 'F5ABC', 'band': '14', 'mode': 'SSB',
            'date': '20260720', 'time': '10:00'}
    base.update(kw)
    return base


def test_doublon_bloque_en_mode_contest(monkeypatch):
    monkeypatch.setattr(http, 'shared_log', [dict(_qso(date='20200101'))])
    monkeypatch.setattr(http, 'save_log_to_disk', lambda: None)
    monkeypatch.setattr(http, 'current_config', {'usage_mode': 'contest'})
    ok, info = http.add_qso_to_log(dict(_qso(date='20260720')))
    assert not ok and info.get('duplicate')


def test_doublon_autorise_en_mode_simple(monkeypatch):
    monkeypatch.setattr(http, 'shared_log', [dict(_qso(date='20200101'))])
    monkeypatch.setattr(http, 'save_log_to_disk', lambda: None)
    monkeypatch.setattr(http, 'current_config', {'usage_mode': 'simple'})
    ok, info = http.add_qso_to_log(dict(_qso(date='20260720')))
    assert ok and not info.get('duplicate')
