# -*- coding: utf-8 -*-
"""Perf hot path — logx_wca.search_castles pliait les accents (strip_accents)
pour les ~15-20k châteaux à CHAQUE frappe, sous le lock. L'index plié est
désormais précalculé une fois au chargement ; la recherche n'appelle plus
strip_accents que pour la REQUÊTE, pas par item."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_wca as wca
import logx_activation_db as adb


def _items():
    def it(code, name, loc):
        return {'code': code, 'name': name, 'location': loc,
                '_name_folded': adb.strip_accents(name).lower(),
                '_loc_folded': adb.strip_accents(loc).lower()}
    return [
        it('FF-0001', 'Château de Québec', 'Ville A'),
        it('FF-0002', 'Manoir de Quévert', 'Quimper'),
        it('FF-0003', 'Fort de Brest', 'Brest'),
        it('FF-0004', 'Tour Solidor', 'Saint-Malo'),
        it('FF-0005', 'Château du Taureau', 'Carantec'),
    ]


def test_search_ne_plie_pas_les_accents_par_item(monkeypatch):
    wca._state['list'] = _items()
    wca._state['by_code'] = {c['code']: c for c in wca._state['list']}
    wca._state['loaded'] = True
    wca._state['loading'] = False
    appels = []
    orig = adb.strip_accents
    monkeypatch.setattr(adb, 'strip_accents', lambda s: appels.append(1) or orig(s))
    res = wca.search_castles('que')
    assert any('Québec' in r['name'] for r in res), "la recherche doit toujours trouver Québec"
    assert len(appels) <= 2, f"strip_accents appelé {len(appels)}x (devrait être ~1, pour la requête seule)"
