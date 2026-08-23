# -*- coding: utf-8 -*-
"""_corps() ne doit pas lever sur une entrée TLE malformée dans le cache.

charger_tle() promet « Ne lève jamais... le reste doit continuer de
fonctionner », mais _corps() dépaquetait directement chaque valeur en (l1, l2)
via `for cle, (l1, l2) in jeux.items()`. Une entrée qui n'est pas une paire
(cache recopié/édité/écrit par une autre version — cas explicitement envisagé)
levait ValueError AVANT le try interne, remontant à l'UI (position()/passages()
appellent _corps() HORS de leur try).

Correctif : ignorer toute entrée qui n'est pas une liste/tuple de 2 éléments.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_sat_passes as sp  # noqa: E402


def test_corps_ignore_une_entree_malformee(monkeypatch):
    monkeypatch.setattr(sp, 'HAS_EPHEM', True)   # sinon _corps sort avant la boucle
    cache = {'tle': {'ISS': 'garbage',                 # str, pas une paire
                     'AO-7': ['l1', 'l2', 'l3']}}      # 3 éléments, pas 2
    # ne doit PAS lever, et renvoyer None (aucune paire exploitable ne matche)
    assert sp._corps(cache, 'ISS') is None
    assert sp._corps(cache, 'AO-7') is None
    assert sp._corps(cache, 'INCONNU') is None
