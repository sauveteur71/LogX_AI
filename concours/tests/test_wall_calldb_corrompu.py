# -*- coding: utf-8 -*-
"""Audit : _load_calldb ne mémorisait pas le mtime d'un calldb.json corrompu ->
re-parsé à CHAQUE poll du mur. Désormais le mtime d'échec est mémorisé : on ne
re-parse que si le fichier change réellement."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_wall as wall


def test_calldb_corrompu_parse_une_seule_fois(monkeypatch, tmp_path):
    (tmp_path / 'calldb.json').write_text('{ ceci nest pas du json', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    wall._calldb_cache['mtime'] = None
    wall._calldb_cache['calls'] = {}
    appels = []
    orig = wall.json.load
    monkeypatch.setattr(wall.json, 'load', lambda f: appels.append(1) or orig(f))
    wall._load_calldb()
    wall._load_calldb()
    assert len(appels) == 1, "le calldb corrompu ne doit être parsé qu'une fois (mtime mémorisé)"
