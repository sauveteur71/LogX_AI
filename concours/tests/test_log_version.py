# -*- coding: utf-8 -*-
"""Compteur de fraîcheur du log (logx_storage.log_version) : /log/list ne doit
retransmettre le log complet que si la version a changé depuis le dernier
poll du client — voir bump_log_version() et son appel à chaque mutation de
shared_log (ajout/édition/suppression/import/reset)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_storage as storage
import logx_http as http


def _qso(**kw):
    base = {'call': 'F5ABC', 'band': '14', 'mode': 'SSB',
            'date': '20260720', 'time': '10:00'}
    base.update(kw)
    return base


def test_bump_log_version_incremente():
    storage.log_version = 0
    v1 = storage.bump_log_version()
    v2 = storage.bump_log_version()
    assert v1 == 1 and v2 == 2 and storage.log_version == 2


def test_add_qso_to_log_incremente_la_version(monkeypatch):
    monkeypatch.setattr(http, 'shared_log', [])
    monkeypatch.setattr(http, 'save_log_to_disk', lambda effacement_autorise=False: None)
    monkeypatch.setattr(http, 'current_config', {'usage_mode': 'simple'})
    storage.log_version = 0
    ok, _info = http.add_qso_to_log(dict(_qso()))
    assert ok
    assert storage.log_version == 1
