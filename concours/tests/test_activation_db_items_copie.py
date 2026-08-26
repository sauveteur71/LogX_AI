# -*- coding: utf-8 -*-
"""ActivationDatabase.items() doit renvoyer une COPIE, pas la liste interne
(audit STRATE-3 logx_activation_db.py:115). search() copie déjà
(`list(self._state['list'])`, l.151) mais items() renvoyait `self._state['list']`
tel quel : un appelant qui trie/ajoute/vide le résultat corromprait l'état
partagé de la base (lu sans copie par d'autres threads de requête)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logx_activation_db import ActivationDatabase


def _db_charge():
    db = ActivationDatabase('TEST', 'http://x', 'x.cache',
                            parse_fn=lambda c: [], valid_fn=lambda c: True)
    db._state['list'] = [{'code': 'F-0001'}, {'code': 'F-0002'}]
    db._state['loaded'] = True
    db.ensure_loading_started = lambda: None   # pas de chargement réseau
    return db


def test_items_renvoie_une_copie():
    db = _db_charge()
    obtenu = db.items()
    obtenu.append({'code': 'POISON'})
    obtenu.clear()
    # L'état interne ne doit pas avoir bougé.
    codes = [it['code'] for it in db.items()]
    assert codes == ['F-0001', 'F-0002'], "items() a exposé la liste interne (mutée depuis l'extérieur)"


def test_items_renvoie_bien_le_contenu():
    db = _db_charge()
    assert [it['code'] for it in db.items()] == ['F-0001', 'F-0002']
