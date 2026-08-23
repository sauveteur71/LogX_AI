# -*- coding: utf-8 -*-
"""Concurrence de l'index partagé (logx_callhistory.py) — Strate 2, haute.

build_index() renvoie l'objet _index VIVANT ; export_index/suggest/near_matches
l'itéraient hors verrou. Sous ThreadingHTTPServer, un QSO logué en concurrence
(update_from_qso -> _feed_qso -> _index.setdefault) AJOUTE une clé pendant
l'itération -> `RuntimeError: dictionary changed size during iteration`.

Ces tests provoquent la mutation de façon DÉTERMINISTE pendant l'itération (via
un hook sur une fonction appelée DANS la boucle vulnérable) et exigent que la
fonction termine sans lever. Rouges sur le code d'origine, verts après le
correctif (itération sur un instantané pris sous verrou).
"""
import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_callhistory as ch  # noqa: E402


def _seed(n=60):
    with ch._lock:
        ch._index.clear()
        for i in range(n):
            ch._index['CALL%03d' % i] = {'dept': None, 'locator': None,
                                         'qso_count': 1, 'last_date': None}
        ch._built_at = time.time()  # bloque le rebuild (TTL) pendant le test


def _ajoute_une_cle():
    with ch._lock:
        ch._index['NOUVEAU'] = {'dept': None, 'locator': None,
                                'qso_count': 0, 'last_date': None}


def test_export_index_resiste_a_un_ajout_pendant_l_iteration(monkeypatch):
    _seed()
    # ch_slice non vide -> _apply_call_history est appelé DANS la boucle (l.660).
    monkeypatch.setattr(ch, '_ch_slice', lambda contest: {'ZZ': {'dept': '01'}})
    orig = ch._apply_call_history
    fired = {'x': False}

    def hooked(e, ch_entry):
        if not fired['x']:
            fired['x'] = True
            _ajoute_une_cle()
        return orig(e, ch_entry)

    monkeypatch.setattr(ch, '_apply_call_history', hooked)
    out = ch.export_index(shared_log=[], contest='X')   # ne doit PAS lever
    assert isinstance(out, dict)
    assert fired['x'], "le hook in-loop n'a pas été déclenché (test inopérant)"


def test_near_matches_resiste_a_un_ajout_pendant_l_iteration(monkeypatch):
    _seed()
    orig = ch._one_edit_away
    fired = {'x': False}

    def hooked(a, b):
        if not fired['x']:
            fired['x'] = True
            _ajoute_une_cle()
        return orig(a, b)

    monkeypatch.setattr(ch, '_one_edit_away', hooked)
    # 'CALL00X' : longueur 7 (comme les seeds) et absent de l'index -> la boucle
    # atteint _one_edit_away pour au moins une entrée de même longueur.
    out = ch.near_matches('CALL00X')                    # ne doit PAS lever
    assert isinstance(out, list)
    assert fired['x'], "le hook in-loop n'a pas été déclenché (test inopérant)"
