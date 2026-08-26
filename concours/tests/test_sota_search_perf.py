# -*- coding: utf-8 -*-
"""Perf hot path — logx_sota.search_summits pliait les accents pour les ~181k
sommets à CHAQUE frappe, sous _summits_lock. Index plié précalculé au
chargement ; la recherche ne plie plus que la requête."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_sota as sota


def _items():
    def it(code, name, region):
        return {'code': code, 'name': name, 'region': region,
                '_name_folded': sota._strip_accents(name).lower(),
                '_region_folded': sota._strip_accents(region).lower()}
    return [
        it('F/AB-001', 'Pic de Québeira', 'Alpes'),
        it('F/AB-002', 'Mont Quévert', 'Bretagne'),
        it('F/AB-003', 'Puy de Dôme', 'Auvergne'),
        it('F/AB-004', 'Aiguille du Midi', 'Alpes'),
        it('F/AB-005', 'Ballon d\'Alsace', 'Vosges'),
    ]


def test_search_summits_ne_plie_pas_par_item(monkeypatch):
    sota._summits['list'] = _items()
    sota._summits['by_code'] = {s['code']: s for s in sota._summits['list']}
    sota._summits['loaded'] = True
    sota._summits['loading'] = False
    appels = []
    orig = sota._strip_accents
    monkeypatch.setattr(sota, '_strip_accents', lambda s: appels.append(1) or orig(s))
    res = sota.search_summits('que')
    assert any('Québeira' in r['name'] for r in res), "doit trouver Québeira"
    assert len(appels) <= 2, f"_strip_accents appelé {len(appels)}x (devrait être ~1)"
