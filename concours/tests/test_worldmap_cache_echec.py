# -*- coding: utf-8 -*-
"""Empoisonnement du cache de la carte monde (logx_worldmap.py) — Strate 2, haute.

_entity_feature_map() mettait en cache le mapping {préfixe DXCC: feature}
INCONDITIONNELLEMENT. Si _load_features() échouait transitoirement (GeoJSON pas
encore prêt, lecture ratée), le mapping calculé était vide — et cet état vide
était mémorisé pour toute la session : plus aucun pays ne pouvait apparaître
comme travaillé sur la carte monde, même après que le GeoJSON redevienne
lisible. Ce test exige qu'un mapping vide (échec) ne soit PAS mis en cache.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_worldmap as wm   # noqa: E402
import logx_dxcc            # noqa: E402


def test_echec_transitoire_ne_met_pas_en_cache_un_mapping_vide(monkeypatch):
    wm.invalidate_cache()
    monkeypatch.setattr(wm, '_load_features', lambda: [])                       # échec de chargement
    monkeypatch.setattr(logx_dxcc, 'list_entities',
                        lambda: [{'prefix': 'F', 'lat': 47.0, 'lon': 2.0}])
    m = wm._entity_feature_map()
    assert m == {}
    assert wm._cache['entity_feature'] is None, (
        "un mapping vide (échec transitoire) a été mis en cache -> carte monde "
        "figée cassée pour toute la session"
    )


def test_chargement_reussi_est_mis_en_cache(monkeypatch):
    wm.invalidate_cache()
    monkeypatch.setattr(wm, '_load_features', lambda: [{'id': 'FR', 'geometry': {}}])
    monkeypatch.setattr(logx_dxcc, 'list_entities',
                        lambda: [{'prefix': 'F', 'lat': 47.0, 'lon': 2.0}])
    monkeypatch.setattr(wm, 'entity_to_feature_id',
                        lambda lat, lon, features=None: 'FR')
    m = wm._entity_feature_map()
    assert m == {'F': 'FR'}
    assert wm._cache['entity_feature'] == {'F': 'FR'}, "un mapping valide doit être mis en cache"
